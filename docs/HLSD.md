# High-Level System Design (HLSD)
## Metadata-Driven Governed Workflow Platform

---

## 1. Executive Summary & Core Architectural Goals

The **Metadata-Driven Governed Workflow Platform** is an enterprise-grade, domain-agnostic, multi-tenant application where every business entity, data schema, UI layout, lifecycle transition, authorization rule, approval constraint, and dashboard widget is defined via declarative JSON metadata.

### 1.1 Core Tenets & Architectural Guarantees
1. **Zero Domain-Specific Code**: Neither the backend nor the frontend contains a single hardcoded reference to any specific domain (e.g., zero occurrences of `Vendor`, `Purchase Request`, `Asset`, or `Maintenance Job`). Introducing a third business domain requires **zero code changes or deployments**—strictly new metadata seeds.
2. **Server-Authoritative Governance**: The UI is purely an adaptive projection. All access control checks, field visibility projections, state transition guard evaluations, and approval constraints are enforced strictly on the server.
3. **Ironclad Multi-Tenant Isolation**: Multi-tenancy is enforced at the API Gateway and query layers. One tenant can never access, query, or leak data into another tenant.
4. **Zero-Leakage Field-Level Security**: If a persona is not granted read access to a field, that field is stripped server-side from all record payloads and is strictly excluded from aggregate/dashboard calculations.
5. **Universal & Granular Audit Logging**: Every single event—whether accepted, rejected, forbidden, or failed due to validation—is intercepted and recorded in an immutable audit store. Logs capture actor attribution, target object, state transition, and a granular field-level diff (`old_value` vs `new_value`).
6. **Concurrent State & Approval Safety**: State transitions and approvals employ atomic transactions to prevent double-approval race conditions and enforce self-approval blocking.

---

## 2. High-Level Component Architecture

```mermaid
graph TB
    subgraph ClientLayer["Universal Client (React + Vite + Tailwind)"]
        PersonaBar["Context Switcher Bar<br/>(Tenant & Persona Switcher)"]
        FormEngine["Metadata Form Builder<br/>(Dynamic Fields, Layouts, Client Guards)"]
        RecordViews["Universal Record Views<br/>(Data Table, Detail Card, Timeline)"]
        DashboardUI["Dynamic Analytics Renderer<br/>(KPI Cards, Charts, Filter Bar)"]
        AdminStudio["Metadata Admin Studio<br/>(Schema, Lifecycle & RBAC Visual Editor)"]
    end

    subgraph EdgeLayer["API Gateway & Context Injector (FastAPI)"]
        HeaderExtractor["Header Interceptor<br/>(X-Tenant-Id, X-Persona-Role, X-Persona-Id)"]
        ContextFactory["RequestContext Builder & Validator"]
        TenantGuard["Tenant Isolation Verifier"]
    end

    subgraph SecurityLayer["Security & Governance Pipeline"]
        ObjectRBAC["Object & Action Authorizer<br/>(Create, Read, Update, Transition)"]
        FieldProjector["Field-Level Projection Engine<br/>(Read Stripping & Write Sanitization)"]
        DashboardScoper["Aggregation Field Scoper<br/>(Prevents Metric Leakage)"]
    end

    subgraph WorkflowLayer["Workflow & State Machine Engine"]
        FSM["Finite State Machine Engine<br/>(Lifecycle State Transitions)"]
        RuleEngine["Rule & Guard Evaluator<br/>(JSON Expressions: e.g. amount > 5000)"]
        ApprovalBroker["Approval Broker<br/>(Pending Queue, Self-Approval Blocker)"]
    end

    subgraph AuditSubsystem["Universal Audit & Compliance Subsystem"]
        AuditInterceptor["Audit Interceptor<br/>(Captures ALL Invocations & Outcomes)"]
        DiffCalculator["Field-Level Delta Engine<br/>(Old Value vs New Value Tracker)"]
    end

    subgraph DataLayer["Persistence & Storage Layer (SQLite + JSON)"]
        RelationalStore["Relational Metadata & Core Store"]
        RecordStore["Record Store & Version History"]
        AuditStore["Append-Only Audit Log"]
    end

    PersonaBar -->|HTTP Headers| HeaderExtractor
    FormEngine -->|API Requests| HeaderExtractor
    RecordViews -->|API Requests| HeaderExtractor
    DashboardUI -->|API Requests| HeaderExtractor
    AdminStudio -->|Admin APIs| HeaderExtractor

    HeaderExtractor --> ContextFactory
    ContextFactory --> TenantGuard
    TenantGuard --> ObjectRBAC
    ObjectRBAC --> FieldProjector
    ObjectRBAC --> WorkflowLayer

    %% Audit Interceptor connections across all stages
    HeaderExtractor -.->|400/401 Rejections| AuditInterceptor
    ObjectRBAC -.->|403 Denials| AuditInterceptor
    FieldProjector -.->|Field Write Violations| AuditInterceptor
    WorkflowLayer -.->|Guard / State Failures| AuditInterceptor
    WorkflowLayer -.->|Successful Actions| AuditInterceptor

    AuditInterceptor --> DiffCalculator
    DiffCalculator --> AuditStore

    WorkflowLayer --> RelationalStore
    WorkflowLayer --> RecordStore
```

