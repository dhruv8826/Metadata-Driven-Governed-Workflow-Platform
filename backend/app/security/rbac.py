import json
import sqlite3
from typing import Dict, Any, List, Optional

class RBACService:
    @staticmethod
    def get_permissions(
        db: sqlite3.Connection,
        tenant_id: str,
        object_type: str,
        role: str
    ) -> Dict[str, Any]:
        """
        Retrieves permission matrix for (tenant, object_type, role).
        If role is Admin, full permissions are synthesized based on object fields.
        """
        cursor = db.cursor()
        cursor.execute("""
            SELECT can_create, can_read, can_update, can_delete,
                   field_permissions, transition_permissions, approval_permissions
            FROM metadata_permissions
            WHERE tenant_id = ? AND object_type = ? AND role = ?;
        """, (tenant_id, object_type, role))
        row = cursor.fetchone()

        if row:
            return {
                "can_create": bool(row["can_create"]),
                "can_read": bool(row["can_read"]),
                "can_update": bool(row["can_update"]),
                "can_delete": bool(row["can_delete"]),
                "field_permissions": json.loads(row["field_permissions"]),
                "transition_permissions": json.loads(row["transition_permissions"]),
                "approval_permissions": json.loads(row["approval_permissions"])
            }

        # If role is Admin and no explicit row was configured, grant full privileges
        if role == "Admin":
            cursor.execute("""
                SELECT schema_definition FROM metadata_objects
                WHERE tenant_id = ? AND object_type = ?;
            """, (tenant_id, object_type))
            obj_row = cursor.fetchone()
            field_perms = {}
            if obj_row:
                fields = json.loads(obj_row["schema_definition"])
                for f in fields:
                    field_perms[f["name"]] = {"read": True, "edit": True}

            return {
                "can_create": True,
                "can_read": True,
                "can_update": True,
                "can_delete": True,
                "field_permissions": field_perms,
                "transition_permissions": ["*"],
                "approval_permissions": ["*"]
            }

        # Default: no access
        return {
            "can_create": False,
            "can_read": False,
            "can_update": False,
            "can_delete": False,
            "field_permissions": {},
            "transition_permissions": [],
            "approval_permissions": []
        }

    @staticmethod
    def can_perform(
        db: sqlite3.Connection,
        tenant_id: str,
        object_type: str,
        role: str,
        action: str  # "create", "read", "update", "delete"
    ) -> bool:
        perms = RBACService.get_permissions(db, tenant_id, object_type, role)
        return perms.get(f"can_{action}", False)
