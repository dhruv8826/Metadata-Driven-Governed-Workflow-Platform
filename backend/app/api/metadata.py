import json
import sqlite3
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.context import RequestContext, get_request_context
from app.security.rbac import RBACService
from app.services.audit import AuditService

router = APIRouter(prefix="/api/metadata", tags=["Metadata Studio"])

class ObjectDefinitionPayload(BaseModel):
    object_type: str
    label: str
    description: Optional[str] = ""
    schema_definition: List[Dict[str, Any]]
    validation_rules: Optional[List[Dict[str, Any]]] = []
    change_reason: str = Field(..., min_length=10, description="Mandatory administrative reason for change")

@router.get("/objects")
def list_metadata_objects(
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT object_type, label, description, version, updated_at
        FROM metadata_objects
        WHERE tenant_id = ?
        ORDER BY label;
    """, (ctx.tenant_id,))
    rows = cursor.fetchall()
    results = []
    for r in rows:
        perms = RBACService.get_permissions(db, ctx.tenant_id, r["object_type"], ctx.actor_role)
        if perms["can_read"]:
            results.append({
                "object_type": r["object_type"],
                "label": r["label"],
                "description": r["description"],
                "version": r["version"],
                "updated_at": r["updated_at"],
                "can_create": perms["can_create"]
            })
    return results

@router.get("/objects/{object_type}")
def get_metadata_object(
    object_type: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT object_type, label, description, schema_definition, validation_rules, version
        FROM metadata_objects
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    obj_row = cursor.fetchone()
    if not obj_row:
        raise HTTPException(status_code=404, detail=f"Object '{object_type}' not found in tenant '{ctx.tenant_id}'")

    perms = RBACService.get_permissions(db, ctx.tenant_id, object_type, ctx.actor_role)
    if not perms["can_read"]:
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="METADATA_READ", outcome="DENIED",
            object_type=object_type, reason="Persona does not have read permissions for this object"
        )
        raise HTTPException(status_code=403, detail="Access denied for object metadata")

    # Fetch lifecycle
    cursor.execute("""
        SELECT initial_state, states, transitions
        FROM metadata_lifecycles
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    lc_row = cursor.fetchone()

    schema_fields = json.loads(obj_row["schema_definition"])
    # Annotate fields with persona-specific permissions for UI convenience
    annotated_fields = []
    field_perms = perms["field_permissions"]
    for f in schema_fields:
        fp = field_perms.get(f["name"], {})
        f_copy = f.copy()
        f_copy["can_read"] = fp.get("read", False)
        f_copy["can_edit"] = fp.get("edit", False)
        annotated_fields.append(f_copy)

    return {
        "tenant_id": ctx.tenant_id,
        "object_type": obj_row["object_type"],
        "label": obj_row["label"],
        "description": obj_row["description"],
        "version": obj_row["version"],
        "fields": annotated_fields,
        "validation_rules": json.loads(obj_row["validation_rules"] or "[]"),
        "permissions": perms,
        "lifecycle": {
            "initial_state": lc_row["initial_state"] if lc_row else "Draft",
            "states": json.loads(lc_row["states"]) if lc_row else [],
            "transitions": json.loads(lc_row["transitions"]) if lc_row else []
        } if lc_row else None
    }

@router.post("/objects")
def save_metadata_object(
    payload: ObjectDefinitionPayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    if ctx.actor_role != "Admin":
        AuditService.log(
            db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
            action="METADATA_MUTATION", outcome="DENIED",
            object_type=payload.object_type, reason="Only Admins may configure metadata"
        )
        raise HTTPException(status_code=403, detail="Admin role required for metadata configuration")

    # 1. Destructive Wipeout Prevention
    if not payload.schema_definition or len(payload.schema_definition) < 1:
        raise HTTPException(
            status_code=422,
            detail="An object schema must contain at least one field. Removing all fields is blocked."
        )

    cursor = db.cursor()
    # Check if object exists
    cursor.execute("""
        SELECT schema_definition, version FROM metadata_objects
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, payload.object_type))
    existing = cursor.fetchone()

    new_field_names = {f["name"] for f in payload.schema_definition}

    if existing:
        old_fields = json.loads(existing["schema_definition"])
        old_field_names = {f["name"] for f in old_fields}
        removed_fields = old_field_names - new_field_names

        # 2. Dependency Check: Cannot delete fields referenced in lifecycle or rules
        if removed_fields:
            cursor.execute("""
                SELECT transitions FROM metadata_lifecycles
                WHERE tenant_id = ? AND object_type = ?;
            """, (ctx.tenant_id, payload.object_type))
            lc_row = cursor.fetchone()
            if lc_row:
                transitions_str = lc_row["transitions"]
                for rf in removed_fields:
                    if rf in transitions_str:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Cannot delete field '{rf}': it is referenced in active lifecycle transition guards."
                        )

        new_version = existing["version"] + 1
        cursor.execute("""
            UPDATE metadata_objects
            SET label = ?, description = ?, schema_definition = ?,
                validation_rules = ?, version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND object_type = ?;
        """, (
            payload.label, payload.description,
            json.dumps(payload.schema_definition),
            json.dumps(payload.validation_rules),
            new_version,
            ctx.tenant_id, payload.object_type
        ))
    else:
        new_version = 1
        cursor.execute("""
            INSERT INTO metadata_objects (
                id, tenant_id, object_type, label, description,
                schema_definition, validation_rules, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1);
        """, (
            f"{ctx.tenant_id}_{payload.object_type}", ctx.tenant_id,
            payload.object_type, payload.label, payload.description,
            json.dumps(payload.schema_definition),
            json.dumps(payload.validation_rules)
        ))

    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="METADATA_UPDATE", outcome="SUCCESS",
        object_type=payload.object_type,
        reason=payload.change_reason
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "object_type": payload.object_type,
        "version": new_version,
        "change_reason": payload.change_reason
    }

class LifecyclePayload(BaseModel):
    object_type: str
    initial_state: str
    states: List[str]
    transitions: List[Dict[str, Any]]
    change_reason: str = Field(..., min_length=10)

@router.get("/lifecycles/{object_type}")
def get_metadata_lifecycle(
    object_type: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT initial_state, states, transitions, version
        FROM metadata_lifecycles
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"No lifecycle defined for '{object_type}'")
    return {
        "object_type": object_type,
        "initial_state": row["initial_state"],
        "states": json.loads(row["states"]),
        "transitions": json.loads(row["transitions"]),
        "version": row["version"]
    }

@router.post("/lifecycles")
def save_metadata_lifecycle(
    payload: LifecyclePayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    if ctx.actor_role != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required for lifecycle updates")

    cursor = db.cursor()
    cursor.execute("""
        SELECT version FROM metadata_lifecycles
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, payload.object_type))
    existing = cursor.fetchone()

    if existing:
        new_version = existing["version"] + 1
        cursor.execute("""
            UPDATE metadata_lifecycles
            SET initial_state = ?, states = ?, transitions = ?, version = ?, updated_at = CURRENT_TIMESTAMP
            WHERE tenant_id = ? AND object_type = ?;
        """, (
            payload.initial_state,
            json.dumps(payload.states),
            json.dumps(payload.transitions),
            new_version,
            ctx.tenant_id,
            payload.object_type
        ))
    else:
        new_version = 1
        cursor.execute("""
            INSERT INTO metadata_lifecycles (
                id, tenant_id, object_type, initial_state, states, transitions, version
            ) VALUES (?, ?, ?, ?, ?, ?, 1);
        """, (
            f"{ctx.tenant_id}_{payload.object_type}_lc",
            ctx.tenant_id,
            payload.object_type,
            payload.initial_state,
            json.dumps(payload.states),
            json.dumps(payload.transitions)
        ))

    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="LIFECYCLE_UPDATE", outcome="SUCCESS",
        object_type=payload.object_type, reason=payload.change_reason
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "object_type": payload.object_type,
        "version": new_version,
        "change_reason": payload.change_reason
    }