---

## 3. Component Responsibilities & Separation of Concerns

### 3.1 Universal UI Layer
- **Domain Independence**: Renders screens entirely from metadata payloads delivered by the backend.
- **Dynamic Form Renderer**: Constructs input controls (text, number, date, select, checkbox, reference lookups) based on field definitions and handles client-side dynamic visibility.
- **Universal Data & Detail Views**: Renders sortable, filterable tables and record detail views with state badges, transition buttons, pending approval banners, and chronological history timelines.
- **Persona & Tenant Switcher**: Facilitates instant testing by toggling tenant and persona headers sent on all requests.

### 3.2 API Gateway & Context Injector Layer
- **Header Parsing**: Extracts `X-Tenant-Id`, `X-Persona-Role`, and `X-Persona-Id`.
- **Context Injection**: Produces an immutable, request-scoped context containing tenant and actor details.
- **Fail-Closed Boundary**: Immediately blocks and logs any request lacking valid tenant or persona credentials.

### 3.3 Security & Governance Pipeline
- **Object-Level RBAC**: Evaluates whether the caller's role is authorized to perform `create`, `read`, `update`, `delete`, or `transition` on the target object.
- **Field-Level Projection**:
  - **Read**: Strips all fields from API responses where the role lacks read permission.
  - **Write**: Drops or rejects writes targeting fields where the role lacks edit permission.
  - **Analytics**: Validates that metric and grouping fields are readable by the caller before calculating dashboard metrics.

### 3.4 Workflow & State Machine Engine
- **Lifecycle FSM**: Validates allowed state transitions per object definition.
- **Guard Rule Engine**: Evaluates JSON-based conditional guard expressions against record fields and actor context.
- **Approval Broker**: Manages pending approvals, enforces atomic approval decisions, and prevents self-approvals.

### 3.5 Universal Audit & Compliance Subsystem
- **Comprehensive Capture**: Enforces that **every** outcome—acceptance, user rejection, permission denial, validation failure, and guard failure—is permanently logged.
- **Granular Delta Tracking**: Computes field-level changes showing the previous and new value for every modified field, along with before and after state snapshots.
- **Audit Tamper-Resistance**: Append-only design with no update or delete access.

---

## 4. End-to-End Request Data Flows (With Comprehensive Audit Logging)

