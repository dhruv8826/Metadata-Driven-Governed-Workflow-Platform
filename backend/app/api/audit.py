import json
import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context

router = APIRouter(prefix="/api/audit", tags=["Audit & Governance"])

@router.get("")
def list_audit_trail(
    object_type: Optional[str] = Query(None),
    record_id: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    query = """
        SELECT id, tenant_id, actor_id, actor_role, action, object_type,
               record_id, outcome, reason, before_state, after_state,
               field_diffs, timestamp
        FROM audit_log
        WHERE tenant_id = ?
    """
    params = [ctx.tenant_id]

    if object_type:
        query += " AND object_type = ?"
        params.append(object_type)
    if record_id:
        query += " AND record_id = ?"
        params.append(record_id)
    if outcome:
        query += " AND outcome = ?"
        params.append(outcome)

    query += " ORDER BY id DESC LIMIT ?;"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "tenant_id": r["tenant_id"],
            "actor_id": r["actor_id"],
            "actor_role": r["actor_role"],
            "action": r["action"],
            "object_type": r["object_type"],
            "record_id": r["record_id"],
            "outcome": r["outcome"],
            "reason": r["reason"],
            "before_state": r["before_state"],
            "after_state": r["after_state"],
            "field_diffs": json.loads(r["field_diffs"]) if r["field_diffs"] else None,
            "timestamp": r["timestamp"]
        })

    return results
