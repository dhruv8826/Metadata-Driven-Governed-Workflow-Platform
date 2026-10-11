from dataclasses import dataclass
from fastapi import Header, HTTPException, Depends
from typing import Optional
import sqlite3
from app.core.database import get_db

@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    actor_id: str
    actor_role: str

def get_request_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    x_persona_role: Optional[str] = Header(None, alias="X-Persona-Role"),
    x_persona_id: Optional[str] = Header(None, alias="X-Persona-Id"),
    db: sqlite3.Connection = Depends(get_db)
) -> RequestContext:
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required header: X-Tenant-Id"
        )
    if not x_persona_role:
        raise HTTPException(
            status_code=400,
            detail="Missing required header: X-Persona-Role"
        )

    # Validate tenant exists
    cursor = db.cursor()
    cursor.execute("SELECT id FROM tenants WHERE id = ?;", (x_tenant_id,))
    tenant = cursor.fetchone()
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant '{x_tenant_id}' does not exist"
        )

    actor_id = x_persona_id or f"actor_{x_persona_role.lower()}"

    return RequestContext(
        tenant_id=x_tenant_id,
        actor_id=actor_id,
        actor_role=x_persona_role
    )