### 4.1 Record Read & Dashboard Aggregation Flow
```mermaid
sequenceDiagram
    autonumber
    actor Client as Persona (UI)
    participant GW as API Gateway
    participant Sec as Security Pipeline
    participant DB as Storage Layer
    participant Audit as Audit Subsystem

    Client->>GW: GET /api/records/{object_type}/{id} [Headers: Tenant & Role]
    GW->>GW: Build RequestContext
    GW->>Sec: Verify Object Read Permission
    alt Object Read Denied
        Sec->>Audit: Log Access Denied (Actor, Object, Outcome="DENIED", Reason="No Object Read Access")
        Sec-->>Client: 403 Forbidden ("Object access denied")
    else Object Read Permitted
        Sec->>DB: Query record (Scoped strictly by tenant_id)
        DB-->>Sec: Raw Record Data
        Sec->>Sec: Project Fields (Strip hidden fields for Role)
        Sec-->>Client: 200 OK (Projected Record Payload)
    end
```

### 4.2 Record Create / Update Flow (With Granular Field Diffs)
```mermaid
sequenceDiagram
    autonumber
    actor Client as Persona (UI)
    participant GW as API Gateway
    participant Sec as Security Pipeline
    participant Val as Validation Engine
    participant DB as Storage Layer
    participant Audit as Audit Subsystem

    Client->>GW: PUT /api/records/{object_type}/{id} [Payload: Updates, Headers: Tenant & Role]
    GW->>GW: Build RequestContext
    GW->>Sec: Validate Object & Field Edit Permissions
    alt Unauthorized Field Edited
        Sec->>Audit: Log Rejection (Actor, Outcome="DENIED", Reason="Field Edit Forbidden", Target Fields)
        Sec-->>Client: 403 Forbidden ("Editing restricted fields")
    else Permissions Valid
        Sec->>Val: Run Schema & Cross-Field Validations
        alt Validation Failed (e.g. End Date < Start Date)
            Val->>Audit: Log Rejection (Actor, Outcome="FAILED_VALIDATION", Errors)
            Val-->>Client: 422 Unprocessable Entity (Validation Details)
        else Validation Succeeded
            Val->>DB: Fetch Current Record Snapshot
            DB-->>Val: Old Record State & Field Values
            Val->>Val: Calculate Field Diffs: {field: {old: v1, new: v2}}
            Val->>DB: Commit Update & Create Version Snapshot
            Val->>Audit: Log Success (Actor, Outcome="SUCCESS", Action="UPDATE", Granular Diffs, FromState, ToState)
            Val-->>Client: 200 OK (Updated Record)
        end
    end
```

### 4.3 Lifecycle State Transition Flow
```mermaid
sequenceDiagram
    autonumber
    actor Client as Persona (UI)
    participant GW as API Gateway
    participant FSM as Workflow Engine
    participant DB as Storage Layer
    participant Audit as Audit Subsystem

    Client->>GW: POST /api/records/{id}/transitions {transition_name} [Headers: Tenant & Role]
    GW->>FSM: Validate Transition Legality & Permissions
    alt Unauthorized Transition
        FSM->>Audit: Log Denied Transition (Actor, Outcome="DENIED", Reason="Role cannot execute transition")
        FSM-->>Client: 403 Forbidden ("Transition unauthorized")
    else Transition Permitted
        FSM->>FSM: Evaluate Transition Guards (e.g., amount > 5000)
        alt Guard Check Failed
            FSM->>Audit: Log Guard Failure (Actor, Outcome="GUARD_FAILED", Reason="Amount exceeds approval threshold")
            FSM-->>Client: 400 Bad Request (Human-readable guard error)
        else Guard Check Passed
            alt Requires Approval
                FSM->>DB: Transition to Pending State & Create Approval Request
                FSM->>Audit: Log Event (Actor, Outcome="PENDING_APPROVAL", Target Role, BeforeState, AfterState)
                FSM-->>Client: 202 Accepted ("Approval requested")
            else Direct Transition
                FSM->>DB: Advance Record State & Save Version
                FSM->>Audit: Log Event (Actor, Outcome="SUCCESS", Action="TRANSITION", BeforeState, AfterState)
                FSM-->>Client: 200 OK ("State transitioned")
            end
        end
    end
```

