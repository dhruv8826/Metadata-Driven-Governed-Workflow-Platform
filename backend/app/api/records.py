import json
import uuid
import sqlite3
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context
from app.core.config import MAX_PAGE_SIZE, DEFAULT_PAGE_SIZE
from app.security.rbac import RBACService
from app.security.projection import FieldProjector
from app.workflow.rules import RuleEvaluator
from app.services.audit import AuditService, compute_field_diff

router = APIRouter(prefix="/api/records", tags=["Records Engine"])

class RecordCreatePayload(BaseModel):
    data: Dict[str, Any]

class RecordUpdatePayload(BaseModel):
    data: Dict[str, Any]

@router.get("/{object_type}")
def list_records(
    object_type: str,
    state: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_read"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="READ_LIST", outcome="DENIED",
            object_type=object_type, reason="Persona does not have read permissions for this object"
        )
        raise HTTPException(status_code=403, detail="Access denied for this entity")

    cursor = db.cursor()
    query = """
        SELECT id, tenant_id, object_type, state, version, created_by, created_at, updated_at, data
        FROM records
        WHERE tenant_id = ? AND object_type = ? AND is_deleted = 0
    """
    params = [ctx.tenant_id, object_type]

    if state:
        query += " AND state = ?"
        params.append(state)

    order_direction = "DESC" if sort_order.lower() == "desc" else "ASC"
    if sort_by in ["created_at", "updated_at", "state", "version"]:
        query += f" ORDER BY {sort_by} {order_direction}"
    else:
        query += f" ORDER BY created_at {order_direction}"

    query += " LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    # Total count query
    count_query = "SELECT COUNT(*) FROM records WHERE tenant_id = ? AND object_type = ? AND is_deleted = 0"
    count_params = [ctx.tenant_id, object_type]
    if state:
        count_query += " AND state = ?"
        count_params.append(state)
    cursor.execute(count_query, tuple(count_params))
    total_count = cursor.fetchone()[0]

    # Project fields server-side
    field_perms = perms["field_permissions"]
    projected_records = []
    for r in rows:
        rec_dict = {
            "id": r["id"],
            "tenant_id": r["tenant_id"],
            "object_type": r["object_type"],
            "state": r["state"],
            "version": r["version"],
            "created_by": r["created_by"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "data": json.loads(r["data"])
        }
        projected_records.append(FieldProjector.project_read_record(rec_dict, field_perms))

    return {
        "object_type": object_type,
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "items": projected_records
    }

@router.get("/{object_type}/{record_id}")
def get_record_detail(
    object_type: str,
    record_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_read"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="READ_RECORD", outcome="DENIED",
            object_type=object_type, record_id=record_id,
            reason="Persona does not have read permissions for this object"
        )
        raise HTTPException(status_code=403, detail="Access denied for this entity")

    cursor = db.cursor()
    cursor.execute("""
        SELECT id, tenant_id, object_type, state, version, created_by, created_at, updated_by, updated_at, data
        FROM records
        WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0;
    """, (record_id, ctx.tenant_id, object_type))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")

    # Fetch version history
    cursor.execute("""
        SELECT version, state, data, changed_by, changed_at
        FROM record_versions
        WHERE record_id = ? AND tenant_id = ?
        ORDER BY version DESC;
    """, (record_id, ctx.tenant_id))
    version_rows = cursor.fetchall()
    versions = [{
        "version": vr["version"],
        "state": vr["state"],
        "data": json.loads(vr["data"]),
        "changed_by": vr["changed_by"],
        "changed_at": vr["changed_at"]
    } for vr in version_rows]

    # Fetch pending approvals
    cursor.execute("""
        SELECT id, transition_name, target_state, requester_id, required_role, status, created_at
        FROM approval_requests
        WHERE record_id = ? AND tenant_id = ? AND status = 'PENDING'
        ORDER BY created_at DESC LIMIT 1;
    """, (record_id, ctx.tenant_id))
    appr_row = cursor.fetchone()
    pending_approval = None
    if appr_row:
        pending_approval = {
            "id": appr_row["id"],
            "transition_name": appr_row["transition_name"],
            "target_state": appr_row["target_state"],
            "requester_id": appr_row["requester_id"],
            "required_role": appr_row["required_role"],
            "status": appr_row["status"],
            "created_at": appr_row["created_at"],
            "can_approve": (ctx.actor_role == appr_row["required_role"] or ctx.actor_role == "Admin") and (ctx.actor_id != appr_row["requester_id"])
        }

    rec_dict = {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "object_type": row["object_type"],
        "state": row["state"],
        "version": row["version"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_by": row["updated_by"],
        "updated_at": row["updated_at"],
        "data": json.loads(row["data"]),
        "versions": versions,
        "pending_approval": pending_approval
    }

    # Strict server-side projection of current and past versions
    return FieldProjector.project_read_record(rec_dict, perms["field_permissions"])

@router.post("/{object_type}")
def create_record(
    object_type: str,
    payload: RecordCreatePayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_create"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="CREATE", outcome="DENIED",
            object_type=object_type, reason="Persona does not have create permission for this object"
        )
        raise HTTPException(status_code=403, detail="Creation not permitted for your role")

    cursor = db.cursor()
    # 1. Fetch metadata schema
    cursor.execute("""
        SELECT schema_definition, validation_rules
        FROM metadata_objects
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    obj_row = cursor.fetchone()
    if not obj_row:
        raise HTTPException(status_code=404, detail=f"Object '{object_type}' not defined")

    schema_fields = json.loads(obj_row["schema_definition"])
    validation_rules = json.loads(obj_row["validation_rules"] or "[]")

    # 2. Check field-level write permissions
    sanitized_data, forbidden_fields = FieldProjector.validate_and_filter_write(
        payload.data, perms["field_permissions"]
    )
    if forbidden_fields:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="CREATE", outcome="DENIED",
            object_type=object_type, reason=f"Attempted to edit forbidden fields: {forbidden_fields}"
        )
        raise HTTPException(status_code=403, detail=f"Cannot populate forbidden fields: {forbidden_fields}")

    # 3. Validate required fields
    for field in schema_fields:
        field_name = field["name"]
        if field.get("required") and sanitized_data.get(field_name) in [None, ""]:
            raise HTTPException(
                status_code=422,
                detail=f"Field '{field.get('label', field_name)}' is required."
            )

        # 4. Reference target validation (ensure referenced record exists in the SAME tenant and is not deleted)
        if field.get("type") == "reference" and sanitized_data.get(field_name):
            ref_target = field.get("reference_target")
            ref_val = sanitized_data[field_name]
            cursor.execute("""
                SELECT 1 FROM records
                WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0;
            """, (ref_val, ctx.tenant_id, ref_target))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=422,
                    detail=f"Referenced {ref_target} '{ref_val}' does not exist within the active tenant."
                )

    # 5. Evaluate cross-field validation rules
    rule_errors = RuleEvaluator.validate_record_rules(validation_rules, sanitized_data)
    if rule_errors:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="CREATE", outcome="FAILED_VALIDATION",
            object_type=object_type, reason="; ".join(rule_errors)
        )
        raise HTTPException(status_code=422, detail="; ".join(rule_errors))

    # 6. Fetch initial state
    cursor.execute("""
        SELECT initial_state FROM metadata_lifecycles
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    lc_row = cursor.fetchone()
    initial_state = lc_row["initial_state"] if lc_row else "Draft"

    record_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO records (
            id, tenant_id, object_type, state, version,
            created_by, updated_by, data, is_deleted
        ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, 0);
    """, (
        record_id, ctx.tenant_id, object_type, initial_state,
        ctx.actor_id, ctx.actor_id, json.dumps(sanitized_data)
    ))

    # Record version 1
    cursor.execute("""
        INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
        VALUES (?, ?, ?, 1, ?, ?, ?);
    """, (
        str(uuid.uuid4()), ctx.tenant_id, record_id, initial_state,
        json.dumps(sanitized_data), ctx.actor_id
    ))

    # Audit log entry with granular diffs
    diffs = {k: {"old": None, "new": v} for k, v in sanitized_data.items()}
    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="CREATE", outcome="SUCCESS",
        object_type=object_type, record_id=record_id,
        after_state=initial_state, field_diffs=diffs,
        reason="Record created"
    )

    db.commit()

    created_rec = {
        "id": record_id,
        "tenant_id": ctx.tenant_id,
        "object_type": object_type,
        "state": initial_state,
        "version": 1,
        "created_by": ctx.actor_id,
        "data": sanitized_data
    }
    return FieldProjector.project_read_record(created_rec, perms["field_permissions"])

@router.put("/{object_type}/{record_id}")
def update_record(
    object_type: str,
    record_id: str,
    payload: RecordUpdatePayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_update"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="UPDATE", outcome="DENIED",
            object_type=object_type, record_id=record_id,
            reason="Persona does not have update permission for this object"
        )
        raise HTTPException(status_code=403, detail="Update not permitted for your role")

    cursor = db.cursor()
    cursor.execute("""
        SELECT state, version, data FROM records
        WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0;
    """, (record_id, ctx.tenant_id, object_type))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Record not found")

    old_data = json.loads(existing["data"])
    current_state = existing["state"]
    current_version = existing["version"]

    # Validate field edit permissions
    sanitized_delta, forbidden_fields = FieldProjector.validate_and_filter_write(
        payload.data, perms["field_permissions"]
    )
    if forbidden_fields:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="UPDATE", outcome="DENIED",
            object_type=object_type, record_id=record_id,
            reason=f"Attempted to edit forbidden fields: {forbidden_fields}"
        )
        raise HTTPException(status_code=403, detail=f"Cannot edit forbidden fields: {forbidden_fields}")

    # Merge data
    merged_data = old_data.copy()
    merged_data.update(sanitized_delta)

    # Validate references and cross-field rules on merged data
    cursor.execute("""
        SELECT schema_definition, validation_rules
        FROM metadata_objects
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    obj_row = cursor.fetchone()
    schema_fields = json.loads(obj_row["schema_definition"])
    validation_rules = json.loads(obj_row["validation_rules"] or "[]")

    for field in schema_fields:
        fn = field["name"]
        if field.get("type") == "reference" and merged_data.get(fn):
            ref_target = field.get("reference_target")
            cursor.execute("""
                SELECT 1 FROM records
                WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0;
            """, (merged_data[fn], ctx.tenant_id, ref_target))
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=422,
                    detail=f"Referenced {ref_target} does not exist within the active tenant."
                )

    rule_errors = RuleEvaluator.validate_record_rules(validation_rules, merged_data)
    if rule_errors:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="UPDATE", outcome="FAILED_VALIDATION",
            object_type=object_type, record_id=record_id,
            reason="; ".join(rule_errors)
        )
        raise HTTPException(status_code=422, detail="; ".join(rule_errors))

    # Calculate granular diffs
    diffs = compute_field_diff(old_data, merged_data)
    new_version = current_version + 1

    cursor.execute("""
        UPDATE records
        SET data = ?, version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?;
    """, (json.dumps(merged_data), new_version, ctx.actor_id, record_id))

    cursor.execute("""
        INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (str(uuid.uuid4()), ctx.tenant_id, record_id, new_version, current_state, json.dumps(merged_data), ctx.actor_id))

    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="UPDATE", outcome="SUCCESS",
        object_type=object_type, record_id=record_id,
        before_state=current_state, after_state=current_state,
        field_diffs=diffs, reason="Record data updated"
    )

    db.commit()

    updated_rec = {
        "id": record_id,
        "tenant_id": ctx.tenant_id,
        "object_type": object_type,
        "state": current_state,
        "version": new_version,
        "data": merged_data
    }
    return FieldProjector.project_read_record(updated_rec, perms["field_permissions"])

@router.delete("/{object_type}/{record_id}")
def delete_record(
    object_type: str,
    record_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_delete"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="DELETE", outcome="DENIED",
            object_type=object_type, record_id=record_id,
            reason="Persona does not have delete permission for this object"
        )
        raise HTTPException(status_code=403, detail="Deletion not permitted for your role")

    cursor = db.cursor()
    cursor.execute("""
        UPDATE records
        SET is_deleted = 1, updated_by = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND tenant_id = ? AND object_type = ?;
    """, (ctx.actor_id, record_id, ctx.tenant_id, object_type))

    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="DELETE", outcome="SUCCESS",
        object_type=object_type, record_id=record_id,
        reason="Record soft deleted"
    )
    db.commit()
    return {"status": "SUCCESS", "record_id": record_id, "is_deleted": True}