class PermissionRowPayload(BaseModel):
    role: str
    can_create: bool
    can_read: bool
    can_update: bool
    can_delete: bool
    field_permissions: Dict[str, Dict[str, bool]]
    transition_permissions: Optional[List[str]] = []
    approval_permissions: Optional[List[str]] = []

class PermissionsUpdatePayload(BaseModel):
    object_type: str
    permissions: List[PermissionRowPayload]
    change_reason: str = Field(..., min_length=10)

@router.get("/permissions/{object_type}")
def get_metadata_permissions(
    object_type: str,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    cursor = db.cursor()
    cursor.execute("""
        SELECT role, can_create, can_read, can_update, can_delete,
               field_permissions, transition_permissions, approval_permissions
        FROM metadata_permissions
        WHERE tenant_id = ? AND object_type = ?;
    """, (ctx.tenant_id, object_type))
    rows = cursor.fetchall()
    return [
        {
            "role": r["role"],
            "can_create": bool(r["can_create"]),
            "can_read": bool(r["can_read"]),
            "can_update": bool(r["can_update"]),
            "can_delete": bool(r["can_delete"]),
            "field_permissions": json.loads(r["field_permissions"]),
            "transition_permissions": json.loads(r["transition_permissions"] or "[]"),
            "approval_permissions": json.loads(r["approval_permissions"] or "[]")
        }
        for r in rows
    ]

@router.post("/permissions")
def save_metadata_permissions(
    payload: PermissionsUpdatePayload,
    ctx: RequestContext = Depends(get_request_context),
    db: sqlite3.Connection = Depends(get_db)
):
    if ctx.actor_role != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required for permissions updates")

    cursor = db.cursor()
    for p in payload.permissions:
        cursor.execute("""
            INSERT INTO metadata_permissions (
                id, tenant_id, object_type, role,
                can_create, can_read, can_update, can_delete,
                field_permissions, transition_permissions, approval_permissions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tenant_id, object_type, role) DO UPDATE SET
                can_create = excluded.can_create,
                can_read = excluded.can_read,
                can_update = excluded.can_update,
                can_delete = excluded.can_delete,
                field_permissions = excluded.field_permissions,
                transition_permissions = excluded.transition_permissions,
                approval_permissions = excluded.approval_permissions;
        """, (
            f"{ctx.tenant_id}_{payload.object_type}_{p.role}",
            ctx.tenant_id, payload.object_type, p.role,
            1 if p.can_create else 0,
            1 if p.can_read else 0,
            1 if p.can_update else 0,
            1 if p.can_delete else 0,
            json.dumps(p.field_permissions),
            json.dumps(p.transition_permissions or []),
            json.dumps(p.approval_permissions or [])
        ))

    AuditService.log(
        db, ctx.tenant_id, ctx.actor_id, ctx.actor_role,
        action="PERMISSIONS_UPDATE", outcome="SUCCESS",
        object_type=payload.object_type, reason=payload.change_reason
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "object_type": payload.object_type,
        "roles_updated": len(payload.permissions),
        "change_reason": payload.change_reason
    }
