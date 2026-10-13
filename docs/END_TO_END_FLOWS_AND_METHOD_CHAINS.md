# End-to-End Flows, Method Chains & UI-to-API Architecture

This document provides a comprehensive, diagram-driven reference explaining:
1. **Backend Method Chains**: How methods invoke one another across classes and modules for every core end-to-end operation.
2. **UI Component Encapsulation & Flow**: How frontend components nest, encapsulate state, and trigger reactive updates for every view and page.
3. **UI-to-API Mapping Matrix**: The exact linkage between user interactions, client services, HTTP routes, backend services, and database persistence.

---

## Table of Contents
1. [System Interaction Topology](#1-system-interaction-topology)
2. [Backend Method Chains Across Classes](#2-backend-method-chains-across-classes)
   - [2.1 Flow 1: Record Creation Flow](#21-flow-1-record-creation-flow)
   - [2.2 Flow 2: Record Read & Detail Inspection Flow](#22-flow-2-record-read--detail-inspection-flow)
   - [2.3 Flow 3: Record Update & Delta Computation Flow](#23-flow-3-record-update--delta-computation-flow)
   - [2.4 Flow 4: Lifecycle State Transition Flow](#24-flow-4-lifecycle-state-transition-flow)
   - [2.5 Flow 5: Atomic Approval Decision Flow](#25-flow-5-atomic-approval-decision-flow)
   - [2.6 Flow 6: Anti-Leakage Analytics Metric Flow](#26-flow-6-anti-leakage-analytics-metric-flow)
   - [2.7 Flow 7: Metadata Administration Mutation Flow](#27-flow-7-metadata-administration-mutation-flow)
   - [2.8 Flow 8: Database Bootstrapping & Seed Flow](#28-flow-8-database-bootstrapping--seed-flow)
3. [UI Component Encapsulation & View Flows](#3-ui-component-encapsulation--view-flows)
   - [3.1 Component Encapsulation Hierarchy](#31-component-encapsulation-hierarchy)
   - [3.2 Context Switcher & Shell Flow (`ContextSwitcher` $\leftrightarrow$ `App`)](#32-context-switcher--shell-flow-contextswitcher--app)
   - [3.3 Records Workspace Flow (`DynamicTable` $\leftrightarrow$ `RecordDetail` $\leftrightarrow$ `DynamicForm`)](#33-records-workspace-flow-dynamictable--recorddetail--dynamicform)
   - [3.4 Approvals Governance Inbox Flow (`ApprovalsView`)](#34-approvals-governance-inbox-flow-approvalsview)
   - [3.5 Analytics & KPI Dashboard Flow (`DashboardView`)](#35-analytics--kpi-dashboard-flow-dashboardview)
   - [3.6 Compliance & Forensics Audit Explorer Flow (`AuditView`)](#36-compliance--forensics-audit-explorer-flow-auditview)
   - [3.7 Visual Metadata Administration Studio Flow (`AdminStudio`)](#37-visual-metadata-administration-studio-flow-adminstudio)
4. [Master UI-to-API Mapping Matrix](#4-master-ui-to-api-mapping-matrix)
5. [End-to-End User Journey Sequence Diagrams](#5-end-to-end-user-journey-sequence-diagrams)

---

## 1. System Interaction Topology

```mermaid
graph TB
    subgraph ClientLayer["Frontend Client (React + Vite)"]
        UI_Event["User Action (Click, Submit, Switch)"]
        UI_Comp["UI Component (Form, Table, Detail, Studio)"]
        API_Client["services/api.js (fetch + getHeaders)"]
    end

    subgraph GatewayLayer["FastAPI Gateway & Context"]
        FastAPI_Router["app/api/*.py Routers"]
        Context_Factory["get_request_context (app/core/context.py)"]
    end

    subgraph GovernanceLayer["Security & Governance Subsystem"]
        RBAC["RBACService.get_permissions (app/security/rbac.py)"]
        Projector["FieldProjector (app/security/projection.py)"]
    end

    subgraph WorkflowLayer["Workflow & State Engine"]
        WF_Engine["WorkflowEngine (app/workflow/engine.py)"]
        Rule_AST["RuleEvaluator (app/workflow/rules.py)"]
    end

    subgraph ServiceLayer["Services & Auditing"]
        Audit_Service["AuditService.log (app/services/audit.py)"]
        Diff_Engine["compute_field_diff (app/services/audit.py)"]
    end

    subgraph DatabaseLayer["Persistence Store (SQLite WAL)"]
        DB[(platform.db)]
    end

    UI_Event --> UI_Comp
    UI_Comp --> API_Client
    API_Client -->|HTTP + Custom Headers| FastAPI_Router
    FastAPI_Router --> Context_Factory
    Context_Factory --> DB
    FastAPI_Router --> RBAC
    RBAC --> DB
    FastAPI_Router --> Projector
    FastAPI_Router --> WF_Engine
    WF_Engine --> Rule_AST
    WF_Engine --> DB
    FastAPI_Router --> Diff_Engine
    FastAPI_Router --> Audit_Service
    WF_Engine --> Audit_Service
    Audit_Service --> DB
```

---

## 2. Backend Method Chains Across Classes

### 2.1 Flow 1: Record Creation Flow
Triggered by: `POST /api/records/{object_type}`

```mermaid
sequenceDiagram
    autonumber
    actor Client as HTTP Client
    participant RecordsAPI as app.api.records.create_record
    participant Context as app.core.context.get_request_context
    participant RBAC as app.security.rbac.RBACService
    participant Projector as app.security.projection.FieldProjector
    participant Rules as app.workflow.rules.RuleEvaluator
    participant DB as SQLite DB
    participant Audit as app.services.audit.AuditService

    Client->>RecordsAPI: POST /api/records/purchase_request { data: {...} }
    RecordsAPI->>Context: get_request_context(x_tenant_id, x_persona_role, x_persona_id, db)
    Context->>DB: SELECT id FROM tenants WHERE id = ?
    Context-->>RecordsAPI: RequestContext(tenant_id, actor_id, actor_role)

    RecordsAPI->>RBAC: get_permissions(db, tenant_id, object_type, actor_role)
    RBAC->>DB: SELECT permissions FROM metadata_permissions
    RBAC-->>RecordsAPI: permissions {can_create, can_read, field_permissions, ...}

    alt can_create is False
        RecordsAPI->>Audit: log(action='CREATE', outcome='DENIED', reason='Persona cannot create')
        Audit->>DB: INSERT INTO audit_log
        RecordsAPI-->>Client: 403 Forbidden
    end

    RecordsAPI->>DB: SELECT schema_definition, validation_rules FROM metadata_objects
    DB-->>RecordsAPI: schema_fields, validation_rules

    RecordsAPI->>Projector: validate_and_filter_write(payload.data, field_perms)
    Projector-->>RecordsAPI: (sanitized_data, forbidden_fields)

    alt forbidden_fields is not empty
        RecordsAPI->>Audit: log(action='CREATE', outcome='DENIED', reason='Forbidden fields')
        Audit->>DB: INSERT INTO audit_log
        RecordsAPI-->>Client: 403 Forbidden
    end

    loop For each schema field
        opt field is reference and has value
            RecordsAPI->>DB: SELECT 1 FROM records WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0
            Note over RecordsAPI,DB: Validates reference belongs to SAME tenant
        end
    end

    RecordsAPI->>Rules: validate_record_rules(validation_rules, sanitized_data)
    loop For each rule
        Rules->>Rules: evaluate(rule.expression, sanitized_data)
    end
    Rules-->>RecordsAPI: rule_errors list

    alt rule_errors is not empty
        RecordsAPI->>Audit: log(action='CREATE', outcome='FAILED_VALIDATION', reason=errors)
        Audit->>DB: INSERT INTO audit_log
        RecordsAPI-->>Client: 422 Unprocessable Entity
    end

    RecordsAPI->>DB: SELECT initial_state FROM metadata_lifecycles
    DB-->>RecordsAPI: initial_state (e.g. 'Draft')

    RecordsAPI->>DB: INSERT INTO records (id, tenant_id, object_type, state='Draft', version=1, data)
    RecordsAPI->>DB: INSERT INTO record_versions (id, tenant_id, record_id, version=1, state='Draft', data)

    RecordsAPI->>Audit: log(action='CREATE', outcome='SUCCESS', after_state='Draft', field_diffs)
    Audit->>DB: INSERT INTO audit_log

    RecordsAPI->>Projector: project_read_record(created_rec, field_perms)
    Projector-->>RecordsAPI: clean_record
    RecordsAPI-->>Client: 200 OK clean_record
```

#### Method Call Sequence:
1. `app.core.context:get_request_context()` validates headers and verifies tenant.
2. `app.security.rbac:RBACService.get_permissions()` verifies `can_create`.
3. `app.security.projection:FieldProjector.validate_and_filter_write()` verifies that every submitted key has `edit: True`.
4. Tenant Foreign Key Guard checks that referenced entities exist in the same tenant.
5. `app.workflow.rules:RuleEvaluator.validate_record_rules()` calls `RuleEvaluator.evaluate()` for all cross-field rules.
6. DB insertion into `records` and `record_versions`.
7. `app.services.audit:AuditService.log()` permanently records initial field creation.
8. `app.security.projection:FieldProjector.project_read_record()` strips unreadable fields before returning payload.

---

### 2.2 Flow 2: Record Read & Detail Inspection Flow
Triggered by: `GET /api/records/{object_type}/{record_id}`

```mermaid
sequenceDiagram
    autonumber
    actor Client as HTTP Client
    participant RecordsAPI as app.api.records.get_record_detail
    participant Context as app.core.context.get_request_context
    participant RBAC as app.security.rbac.RBACService
    participant DB as SQLite DB
    participant Projector as app.security.projection.FieldProjector
    participant Audit as app.services.audit.AuditService

    Client->>RecordsAPI: GET /api/records/{object_type}/{record_id}
    RecordsAPI->>Context: get_request_context(...)
    Context-->>RecordsAPI: RequestContext

    RecordsAPI->>RBAC: get_permissions(db, tenant_id, object_type, actor_role)
    RBAC-->>RecordsAPI: permissions {can_read, field_permissions, ...}

    alt can_read is False
        RecordsAPI->>Audit: log(action='READ_RECORD', outcome='DENIED')
        RecordsAPI-->>Client: 403 Forbidden
    end

    RecordsAPI->>DB: SELECT * FROM records WHERE id = ? AND tenant_id = ? AND object_type = ? AND is_deleted = 0
    DB-->>RecordsAPI: record row

    RecordsAPI->>DB: SELECT * FROM record_versions WHERE record_id = ? AND tenant_id = ? ORDER BY version DESC
    DB-->>RecordsAPI: version_rows

    RecordsAPI->>DB: SELECT * FROM approval_requests WHERE record_id = ? AND status = 'PENDING'
    DB-->>RecordsAPI: pending_approval_row

    Note over RecordsAPI: Constructs rec_dict with data, versions, and pending_approval

    RecordsAPI->>Projector: project_read_record(rec_dict, field_permissions)
    Note over Projector: 1. Strips unreadable fields from current data<br/>2. Iterates over historical versions and strips unreadable fields from each past version!
    Projector-->>RecordsAPI: clean_record_dict

    RecordsAPI-->>Client: 200 OK clean_record_dict
```

#### Method Call Sequence:
1. `app.core.context:get_request_context()` produces tenant and persona credentials.
2. `app.security.rbac:RBACService.get_permissions()` validates `can_read`.
3. SQLite queries `records`, `record_versions`, and `approval_requests`.
4. `app.security.projection:FieldProjector.project_read_record()` executes recursive projection:
   - Strips unreadable fields from `rec_dict["data"]`.
   - Iterates through `rec_dict["versions"]` and strips unreadable fields from every snapshot `v["data"]`.

---

### 2.3 Flow 3: Record Update & Delta Computation Flow
Triggered by: `PUT /api/records/{object_type}/{record_id}`

```mermaid
sequenceDiagram
    autonumber
    actor Client as HTTP Client
    participant RecordsAPI as app.api.records.update_record
    participant RBAC as app.security.rbac.RBACService
    participant Projector as app.security.projection.FieldProjector
    participant Rules as app.workflow.rules.RuleEvaluator
    participant Diff as app.services.audit.compute_field_diff
    participant Audit as app.services.audit.AuditService
    participant DB as SQLite DB

    Client->>RecordsAPI: PUT /api/records/{type}/{id} { data: { amount: 5500 } }
    RecordsAPI->>RBAC: get_permissions(db, tenant_id, object_type, actor_role)
    RBAC-->>RecordsAPI: permissions

    alt can_update is False
        RecordsAPI->>Audit: log(action='UPDATE', outcome='DENIED')
        RecordsAPI-->>Client: 403 Forbidden
    end

    RecordsAPI->>DB: SELECT state, version, data FROM records WHERE id = ?
    DB-->>RecordsAPI: existing record

    RecordsAPI->>Projector: validate_and_filter_write(payload.data, field_perms)
    Projector-->>RecordsAPI: (sanitized_delta, forbidden_fields)

    alt forbidden_fields is not empty
        RecordsAPI->>Audit: log(action='UPDATE', outcome='DENIED', reason='Forbidden fields')
        RecordsAPI-->>Client: 403 Forbidden
    end

    Note over RecordsAPI: merged_data = old_data.copy(); merged_data.update(sanitized_delta)

    RecordsAPI->>Rules: validate_record_rules(validation_rules, merged_data)
    Rules-->>RecordsAPI: rule_errors

    alt rule_errors is not empty
        RecordsAPI->>Audit: log(action='UPDATE', outcome='FAILED_VALIDATION')
        RecordsAPI-->>Client: 422 Unprocessable Entity
    end

    RecordsAPI->>Diff: compute_field_diff(old_data, merged_data)
    Note over Diff: Identifies deltas: { amount: { old: 4000, new: 5500 } }
    Diff-->>RecordsAPI: field_diffs

    RecordsAPI->>DB: UPDATE records SET data = ?, version = version + 1 WHERE id = ?
    RecordsAPI->>DB: INSERT INTO record_versions (id, version, state, data, changed_by)

    RecordsAPI->>Audit: log(action='UPDATE', outcome='SUCCESS', field_diffs=field_diffs)
    Audit->>DB: INSERT INTO audit_log

    RecordsAPI->>Projector: project_read_record(updated_rec, field_perms)
    Projector-->>RecordsAPI: clean_record
    RecordsAPI-->>Client: 200 OK clean_record
```

#### Method Call Sequence:
1. `app.security.rbac:RBACService.get_permissions()` checks `can_update`.
2. `app.security.projection:FieldProjector.validate_and_filter_write()` verifies that only editable fields are being altered.
3. Merged data is validated against foreign key references and `RuleEvaluator.validate_record_rules()`.
4. `app.services.audit:compute_field_diff(old_data, merged_data)` calculates exact key-value deltas.
5. `records` is updated and a new snapshot is written to `record_versions`.
6. `app.services.audit:AuditService.log()` captures the change with the computed deltas.
7. `app.security.projection:FieldProjector.project_read_record()` projects the response.

---

### 2.4 Flow 4: Lifecycle State Transition Flow
Triggered by: `POST /api/records/{record_id}/transitions`

```mermaid
sequenceDiagram
    autonumber
    actor Client as HTTP Client
    participant TransAPI as app.api.transitions.trigger_transition
    participant Engine as app.workflow.engine.WorkflowEngine
    participant Rules as app.workflow.rules.RuleEvaluator
    participant DB as SQLite DB
    participant Audit as app.services.audit.AuditService

    Client->>TransAPI: POST /api/records/{id}/transitions { transition_name: 'submit' }
    TransAPI->>Engine: execute_transition(db, tenant_id, record_id, transition_name, actor_id, actor_role)

    Engine->>DB: SELECT id, object_type, state, version, created_by, data FROM records WHERE id = ?
    DB-->>Engine: record

    Engine->>DB: SELECT initial_state, states, transitions FROM metadata_lifecycles WHERE object_type = ?
    DB-->>Engine: lifecycle

    Note over Engine: 1. Validate matched_transition.from_state == record.current_state<br/>2. Validate actor_role in matched_transition.allowed_roles

    opt transition specifies guard
        Engine->>Rules: evaluate(matched_transition.guard, record_data)
        alt guard fails
            Engine->>Audit: log(action='TRANSITION', outcome='GUARD_FAILED')
            Engine-->>Client: 400 Bad Request (Guard check failed)
        end
    end

    opt transition specifies skip_approval_rule
        Engine->>Rules: evaluate(skip_approval_rule, record_data)
        Note over Engine: If true (e.g. priority == 'Emergency'): requires_approval = False
    end

    alt requires_approval is True
        opt dynamic approval_routing rule exists
            Engine->>Rules: evaluate(approval_routing.rule.condition, record_data)
            Note over Engine: Selects role_if_true (Director) or role_if_false (Manager)
        end

        Engine->>DB: INSERT INTO approval_requests (status='PENDING', target_state, requester_id, required_role)
        Engine->>DB: UPDATE records SET state = target_state, version = version + 1
        Engine->>DB: INSERT INTO record_versions (snapshot)
        Engine->>Audit: log(action='TRANSITION_REQUEST_APPROVAL', outcome='PENDING_APPROVAL')
        Engine-->>Client: 200 OK { requires_approval: true, pending_approval: {...} }

    else Direct Transition (No Approval)
        Engine->>DB: UPDATE records SET state = target_state, version = version + 1
        Engine->>DB: INSERT INTO record_versions (snapshot)
        Engine->>Audit: log(action='TRANSITION', outcome='SUCCESS')
        Engine-->>Client: 200 OK { requires_approval: false, current_state: target_state }
    end
```

#### Method Call Sequence:
1. `app.workflow.engine:WorkflowEngine.execute_transition()` loads the record and lifecycle state machine.
2. Validates `from_state == current_state` and checks actor role authorization.
3. `app.workflow.rules:RuleEvaluator.evaluate()` evaluates any `guard` expression.
4. `RuleEvaluator.evaluate()` checks `skip_approval_rule`.
5. If approval is required:
   - `RuleEvaluator.evaluate()` executes `approval_routing.rule.condition`.
   - An entry is inserted into `approval_requests`.
   - The record advances state and a new version is created in `record_versions`.
   - `AuditService.log()` captures the pending approval event.

---

### 2.5 Flow 5: Atomic Approval Decision Flow
Triggered by: `POST /api/approvals/{approval_id}/decision`

```mermaid
sequenceDiagram
    autonumber
    actor Approver as Approver / Manager
    participant ApprAPI as app.api.approvals.submit_approval_decision
    participant Engine as app.workflow.engine.WorkflowEngine
    participant DB as SQLite DB
    participant Audit as app.services.audit.AuditService

    Approver->>ApprAPI: POST /api/approvals/{id}/decision { decision: 'APPROVE', reason: 'Verified' }
    ApprAPI->>Engine: execute_approval_decision(db, tenant_id, approval_id, actor_id, actor_role, decision, reason)

    Engine->>DB: BEGIN IMMEDIATE; (Acquires exclusive write lock)
    Engine->>DB: SELECT * FROM approval_requests WHERE id = ? AND tenant_id = ?
    DB-->>Engine: approval

    alt status != 'PENDING' (Race Condition)
        Engine->>Audit: log(action='APPROVAL_DECISION', outcome='CONFLICT')
        Engine->>DB: ROLLBACK;
        Engine-->>Approver: 409 Conflict (Request already processed)
    end

    alt actor_id == requester_id (Self-Approval Attack)
        Engine->>Audit: log(action='SELF_APPROVAL_ATTEMPT', outcome='DENIED')
        Engine->>DB: ROLLBACK;
        Engine-->>Approver: 403 Forbidden (Self-approval is strictly forbidden)
    end

    alt actor_role != required_role and actor_role != 'Admin'
        Engine->>Audit: log(action='APPROVAL_DECISION', outcome='DENIED')
        Engine->>DB: ROLLBACK;
        Engine-->>Approver: 403 Forbidden (Unauthorized approver role)
    end

    Engine->>DB: UPDATE approval_requests SET status = 'APPROVED', decision_by = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?
    Engine->>DB: UPDATE records SET state = next_record_state, version = version + 1 WHERE id = ?
    Engine->>DB: INSERT INTO record_versions (snapshot)

    Engine->>Audit: log(action='APPROVAL_APPROVED', outcome='SUCCESS')
    Engine->>DB: COMMIT;

    Engine-->>Approver: 200 OK { approval_id, status: 'APPROVED', new_record_state }
```

#### Method Call Sequence:
1. `app.workflow.engine:WorkflowEngine.execute_approval_decision()` opens a `BEGIN IMMEDIATE;` atomic transaction.
2. Checks for race conditions (`status == 'PENDING'`).
3. Blocks self-approval (`actor_id != requester_id`).
4. Verifies role eligibility (`actor_role == required_role` or `Admin`).
5. Updates `approval_requests`, updates `records`, and snapshots `record_versions`.
6. `app.services.audit:AuditService.log()` captures the decision with justification.
7. Commits the transaction.

---

### 2.6 Flow 6: Anti-Leakage Analytics Metric Flow
Triggered by: `GET /api/dashboards/{dashboard_id}`

```mermaid
sequenceDiagram
    autonumber
    actor Viewer as Client
    participant DashAPI as app.api.dashboards.get_dashboard_metrics
    participant RBAC as app.security.rbac.RBACService
    participant Projector as app.security.projection.FieldProjector
    participant DB as SQLite DB
    participant Audit as app.services.audit.AuditService

    Viewer->>DashAPI: GET /api/dashboards/{dashboard_id}
    DashAPI->>DB: SELECT widgets FROM dashboards WHERE id = ? AND tenant_id = ?
    DB-->>DashAPI: widgets_config

    loop For each widget in widgets_config
        DashAPI->>RBAC: get_permissions(db, tenant_id, widget.object_type, actor_role)
        RBAC-->>DashAPI: perms

        alt perms.can_read is False
            Note over DashAPI: Append widget with status='RESTRICTED'
        else perms.can_read is True
            DashAPI->>Projector: can_read_fields([metric_field, group_by_field], perms.field_permissions)
            
            alt Participating fields contain unreadable field
                DashAPI->>Audit: log(action='DASHBOARD_METRIC_ACCESS', outcome='DENIED', reason='Hidden fields')
                Note over DashAPI: Append widget with status='RESTRICTED'<br/>Zero totals or metrics calculated!
            else All participating fields readable
                DashAPI->>DB: SELECT id, state, data FROM records WHERE object_type = ?
                DB-->>DashAPI: records
                Note over DashAPI: Computes sum, count, avg, or group-by distributions
                Note over DashAPI: Append widget with status='AVAILABLE'
            end
        end
    end

    DashAPI-->>Viewer: 200 OK { id, title, widgets: [ ... ] }
```

#### Method Call Sequence:
1. `app.security.rbac:RBACService.get_permissions()` verifies object access.
2. `app.security.projection:FieldProjector.can_read_fields()` verifies all fields in `metric.field` and `group_by`.
3. If any field is hidden, `AuditService.log()` logs the denied access and returns `status: "RESTRICTED"` without querying aggregates.
4. If readable, queries records and computes authorized aggregations.

---

### 2.7 Flow 7: Metadata Administration Mutation Flow
Triggered by: `POST /api/metadata/objects`

```mermaid
sequenceDiagram
    autonumber
    actor Admin as System Admin
    participant MetaAPI as app.api.metadata.save_metadata_object
    participant DB as SQLite DB
    participant Audit as app.services.audit.AuditService

    Admin->>MetaAPI: POST /api/metadata/objects { payload }
    
    alt actor_role != 'Admin'
        MetaAPI->>Audit: log(action='METADATA_MUTATION', outcome='DENIED')
        MetaAPI-->>Admin: 403 Forbidden
    end

    alt len(schema_definition) < 1 (Wipeout Guard)
        MetaAPI-->>Admin: 422 Unprocessable Entity (At least 1 field required)
    end

    MetaAPI->>DB: SELECT schema_definition, version FROM metadata_objects WHERE object_type = ?
    DB-->>MetaAPI: existing schema

    opt If existing schema has deleted fields
        MetaAPI->>DB: SELECT transitions FROM metadata_lifecycles WHERE object_type = ?
        DB-->>MetaAPI: active transitions
        Note over MetaAPI: Checks if any deleted field is referenced in transition guards!<br/>If found: abort with 422 Unprocessable Entity
    end

    MetaAPI->>DB: INSERT / UPDATE metadata_objects (version = version + 1)
    MetaAPI->>Audit: log(action='METADATA_UPDATE', outcome='SUCCESS', reason=payload.change_reason)
    MetaAPI->>DB: COMMIT;

    MetaAPI-->>Admin: 200 OK { status: 'SUCCESS', version }
```

---

### 2.8 Flow 8: Database Bootstrapping & Seed Flow
Triggered by: Server startup (`lifespan`) or standalone script run (`seed_db.py`)

```mermaid
sequenceDiagram
    autonumber
    participant Main as app.main.lifespan / seed_db.py
    participant DBEngine as app.core.database.init_database
    participant SeedLoader as app.scripts.seed_db.load_seed_file
    participant SeedDB as app.scripts.seed_db.seed_database
    participant DB as SQLite DB

    Main->>DBEngine: init_database(DB_PATH)
    DBEngine->>DB: executescript(DDL: tenants, metadata_objects, lifecycles, permissions, records, record_versions, approval_requests, audit_log, dashboards)
    DBEngine-->>Main: Schema Ready

    Main->>SeedDB: seed_database(DB_PATH)
    loop For each seed file ('procurement.json', 'facilities.json')
        SeedDB->>SeedLoader: load_seed_file(path)
        SeedLoader-->>SeedDB: data JSON
        SeedDB->>DB: INSERT INTO tenants (id, name, description) ON CONFLICT DO UPDATE
        SeedDB->>DB: INSERT INTO metadata_objects (...) ON CONFLICT DO UPDATE
        SeedDB->>DB: INSERT INTO metadata_lifecycles (...) ON CONFLICT DO UPDATE
        SeedDB->>DB: INSERT INTO metadata_permissions (...) ON CONFLICT DO UPDATE
        SeedDB->>DB: INSERT INTO dashboards (...) ON CONFLICT DO UPDATE
        
        loop For each initial record
            SeedDB->>DB: INSERT INTO records (id, state, version=1, data)
            SeedDB->>DB: INSERT INTO record_versions (id, version=1, state, data)
            SeedDB->>DB: INSERT INTO audit_log (action='CREATE', outcome='SUCCESS', reason='Initial seed')
        end
    end
    SeedDB->>DB: COMMIT;
    SeedDB-->>Main: Seeding Complete
```

---

## 3. UI Component Encapsulation & View Flows

### 3.1 Component Encapsulation Hierarchy

```mermaid
classDiagram
    class App {
        -objects: Array
        -selectedObjectType: String
        -selectedObjectMeta: Object
        -activeTab: String
        -viewMode: String
        -selectedRecordId: String
        -pendingApprovalsCount: Number
        +handleContextChange()
        +handleSelectObject()
        +handleSelectRecord()
        +handleCreateRecord()
    }

    class ContextSwitcher {
        -tenants: Array
        -personas: Array
        -activeTenant: String
        -activePersonaId: String
        -activeRole: String
        +handleTenantChange()
        +selectPersona()
    }

    class DynamicTable {
        -records: Array
        -searchTerm: String
        -stateFilter: String
        -sortBy: String
        -page: Number
        +onSelectRecord(id)
        +onCreateNew()
    }

    class DynamicForm {
        -formData: Object
        -referenceOptions: Object
        -submitting: Boolean
        +isFieldVisible(field)
        +handleSubmit(e)
    }

    class RecordDetail {
        -record: Object
        -isEditing: Boolean
        -approvalReason: String
        +handleTransition(name)
        +loadDetail()
    }

    class ApprovalsView {
        -approvals: Array
        -selectedApproval: Object
        -decisionReason: String
        +handleDecision(decision)
    }

    class DashboardView {
        -dashboards: Array
        -metricsData: Object
        +loadDashboards()
    }

    class AuditView {
        -logs: Array
        -filterOutcome: String
        -expandedRowId: Number
        +loadLogs()
    }

    class AdminStudio {
        -studioTab: String
        -objectDetail: Object
        -permissionsData: Array
        -changeReason: String
        +saveSchema()
        +saveLifecycle()
        +savePermissions()
    }

    App *-- ContextSwitcher : Renders in Header
    App *-- DynamicTable : Renders when tab='records' & mode='list'
    App *-- DynamicForm : Renders when tab='records' & mode='create'
    App *-- RecordDetail : Renders when tab='records' & mode='detail'
    RecordDetail *-- DynamicForm : Encapsulates for inline edit
    App *-- ApprovalsView : Renders when tab='approvals'
    App *-- DashboardView : Renders when tab='dashboard'
    App *-- AuditView : Renders when tab='audit'
    App *-- AdminStudio : Renders when tab='admin'
```

---

### 3.2 Context Switcher & Shell Flow (`ContextSwitcher` $\leftrightarrow$ `App`)

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Switcher as ContextSwitcher.jsx
    participant LocalStore as localStorage
    participant API as services/api.js
    participant AppShell as App.jsx

    User->>Switcher: Selects Tenant "facilities"
    Switcher->>LocalStore: setItem("active_tenant_id", "facilities")
    Switcher->>API: getTenantPersonas("facilities")
    API-->>Switcher: { personas: [Tom Bradley (Technician), ...] }
    Switcher->>LocalStore: setItem("active_persona_id", "tom_tech")
    Switcher->>LocalStore: setItem("active_persona_role", "Technician")
    Switcher->>AppShell: onContextChange()

    AppShell->>AppShell: setViewMode("list"); setSelectedRecordId(null)
    AppShell->>API: getMetadataObjects() (Sends X-Tenant-Id: facilities, X-Persona-Role: Technician)
    API-->>AppShell: [Asset, Maintenance Job]
    AppShell->>API: getMetadataObject("asset")
    API-->>AppShell: asset metadata definition
    AppShell->>API: getPendingApprovals()
    API-->>AppShell: pending approvals list
    AppShell->>AppShell: Re-renders sidebar with Asset & Maintenance Job tabs
```

---

### 3.3 Records Workspace Flow (`DynamicTable` $\leftrightarrow$ `RecordDetail` $\leftrightarrow$ `DynamicForm`)

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Table as DynamicTable.jsx
    participant AppShell as App.jsx
    participant Detail as RecordDetail.jsx
    participant Form as DynamicForm.jsx
    participant API as services/api.js

    Note over AppShell,Table: Mode: 'list'
    Table->>API: getRecords(objectType, { limit, offset, state, sort_by })
    API-->>Table: { items: [...], total }
    Table->>Table: Renders dynamic columns, projected fields, state badges

    User->>Table: Clicks record row
    Table->>AppShell: onSelectRecord(recordId)
    AppShell->>AppShell: setViewMode('detail'); setSelectedRecordId(recordId)

    Note over AppShell,Detail: Mode: 'detail'
    Detail->>API: getRecordDetail(objectType, recordId)
    API-->>Detail: { data, versions, pending_approval }
    Detail->>Detail: Renders field grid, pending banner, transition buttons, version timeline

    opt User Clicks "Edit Record"
        Detail->>Detail: setIsEditing(true)
        Detail->>Form: Renders DynamicForm(initialData=record.data)
        User->>Form: Modifies values and clicks "Save Changes"
        Form->>API: updateRecord(objectType, recordId, formData)
        API-->>Form: updated record
        Form->>Detail: onCancel() / loadDetail()
        Detail->>Detail: Refreshes details & version history timeline
    end

    opt User Clicks Transition Button (e.g. "Submit Request")
        Detail->>API: triggerTransition(recordId, "submit")
        API-->>Detail: { requires_approval: true, current_state: 'Submitted' }
        Detail->>Detail: Displays success notification & reloads detail
    end
```

---

### 3.4 Approvals Governance Inbox Flow (`ApprovalsView`)

```mermaid
sequenceDiagram
    autonumber
    actor Approver as Approver / Manager
    participant Inbox as ApprovalsView.jsx
    participant Modal as Decision Modal
    participant API as services/api.js

    Inbox->>API: getPendingApprovals()
    API-->>Inbox: [ { id, record_id, required_role, requester_id, can_approve } ]
    Inbox->>Inbox: Renders pending requests table

    alt Self-Approval Detected (can_approve === false)
        Inbox->>Inbox: Disables "Review Decision" button<br/>Displays "Self-Approval Blocked" pill
    else Authorized Approver (can_approve === true)
        Approver->>Inbox: Clicks "Review Decision"
        Inbox->>Modal: Opens Modal with Approval context
        Approver->>Modal: Selects "Approve", enters reason: "Budget verified"
        Approver->>Modal: Clicks "Submit Decision"
        Modal->>API: submitApprovalDecision(approvalId, "APPROVE", reason)
        API-->>Modal: { status: "APPROVED", new_record_state: "Approved" }
        Modal->>Inbox: Closes modal and re-fetches getPendingApprovals()
    end
```

---

### 3.5 Analytics & KPI Dashboard Flow (`DashboardView`)

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Dash as DashboardView.jsx
    participant API as services/api.js

    Dash->>API: getDashboards()
    API-->>Dash: [ { id: "procurement_overview", title: "..." } ]
    Dash->>API: getDashboardMetrics("procurement_overview")
    API-->>Dash: { widgets: [ kpi_widget, chart_widget, restricted_widget ] }

    loop For each widget
        alt widget.status === 'AVAILABLE'
            opt type === 'kpi'
                Dash->>Dash: Renders Metric Card with numeric value
            end
            opt type === 'chart'
                Dash->>Dash: Renders Horizontal Distribution Bar Chart
            end
            opt type === 'table'
                Dash->>Dash: Renders Compact Data Table
            end
        else widget.status === 'RESTRICTED'
            Dash->>Dash: Renders Anti-Leakage Lock Card with Restricted explanation<br/>Zero numbers or leakable data shown
        end
    end
```

---

### 3.6 Compliance & Forensics Audit Explorer Flow (`AuditView`)

```mermaid
sequenceDiagram
    autonumber
    actor Auditor as Compliance Auditor
    participant AuditUI as AuditView.jsx
    participant API as services/api.js

    Auditor->>AuditUI: Selects Filter: Outcome = "DENIED", Limit = 50
    AuditUI->>API: getAuditTrail({ outcome: "DENIED", limit: 50 })
    API-->>AuditUI: [ { id, actor_id, action, outcome: "DENIED", reason, field_diffs, timestamp } ]
    AuditUI->>AuditUI: Renders chronological compliance events table with color-coded badges

    Auditor->>AuditUI: Clicks "View Field Diffs" on an UPDATE event
    AuditUI->>AuditUI: Expands inline delta comparison:<br/>amount: 4000 -> 5500
```

---

### 3.7 Visual Metadata Administration Studio Flow (`AdminStudio`)

```mermaid
sequenceDiagram
    autonumber
    actor Admin as System Admin
    participant Studio as AdminStudio.jsx
    participant API as services/api.js

    Admin->>Studio: Opens Admin Studio
    Studio->>API: getMetadataObjects()
    API-->>Studio: objects list
    Studio->>API: getMetadataObject("purchase_request")
    API-->>Studio: object definition (fields, rules, lifecycle)
    Studio->>API: getMetadataPermissions("purchase_request")
    API-->>Studio: permissions matrix

    opt Tab: Schema Designer
        Admin->>Studio: Adds new field: 'priority' (type: select)
        Admin->>Studio: Inputs Change Reason: "Adding priority field for urgent routing"
        Admin->>Studio: Clicks "Save Schema"
        Studio->>API: saveMetadataObject(payload)
        API-->>Studio: 200 OK { version: 2 }
    end

    opt Tab: Lifecycle Modeler
        Admin->>Studio: Edits transition guard or approval condition
        Admin->>Studio: Inputs Change Reason: "Adjusted director approval threshold to 7500"
        Admin->>Studio: Clicks "Save Lifecycle"
        Studio->>API: saveMetadataLifecycle(payload)
        API-->>Studio: 200 OK { version: 2 }
    end

    opt Tab: Permissions Matrix
        Admin->>Studio: Toggles field read/edit checkboxes across roles
        Admin->>Studio: Inputs Change Reason: "Restricting cost_centre from technician role"
        Admin->>Studio: Clicks "Save Permissions"
        Studio->>API: saveMetadataPermissions(payload)
        API-->>Studio: 200 OK { roles_updated: 4 }
    end
```

---

## 4. Master UI-to-API Mapping Matrix

The table below maps every frontend interaction to its corresponding client API service method, HTTP endpoint, backend router, downstream class methods, and database tables affected:

| # | User Action / UI Trigger | Source Component | Client Method (`services/api.js`) | HTTP Route | Headers Injected | Backend Router & Handler | Downstream Class Invocations | Database Tables Affected | Result & UI State Update |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **1** | Select Tenant Dropdown | `ContextSwitcher.jsx` | `api.getTenantPersonas(id)` | `GET /api/tenants/{id}/personas` | None | `tenants.get_tenant_personas` | None (reads seed file) | None | Personas dropdown updated |
| **2** | Select Persona Dropdown | `ContextSwitcher.jsx` | `api.getMetadataObjects()` | `GET /api/metadata/objects` | `X-Tenant-Id`<br/>`X-Persona-Role`<br/>`X-Persona-Id` | `metadata.list_metadata_objects` | `RBACService.get_permissions` | `metadata_objects`<br/>`metadata_permissions` | Sidebar dynamically repopulated with authorized objects |
| **3** | Click Entity in Sidebar | `App.jsx` | `api.getMetadataObject(type)` | `GET /api/metadata/objects/{type}` | Context Headers | `metadata.get_metadata_object` | `RBACService.get_permissions` | `metadata_objects`<br/>`metadata_lifecycles` | Entity schema, fields, and permissions loaded; table opens |
| **4** | View Records Table | `DynamicTable.jsx` | `api.getRecords(type, params)` | `GET /api/records/{type}` | Context Headers | `records.list_records` | `RBACService.get_permissions`<br/>`FieldProjector.project_read_record` | `records` | Dynamic columns populated; restricted fields stripped |
| **5** | Click "New Record" Button | `DynamicTable.jsx` | `api.getRecords(refTarget)` | `GET /api/records/{refTarget}` | Context Headers | `records.list_records` | `RBACService.get_permissions`<br/>`FieldProjector.project_read_record` | `records` | Form displays editable fields and foreign key dropdown options |
| **6** | Submit Create Record Form | `DynamicForm.jsx` | `api.createRecord(type, data)` | `POST /api/records/{type}` | Context Headers | `records.create_record` | `RBACService.can_perform`<br/>`FieldProjector.validate_and_filter_write`<br/>`RuleEvaluator.validate_record_rules`<br/>`FieldProjector.project_read_record`<br/>`AuditService.log` | `records`<br/>`record_versions`<br/>`audit_log` | New record created with version 1; switches back to list view |
| **7** | Click Record Row in Table | `DynamicTable.jsx` | `api.getRecordDetail(type, id)` | `GET /api/records/{type}/{id}` | Context Headers | `records.get_record_detail` | `RBACService.get_permissions`<br/>`FieldProjector.project_read_record` | `records`<br/>`record_versions`<br/>`approval_requests` | Displays field grid, version history timeline, and transition buttons |
| **8** | Save Inline Edit Form | `RecordDetail.jsx` | `api.updateRecord(type, id, data)` | `PUT /api/records/{type}/{id}` | Context Headers | `records.update_record` | `RBACService.can_perform`<br/>`FieldProjector.validate_and_filter_write`<br/>`RuleEvaluator.validate_record_rules`<br/>`compute_field_diff`<br/>`AuditService.log` | `records`<br/>`record_versions`<br/>`audit_log` | Version incremented; field deltas appended to audit trail |
| **9** | Click Transition Action Button | `RecordDetail.jsx` | `api.triggerTransition(id, name)` | `POST /api/records/{id}/transitions` | Context Headers | `transitions.trigger_transition` | `WorkflowEngine.execute_transition`<br/>`RuleEvaluator.evaluate`<br/>`AuditService.log` | `records`<br/>`record_versions`<br/>`approval_requests`<br/>`audit_log` | State advances or pending approval banner appears |
| **10**| Click Approvals Tab in Navbar| `App.jsx` | `api.getPendingApprovals()` | `GET /api/approvals/pending` | Context Headers | `approvals.list_pending_approvals` | Queries role-matched requests | `approval_requests`<br/>`records` | Inbox displays pending requests matching user's role |
| **11**| Submit Approval / Rejection | `ApprovalsView.jsx` | `api.submitApprovalDecision(id, d, r)`| `POST /api/approvals/{id}/decision` | Context Headers | `approvals.submit_approval_decision`| `WorkflowEngine.execute_approval_decision`<br/>`BEGIN IMMEDIATE`<br/>`AuditService.log` | `approval_requests`<br/>`records`<br/>`record_versions`<br/>`audit_log` | Approval resolved; record transitions to Approved/Rejected |
| **12**| Click Analytics Tab | `App.jsx` | `api.getDashboardMetrics(id)` | `GET /api/dashboards/{id}` | Context Headers | `dashboards.get_dashboard_metrics` | `RBACService.get_permissions`<br/>`FieldProjector.can_read_fields`<br/>`AuditService.log` | `dashboards`<br/>`records`<br/>`audit_log` | KPI cards and charts render; restricted metrics display lock badge |
| **13**| Click Audit Trail Tab | `App.jsx` | `api.getAuditTrail(params)` | `GET /api/audit` | Context Headers | `audit.list_audit_trail` | Queries filtered log entries | `audit_log` | Compliance audit explorer populated with expandable diffs |
| **14**| Save Schema in Admin Studio | `AdminStudio.jsx` | `api.saveMetadataObject(payload)` | `POST /api/metadata/objects` | Context Headers | `metadata.save_metadata_object` | Destructive wipeout check<br/>Transition guard dependency check<br/>`AuditService.log` | `metadata_objects`<br/>`audit_log` | Schema updated live; version incremented |
| **15**| Save Lifecycle in Admin Studio| `AdminStudio.jsx` | `api.saveMetadataLifecycle(payload)` | `POST /api/metadata/lifecycles` | Context Headers | `metadata.save_metadata_lifecycle`| `AuditService.log` | `metadata_lifecycles`<br/>`audit_log` | FSM transitions updated live |
| **16**| Save Permissions Matrix | `AdminStudio.jsx` | `api.saveMetadataPermissions(payload)`| `POST /api/metadata/permissions` | Context Headers | `metadata.save_metadata_permissions`| `AuditService.log` | `metadata_permissions`<br/>`audit_log` | Role-based CRUD and field read/edit matrix updated live |

---

## 5. End-to-End User Journey Sequence Diagrams

### Journey A: Procurement Workflow (Alice submits $\rightarrow$ Bob approves $\rightarrow$ Dave orders)

```mermaid
sequenceDiagram
    autonumber
    actor Alice as Alice (Requester)
    actor Bob as Bob (Manager)
    actor Dave as Dave (Finance)
    participant Client as Frontend (Vite)
    participant API as FastAPI Backend
    participant Engine as WorkflowEngine
    participant DB as SQLite DB

    Alice->>Client: Fills Purchase Request (Amount: $4,500) & Submits
    Client->>API: POST /api/records/purchase_request { data: { amount: 4500, ... } }
    API->>DB: INSERT INTO records (state='Draft', version=1)
    API-->>Client: Record created (Draft)

    Alice->>Client: Clicks "Submit Request" transition button
    Client->>API: POST /api/records/{id}/transitions { transition_name: 'submit' }
    API->>Engine: execute_transition()
    Note over Engine: Evaluates approval_routing rule: amount <= 5000 -> Routes to Manager
    Engine->>DB: INSERT INTO approval_requests (status='PENDING', required_role='Manager')
    Engine->>DB: UPDATE records SET state='Submitted', version=2
    Engine-->>Client: Requires approval by Manager

    Note over Client: Persona switches to Bob Martinez (Manager)
    Bob->>Client: Opens Approvals Inbox -> Sees pending request
    Bob->>Client: Clicks "Review Decision" -> Enters "Approved" -> Submits
    Client->>API: POST /api/approvals/{appr_id}/decision { decision: 'APPROVE', reason: 'Approved' }
    API->>Engine: execute_approval_decision()
    Engine->>DB: UPDATE approval_requests SET status='APPROVED'
    Engine->>DB: UPDATE records SET state='Approved', version=3
    Engine-->>Client: Request approved

    Note over Client: Persona switches to Dave Sterling (Finance)
    Dave->>Client: Opens Record Detail -> Clicks "Place Order" transition button
    Client->>API: POST /api/records/{id}/transitions { transition_name: 'order' }
    API->>Engine: execute_transition()
    Note over Engine: Transition allowed for Finance without approval
    Engine->>DB: UPDATE records SET state='Ordered', version=4
    Engine-->>Client: State updated to 'Ordered'
```

---

### Journey B: Facilities Emergency Repair (Tom reports job $\rightarrow$ Skips approval $\rightarrow$ Executes)

```mermaid
sequenceDiagram
    autonumber
    actor Tom as Tom (Technician)
    participant Client as Frontend (Vite)
    participant API as FastAPI Backend
    participant Engine as WorkflowEngine
    participant DB as SQLite DB

    Tom->>Client: Creates Maintenance Job (Priority: 'Emergency', Estimated Cost: $3,500)
    Note over Client: DynamicForm hides 'estimated_cost' if uneditable for Technician
    Client->>API: POST /api/records/maintenance_job { data: { priority: 'Emergency', ... } }
    API->>DB: INSERT INTO records (state='Reported', version=1)
    API-->>Client: Job created in 'Reported' state

    Tom->>Client: Clicks "Schedule Maintenance" transition button
    Client->>API: POST /api/records/{id}/transitions { transition_name: 'schedule_job' }
    API->>Engine: execute_transition()
    Note over Engine: Evaluates skip_approval_rule: priority == 'Emergency' -> TRUE!
    Note over Engine: Bypasses approval completely despite estimated_cost > 2000!
    Engine->>DB: UPDATE records SET state='Scheduled', version=2
    Engine-->>Client: Direct transition to 'Scheduled' (requires_approval: false)
```
