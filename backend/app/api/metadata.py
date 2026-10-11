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
