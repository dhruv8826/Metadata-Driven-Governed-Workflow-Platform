import json
import uuid
from pathlib import Path
from app.core.database import get_connection, init_database
from app.core.config import DB_PATH

SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"

def load_seed_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def seed_database(db_path: str = DB_PATH):
    print(f"Initializing database schema at: {db_path}")
    init_database(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    seed_files = [
        SEEDS_DIR / "procurement.json",
        SEEDS_DIR / "facilities.json"
    ]

    for seed_path in seed_files:
        if not seed_path.exists():
            print(f"Warning: Seed file not found at {seed_path}")
            continue

        data = load_seed_file(seed_path)
        tenant = data["tenant"]
        tenant_id = tenant["id"]
        print(f"Seeding tenant: {tenant['name']} ({tenant_id})")

        # 1. Insert Tenant
        cursor.execute("""
            INSERT INTO tenants (id, name, description)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description;
        """, (tenant_id, tenant["name"], tenant.get("description", "")))

        # 2. Insert Metadata Objects
        for obj in data.get("objects", []):
            obj_id = f"{tenant_id}_{obj['object_type']}"
            cursor.execute("""
                INSERT INTO metadata_objects (id, tenant_id, object_type, label, description, schema_definition, validation_rules, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(tenant_id, object_type) DO UPDATE SET
                    label = excluded.label,
                    description = excluded.description,
                    schema_definition = excluded.schema_definition,
                    validation_rules = excluded.validation_rules,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                obj_id,
                tenant_id,
                obj["object_type"],
                obj["label"],
                obj.get("description", ""),
                json.dumps(obj.get("schema_definition", [])),
                json.dumps(obj.get("validation_rules", []))
            ))

        # 3. Insert Lifecycles
        for lc in data.get("lifecycles", []):
            lc_id = f"{tenant_id}_{lc['object_type']}_lifecycle"
            cursor.execute("""
                INSERT INTO metadata_lifecycles (id, tenant_id, object_type, initial_state, states, transitions, version)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(tenant_id, object_type) DO UPDATE SET
                    initial_state = excluded.initial_state,
                    states = excluded.states,
                    transitions = excluded.transitions,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                lc_id,
                tenant_id,
                lc["object_type"],
                lc["initial_state"],
                json.dumps(lc.get("states", [])),
                json.dumps(lc.get("transitions", []))
            ))

        # 4. Insert Permissions Matrix
        for perm in data.get("permissions", []):
            perm_id = f"{tenant_id}_{perm['object_type']}_{perm['role']}"
            cursor.execute("""
                INSERT INTO metadata_permissions (id, tenant_id, object_type, role, can_create, can_read, can_update, can_delete, field_permissions, transition_permissions, approval_permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, object_type, role) DO UPDATE SET
                    can_create = excluded.can_create,
                    can_read = excluded.can_read,
                    can_update = excluded.can_update,
                    can_delete = excluded.can_delete,
                    field_permissions = excluded.field_permissions,
                    transition_permissions = excluded.transition_permissions,
                    approval_permissions = excluded.approval_permissions;
            """, (
                perm_id,
                tenant_id,
                perm["object_type"],
                perm["role"],
                perm.get("can_create", False),
                perm.get("can_read", False),
                perm.get("can_update", False),
                perm.get("can_delete", False),
                json.dumps(perm.get("field_permissions", {})),
                json.dumps(perm.get("transition_permissions", [])),
                json.dumps(perm.get("approval_permissions", []))
            ))

        # 5. Insert Dashboards
        for dash in data.get("dashboards", []):
            cursor.execute("""
                INSERT INTO dashboards (id, tenant_id, title, widgets)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    widgets = excluded.widgets;
            """, (
                dash["id"],
                tenant_id,
                dash["title"],
                json.dumps(dash.get("widgets", []))
            ))

        # 6. Insert Initial Sample Records
        for rec in data.get("records", []):
            cursor.execute("SELECT id FROM records WHERE id = ? AND tenant_id = ?;", (rec["id"], tenant_id))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO records (id, tenant_id, object_type, state, version, created_by, updated_by, data, is_deleted)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, 0);
                """, (
                    rec["id"],
                    tenant_id,
                    rec["object_type"],
                    rec["state"],
                    rec.get("created_by", "system"),
                    rec.get("created_by", "system"),
                    json.dumps(rec.get("data", {}))
                ))

                # Insert Initial Version
                cursor.execute("""
                    INSERT INTO record_versions (id, tenant_id, record_id, version, state, data, changed_by)
                    VALUES (?, ?, ?, 1, ?, ?, ?);
                """, (
                    str(uuid.uuid4()),
                    tenant_id,
                    rec["id"],
                    rec["state"],
                    json.dumps(rec.get("data", {})),
                    rec.get("created_by", "system")
                ))

                # Audit Log Entry for Seed Record Creation
                cursor.execute("""
                    INSERT INTO audit_log (tenant_id, actor_id, actor_role, action, object_type, record_id, outcome, reason, after_state, field_diffs)
                    VALUES (?, ?, ?, 'CREATE', ?, ?, 'SUCCESS', 'Initial domain seed', ?, ?);
                """, (
                    tenant_id,
                    rec.get("created_by", "system"),
                    "System",
                    rec["object_type"],
                    rec["id"],
                    rec["state"],
                    json.dumps({k: {"old": None, "new": v} for k, v in rec.get("data", {}).items()})
                ))

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
