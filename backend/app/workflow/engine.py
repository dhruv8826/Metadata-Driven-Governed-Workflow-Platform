import json
import sqlite3
import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException
from app.workflow.rules import RuleEvaluator
from app.services.audit import AuditService

class WorkflowEngine:
    @staticmethod
    def execute_transition(
        db: sqlite3.Connection,
        tenant_id: str,
        record_id: str,
        transition_name: str,
        actor_id: str,
        actor_role: str
    ) -> Dict[str, Any]:
        cursor = db.cursor()

        # 1. Fetch record
        cursor.execute("""
            SELECT id, object_type, state, version, created_by, data
            FROM records
            WHERE id = ? AND tenant_id = ? AND is_deleted = 0;
        """, (record_id, tenant_id))
        rec = cursor.fetchone()
        if not rec:
            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION", outcome="DENIED",
                reason=f"Record '{record_id}' not found",
                record_id=record_id
            )
            raise HTTPException(status_code=404, detail="Record not found")

        object_type = rec["object_type"]
        current_state = rec["state"]
        record_data = json.loads(rec["data"])
        current_version = rec["version"]

        # 2. Fetch lifecycle
        cursor.execute("""
            SELECT initial_state, states, transitions
            FROM metadata_lifecycles
            WHERE tenant_id = ? AND object_type = ?;
        """, (tenant_id, object_type))
        lc_row = cursor.fetchone()
        if not lc_row:
            raise HTTPException(status_code=400, detail=f"No lifecycle defined for '{object_type}'")

        transitions = json.loads(lc_row["transitions"])
        matched_transition = next((t for t in transitions if t["name"] == transition_name), None)

        if not matched_transition:
            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION", outcome="DENIED",
                object_type=object_type, record_id=record_id,
                reason=f"Transition '{transition_name}' does not exist"
            )
            raise HTTPException(status_code=400, detail=f"Unknown transition '{transition_name}'")

        # 3. State validation
        if matched_transition["from_state"] != current_state:
            reason = f"Transition '{transition_name}' cannot be applied from state '{current_state}'. Expected '{matched_transition['from_state']}'."
            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION", outcome="DENIED",
                object_type=object_type, record_id=record_id,
                before_state=current_state, reason=reason
            )
            raise HTTPException(status_code=400, detail=reason)

        # 4. Role authorization
        allowed_roles = matched_transition.get("allowed_roles", [])
        if actor_role not in allowed_roles and actor_role != "Admin":
            reason = f"Role '{actor_role}' is not permitted to trigger transition '{transition_name}'. Allowed: {allowed_roles}"
            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION", outcome="DENIED",
                object_type=object_type, record_id=record_id,
                before_state=current_state, reason=reason
            )
            raise HTTPException(status_code=403, detail=reason)

        # 5. Guard evaluation
        guard_expr = matched_transition.get("guard")
        if guard_expr:
            passed = RuleEvaluator.evaluate(guard_expr, record_data)
            if not passed:
                guard_msg = matched_transition.get("guard_error_message", "Transition guard condition failed.")
                AuditService.log(
                    db, tenant_id, actor_id, actor_role,
                    action="TRANSITION", outcome="GUARD_FAILED",
                    object_type=object_type, record_id=record_id,
                    before_state=current_state, reason=guard_msg
                )
                raise HTTPException(status_code=400, detail=f"Guard check failed: {guard_msg}")

        # 6. Check approval requirement
        requires_approval = matched_transition.get("requires_approval", False)

        # Check skip approval rule (e.g. priority == 'Emergency')
        skip_rule = matched_transition.get("skip_approval_rule")
        if skip_rule and RuleEvaluator.evaluate(skip_rule, record_data):
            requires_approval = False

        target_state = matched_transition["to_state"]

        if requires_approval:
            # Route approval to required role
            approval_routing = matched_transition.get("approval_routing", {})
            required_role = "Manager"  # default
            rule_config = approval_routing.get("rule", {})
            if rule_config:
                condition = rule_config.get("condition")
                if RuleEvaluator.evaluate(condition, record_data):
                    required_role = rule_config.get("role_if_true", "Director")
                else:
                    required_role = rule_config.get("role_if_false", "Manager")

            # Determine next record state: transition to target_state or intermediate state
            # If target_state is 'Submitted' or 'Scheduled', we update record state and create pending approval
            new_version = current_version + 1
            approval_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO approval_requests (
                    id, tenant_id, record_id, transition_name, target_state,
                    requester_id, required_role, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING');
            """, (
                approval_id, tenant_id, record_id, transition_name, target_state,
                actor_id, required_role
            ))

            cursor.execute("""
                UPDATE records
                SET state = ?, version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (target_state, new_version, actor_id, record_id))

            cursor.execute("""
                INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (str(uuid.uuid4()), tenant_id, record_id, new_version, target_state, rec["data"], actor_id))

            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION_REQUEST_APPROVAL", outcome="PENDING_APPROVAL",
                object_type=object_type, record_id=record_id,
                before_state=current_state, after_state=target_state,
                reason=f"Transition '{transition_name}' requires approval from role '{required_role}'"
            )
            db.commit()

            return {
                "record_id": record_id,
                "previous_state": current_state,
                "current_state": target_state,
                "requires_approval": True,
                "pending_approval": {
                    "id": approval_id,
                    "required_role": required_role,
                    "target_state": target_state
                }
            }
        else:
            # Direct transition without approval
            new_version = current_version + 1
            cursor.execute("""
                UPDATE records
                SET state = ?, version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (target_state, new_version, actor_id, record_id))

            cursor.execute("""
                INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (str(uuid.uuid4()), tenant_id, record_id, new_version, target_state, rec["data"], actor_id))

            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action="TRANSITION", outcome="SUCCESS",
                object_type=object_type, record_id=record_id,
                before_state=current_state, after_state=target_state,
                reason=f"Direct transition '{transition_name}' to '{target_state}'"
            )
            db.commit()

            return {
                "record_id": record_id,
                "previous_state": current_state,
                "current_state": target_state,
                "requires_approval": False
            }

    @staticmethod
    def execute_approval_decision(
        db: sqlite3.Connection,
        tenant_id: str,
        approval_id: str,
        actor_id: str,
        actor_role: str,
        decision: str,  # "APPROVE" or "REJECT"
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        cursor = db.cursor()

        # Atomic transaction to eliminate race conditions
        cursor.execute("BEGIN IMMEDIATE;")
        try:
            cursor.execute("""
                SELECT id, record_id, transition_name, target_state, requester_id, required_role, status
                FROM approval_requests
                WHERE id = ? AND tenant_id = ?;
            """, (approval_id, tenant_id))
            approval = cursor.fetchone()

            if not approval:
                raise HTTPException(status_code=404, detail="Approval request not found")

            record_id = approval["record_id"]
            requester_id = approval["requester_id"]
            required_role = approval["required_role"]
            status = approval["status"]
            target_state = approval["target_state"]

            # 1. Race condition check
            if status != "PENDING":
                AuditService.log(
                    db, tenant_id, actor_id, actor_role,
                    action="APPROVAL_DECISION", outcome="CONFLICT",
                    record_id=record_id, reason="Approval request already processed by another approver"
                )
                raise HTTPException(status_code=409, detail="Approval request has already been processed")

            # 2. Self-approval block
            if actor_id == requester_id:
                AuditService.log(
                    db, tenant_id, actor_id, actor_role,
                    action="SELF_APPROVAL_ATTEMPT", outcome="DENIED",
                    record_id=record_id, reason="Self-approval is strictly forbidden"
                )
                raise HTTPException(status_code=403, detail="Self-approval is strictly forbidden")

            # 3. Role authorization
            if actor_role != required_role and actor_role != "Admin":
                AuditService.log(
                    db, tenant_id, actor_id, actor_role,
                    action="APPROVAL_DECISION", outcome="DENIED",
                    record_id=record_id, reason=f"Unauthorized approver role '{actor_role}'. Requires '{required_role}'."
                )
                raise HTTPException(status_code=403, detail=f"Unauthorized to approve. Requires role '{required_role}'")

            # 4. Fetch current record
            cursor.execute("""
                SELECT state, version, data, object_type
                FROM records
                WHERE id = ? AND tenant_id = ?;
            """, (record_id, tenant_id))
            rec = cursor.fetchone()
            if not rec:
                raise HTTPException(status_code=404, detail="Record not found")

            current_state = rec["state"]
            current_version = rec["version"]
            raw_data = rec["data"]
            object_type = rec["object_type"]

            # 5. Apply decision
            new_approval_status = "APPROVED" if decision.upper() == "APPROVE" else "REJECTED"
            
            # Map next state
            if decision.upper() == "APPROVE":
                next_record_state = "Approved" if current_state == "Submitted" else target_state
            else:
                next_record_state = "Rejected"

            cursor.execute("""
                UPDATE approval_requests
                SET status = ?, decision_by = ?, decision_role = ?, decision_reason = ?, decided_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'PENDING';
            """, (new_approval_status, actor_id, actor_role, reason, approval_id))

            new_version = current_version + 1
            cursor.execute("""
                UPDATE records
                SET state = ?, version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (next_record_state, new_version, actor_id, record_id))

            cursor.execute("""
                INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (str(uuid.uuid4()), tenant_id, record_id, new_version, next_record_state, raw_data, actor_id))

            AuditService.log(
                db, tenant_id, actor_id, actor_role,
                action=f"APPROVAL_{new_approval_status}", outcome="SUCCESS",
                object_type=object_type, record_id=record_id,
                before_state=current_state, after_state=next_record_state,
                reason=reason or f"Request {new_approval_status.lower()} by {actor_role}"
            )

            db.commit()
            return {
                "approval_id": approval_id,
                "record_id": record_id,
                "status": new_approval_status,
                "new_record_state": next_record_state
            }
        except Exception:
            db.rollback()
            raise
