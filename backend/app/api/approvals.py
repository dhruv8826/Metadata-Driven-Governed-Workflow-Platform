import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context
from app.workflow.engine import WorkflowEngine

router = APIRouter(prefix="/api/approvals", tags=["Approvals Broker"])

class ApprovalDecisionPayload(BaseModel):
    decision: str  # "APPROVE" or "REJECT"
    reason: Optional[str] = None

@router.get("/pending")
def list_pending_approvals(
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    query = """
        SELECT a.id, a.record_id, a.transition_name, a.target_state,
               a.requester_id, a.required_role, a.status, a.created_at,
               r.object_type, r.data, r.state as current_record_state
        FROM approval_requests a
        JOIN records r ON a.record_id = r.id
        WHERE a.tenant_id = ? AND a.status = 'PENDING'
    """
    params = [ctx.tenant_id]

    # Non-admins only see approvals matching their role
    if ctx.actor_role != "Admin":
        query += " AND a.required_role = ?"
        params.append(ctx.actor_role)

    query += " ORDER BY a.created_at DESC;"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "record_id": r["record_id"],
            "object_type": r["object_type"],
            "current_record_state": r["current_record_state"],
            "transition_name": r["transition_name"],
            "target_state": r["target_state"],
            "requester_id": r["requester_id"],
            "required_role": r["required_role"],
            "created_at": r["created_at"],
            "can_approve": (ctx.actor_id != r["requester_id"]) and (ctx.actor_role == r["required_role"] or ctx.actor_role == "Admin")
        })
    return results

@router.post("/{approval_id}/decision")
def submit_approval_decision(
    approval_id: str,
    payload: ApprovalDecisionPayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    return WorkflowEngine.execute_approval_decision(
        db=db,
        tenant_id=ctx.tenant_id,
        approval_id=approval_id,
        actor_id=ctx.actor_id,
        actor_role=ctx.actor_role,
        decision=payload.decision,
        reason=payload.reason
    )
