import json
import sqlite3
from typing import Optional, Dict, Any

def compute_field_diff(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Computes exact field-level deltas:
    {"amount": {"old": 4000, "new": 5500}}
    """
    diffs = {}
    all_keys = set(old_data.keys()).union(set(new_data.keys()))
    for key in all_keys:
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        if old_val != new_val:
            diffs[key] = {"old": old_val, "new": new_val}
    return diffs

class AuditService:
    @staticmethod
    def log(
        db: sqlite3.Connection,
        tenant_id: str,
        actor_id: str,
        actor_role: str,
        action: str,
        outcome: str,
        object_type: str = "system",
        record_id: Optional[str] = None,
        reason: Optional[str] = None,
        before_state: Optional[str] = None,
        after_state: Optional[str] = None,
        field_diffs: Optional[Dict[str, Any]] = None
    ) -> int:
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO audit_log (
                tenant_id, actor_id, actor_role, action, object_type,
                record_id, outcome, reason, before_state, after_state,
                field_diffs
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tenant_id,
            actor_id,
            actor_role,
            action,
            object_type,
            record_id,
            outcome,
            reason,
            before_state,
            after_state,
            json.dumps(field_diffs) if field_diffs else None
        ))
        db.commit()
        return cursor.lastrowid
