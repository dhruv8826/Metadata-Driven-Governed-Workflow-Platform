import sqlite3
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context
from app.workflow.engine import WorkflowEngine

router = APIRouter(prefix="/api/records", tags=["Transitions & Lifecycle"])

class TransitionPayload(BaseModel):
    transition_name: str

@router.post("/{record_id}/transitions")
def trigger_transition(
    record_id: str,
    payload: TransitionPayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    return WorkflowEngine.execute_transition(
        db=db,
        tenant_id=ctx.tenant_id,
        record_id=record_id,
        transition_name=payload.transition_name,
        actor_id=ctx.actor_id,
        actor_role=ctx.actor_role
    )
