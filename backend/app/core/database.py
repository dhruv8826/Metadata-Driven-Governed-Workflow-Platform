import sqlite3
from typing import Generator
from app.core.config import DB_PATH

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_database(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # DDL Execution strictly aligned with LLD
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS tenants (
        id VARCHAR(64) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS metadata_objects (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        object_type VARCHAR(64) NOT NULL,
        label VARCHAR(255) NOT NULL,
        description TEXT,
        schema_definition JSON NOT NULL,
        validation_rules JSON,
        version INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
        UNIQUE (tenant_id, object_type)
    );

    CREATE TABLE IF NOT EXISTS metadata_lifecycles (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        object_type VARCHAR(64) NOT NULL,
        initial_state VARCHAR(64) NOT NULL,
        states JSON NOT NULL,
        transitions JSON NOT NULL,
        version INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
        UNIQUE (tenant_id, object_type)
    );

    CREATE TABLE IF NOT EXISTS metadata_permissions (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        object_type VARCHAR(64) NOT NULL,
        role VARCHAR(64) NOT NULL,
        can_create BOOLEAN DEFAULT 0,
        can_read BOOLEAN DEFAULT 0,
        can_update BOOLEAN DEFAULT 0,
        can_delete BOOLEAN DEFAULT 0,
        field_permissions JSON NOT NULL,
        transition_permissions JSON NOT NULL,
        approval_permissions JSON NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
        UNIQUE (tenant_id, object_type, role)
    );

    CREATE TABLE IF NOT EXISTS records (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        object_type VARCHAR(64) NOT NULL,
        state VARCHAR(64) NOT NULL,
        version INTEGER DEFAULT 1,
        created_by VARCHAR(64) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_by VARCHAR(64) NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data JSON NOT NULL,
        is_deleted BOOLEAN DEFAULT 0,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_records_lookup ON records (tenant_id, object_type, state);
    CREATE INDEX IF NOT EXISTS idx_records_deleted ON records (tenant_id, is_deleted);

    CREATE TABLE IF NOT EXISTS record_versions (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        record_id VARCHAR(64) NOT NULL,
        version INTEGER NOT NULL,
        state VARCHAR(64) NOT NULL,
        data JSON NOT NULL,
        changed_by VARCHAR(64) NOT NULL,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE,
        UNIQUE (record_id, version)
    );

    CREATE TABLE IF NOT EXISTS approval_requests (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        record_id VARCHAR(64) NOT NULL,
        transition_name VARCHAR(64) NOT NULL,
        target_state VARCHAR(64) NOT NULL,
        requester_id VARCHAR(64) NOT NULL,
        required_role VARCHAR(64) NOT NULL,
        status VARCHAR(32) DEFAULT 'PENDING',
        decision_by VARCHAR(64),
        decision_role VARCHAR(64),
        decision_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        decided_at TIMESTAMP,
        FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_approvals_pending ON approval_requests (tenant_id, record_id, status);

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id VARCHAR(64) NOT NULL,
        actor_id VARCHAR(64) NOT NULL,
        actor_role VARCHAR(64) NOT NULL,
        action VARCHAR(64) NOT NULL,
        object_type VARCHAR(64) NOT NULL,
        record_id VARCHAR(64),
        outcome VARCHAR(32) NOT NULL,
        reason TEXT,
        before_state VARCHAR(64),
        after_state VARCHAR(64),
        field_diffs JSON,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_audit_lookup ON audit_log (tenant_id, object_type, record_id);
    CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log (tenant_id, actor_id);

    CREATE TABLE IF NOT EXISTS dashboards (
        id VARCHAR(64) PRIMARY KEY,
        tenant_id VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        widgets JSON NOT NULL,
        FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