### 4.4 Approval Decision Flow (Self-Approval Blocker & Atomic Lock)
```mermaid
sequenceDiagram
    autonumber
    actor Approver as Approver Persona
    participant GW as API Gateway
    participant Broker as Approval Broker
    participant DB as Storage Layer
    participant Audit as Audit Subsystem

    Approver->>GW: POST /api/approvals/{id}/decision {decision: "APPROVE"/"REJECT"}
    GW->>Broker: Verify Approver Role
    alt Role Unauthorized for Approval
        Broker->>Audit: Log Denied Approval (Actor, Outcome="DENIED", Reason="Role cannot approve")
        Broker-->>Approver: 403 Forbidden
    else Role Authorized
        Broker->>Broker: Check Self-Approval (Approver ID == Requester ID?)
        alt Self-Approval Attempt
            Broker->>Audit: Log Rejected Self-Approval (Actor, Outcome="DENIED", Reason="Self-approval blocked")
            Broker-->>Approver: 403 Forbidden ("Self-approval is forbidden")
        else Legitimate Approver
            Broker->>DB: Begin Atomic Lock on Approval Record
            alt Already Decided (Concurrency Race)
                Broker->>Audit: Log Race Rejection (Actor, Outcome="CONFLICT", Reason="Already processed")
                Broker-->>Approver: 409 Conflict ("Already processed")
            else Lock Acquired & Pending
                Broker->>DB: Update Approval (status, decision_notes, timestamp)
                Broker->>DB: Advance Record State (Approved or Rejected)
                Broker->>Audit: Log Decision (Actor, Outcome=decision, Action="APPROVAL_DECISION", BeforeState, AfterState)
                Broker-->>Approver: 200 OK (Decision Processed)
            end
        end
    end
```

---

## 5. Granular Audit Log Contract (High-Level Model)

Every audit entry emitted across all subsystems adheres to the following unified schema:

| Field | Conceptual Definition | Example Value |
|:---|:---|:---|
| `tenant_id` | Identifier of the tenant | `"procurement"` |
| `actor_id` | Identifier of acting user | `"user_requester_1"` |
| `actor_role` | Role of actor at time of action | `"Requester"` |
| `action` | Action attempted | `"CREATE"`, `"UPDATE"`, `"TRANSITION"`, `"APPROVE"`, `"REJECT"`, `"READ"` |
| `object_type` | Target metadata object type | `"purchase_request"` |
| `record_id` | ID of the target record | `"rec_101"` |
| `outcome` | Result of invocation | `"SUCCESS"`, `"DENIED"`, `"FAILED_VALIDATION"`, `"GUARD_FAILED"`, `"CONFLICT"` |
| `reason` | Human-readable outcome or failure message | `"Self-approval is forbidden by governance policy"` |
| `before_state` | State before transition/mutation | `"Draft"` |
| `after_state` | State after transition/mutation | `"Submitted"` |
| `field_diffs` | Granular field-level changes | `{"amount": {"old": 4000, "new": 6000}}` |
| `timestamp` | UTC ISO-8601 Timestamp | `"2026-10-11T10:30:00Z"` |

---

## 6. High-Level Edge Case Mitigation Strategy

- **Field Leakage in Dashboards**: Pre-execution authorization check on analytics queries. Hidden fields are omitted from aggregations, calculations, and grouping operations.
- **Double-Approval Race Condition**: Atomic conditional database updates ensure that only the first incoming request can alter a pending approval.
- **Self-Approval Protection**: Hard invariant check comparing `actor_id` against `requester_id` regardless of granted roles.
- **Cross-Tenant & Dangling References**: Relational reference queries are strictly scoped by `tenant_id` and active status.
- **Metadata Changes on Existing Records**: Metadata schema updates are additive and non-destructive; legacy JSON payloads remain queryable without corruption.

