# Deferred Items & Technical Debt Log (What Was Cut & Future Roadmap)

This document tracks items intentionally deferred, specialized edge cases, and future architectural evolutions identified during system design, along with their proposed production blueprints. It serves as the project's **"What I Cut and Why"** architectural record.

---

## 1. Summary of Deferred & Future Items

| # | Deferred Item | Current Scope Handling | Proposed Production Solution & Strategy |
|:---|:---|:---|:---|
| **1** | **Complete Form / All-Field Restriction Handling** | API returns `{id, state, data: {}}` (empty payload). UI displays empty state without error. | Explicit `403 Forbidden ("All fields restricted for this persona")` or dedicated restricted container view in the UI. |
| **2** | **Advanced Analytics & Custom Dashboard Builder** | Hardcoded dashboard widgets in metadata (1 KPI card, 1 chart, 1 table) respecting field permissions. | Drag-and-drop dashboard canvas, multi-dimensional pivot tables, real-time WebSocket metric updates, and export to CSV/PDF. |
| **3** | **Distributed Caching Layer (Lazy Caching with TTL & Invalidation)** | Direct SQLite queries for metadata and records on every request. | Redis/Memcached read-through lazy caching for metadata schemas and record queries, with write-through cache invalidation hooks. |
| **4** | **Advanced Analytics from Audit Logs** | Audit log stores raw records queryable by Admin. | Log mining engine (SIEM), anomaly detection (e.g. repeated unauthorized attempts), state-duration analytics (bottleneck analysis on approval times). |
| **5** | **Destructive Schema Wipeout Guardrails (Form Deletion)** | Admin API blocks saving an object schema with zero fields (`min_fields >= 1`). | Strict schema validation preventing removing all fields, dependency checks against references/guards, and soft-deprecation flags instead of hard deletes. |
| **6** | **Mandatory Admin Reason / Change Justification** | Admin updates write to audit log with action type and timestamp. | Require a non-empty `change_reason` string on all metadata mutations (`PUT /api/admin/metadata/*`); reject requests without a justification comment. |
| **7** | **In-Flight Lifecycle & Approval Evolution Handling** | Records retain their current state; transitions validate against active lifecycle definition. | Lifecycle version pinning: records bind to `lifecycle_version` at creation, or require a migration wizard to transition in-flight records before publishing new lifecycle rules. |
| **8** | **Polyglot Persistence Options (Graph & Document DBs)** | SQLite + JSON columns for single-node zero-setup simplicity. | Graph database (Neo4j) for deep multi-hop entity traversal and authorization DAGs; Document database (MongoDB) for schema-free horizontal scalability. |
| **9** | **Shared Permission Concurrency & Race Condition Hardening** | Relational transactions with ACID isolation. | Optimistic concurrency control (OCC) using version vectors on permission matrices to detect and reject concurrent out-of-order admin edits. |
| **10** | **Granular Dashboard Control Patterns** | Role-level read permission checks on metric and group-by fields. | Granular widget-level permission matrices, row-level filtering per widget (e.g. "Only jobs in my department"), and time-window query restrictions. |
| **11** | **Volumetric Protection & Anti-Abuse (DDoS / Payload Limits)** | Default framework limits. | Enforce strict payload size limits (e.g., 1MB max body), maximum field counts per object (max 50 fields), query pagination ceilings (max 100 records per page), and tenant-level rate limiting. |

---

## 2. In-Depth Analysis of Key Items

### 2.1 Destructive Schema Wipeout Guardrail (Removing All Fields)
- **Problem**: A tenant admin creates a form, users submit records, and later the admin attempts to delete all fields from the schema, breaking the UI and data integrity.
- **Handling**:
  - The metadata engine validates: `len(schema_definition) >= 1`. If an admin attempts to submit an empty field array, the API rejects the update with `422 Unprocessable Entity ("An object schema must contain at least one field")`.
  - Furthermore, before a field can be deleted, the engine verifies that the field is not referenced in active lifecycle transition guards (`approval_routing`, `guard`), cross-field validation rules, or dashboard widgets.

### 2.2 Mandatory Justification Comments for Admin Modifications
- **Problem**: Unchecked metadata modifications can silently alter business rules and access permissions without accountability.
- **Solution**:
  - All admin endpoints modifying `metadata_objects`, `metadata_lifecycles`, or `metadata_permissions` must require a mandatory payload property:
    ```json
    {
      "change_reason": "Updated approval threshold from 5000 to 7500 per Q4 financial guidelines"
    }
    ```
  - If omitted or shorter than 10 characters, the request is rejected with `400 Bad Request`.
  - The justification is recorded permanently in `audit_log.reason`.

### 2.3 Handling In-Flight Records During Lifecycle Rule Changes
- **Problem**: An admin changes a lifecycle transition or adds an approval step while existing records are currently in an intermediate state (e.g., `Submitted` or `Pending Approval`).
- **Options Evaluated**:
  1. *Pinning to Lifecycle Version (Recommended)*: Each record records `lifecycle_version = 1`. In-flight records complete their journey using their original lifecycle definition, while new records use version 2.
  2. *Terminal State Requirement*: Admin cannot modify a lifecycle definition if any records are currently non-terminal (`state NOT IN ('Approved', 'Rejected', 'Done', 'Cancelled')`).
  3. *State Reset*: Automatically reset in-flight records back to `initial_state` with an explanatory audit notice to the creator.

### 2.4 Volumetric Leak-Proof Limits & DoS Prevention
- **Problem**: A malicious or faulty client floods the platform with oversized JSON payloads, infinite fields, or massive record queries.
- **Enforcement Rules**:
  - **Max Payload Size**: HTTP request bodies capped at 1MB.
  - **Max Fields Per Object**: Object definitions capped at 50 fields.
  - **Max Page Size**: API list endpoints cap `limit` at 100 rows per query.
  - **Rate Limiting**: Rate limiter middleware (e.g. 100 requests/minute per `tenant_id` + IP).

### 2.5 Polyglot Persistence Architecture (Graph DB & MongoDB)
- **Graph Database (Neo4j / Amazon Neptune)**: When domains evolve into complex multi-tenant relationship networks (e.g., Asset -> Sub-assembly -> Maintenance Contract -> Vendor -> Location Hierarchy), recursive SQL queries become expensive. Graph DBs allow instantaneous graph traversals (`MATCH (a:Asset)-[:LOCATED_IN]->(b:Building)`) and granular role-inheritance graphs.
- **Document Store (MongoDB)**: For high-volume multi-tenant deployments, MongoDB provides native JSON document indexing, sharding across tenant keys, and high-throughput write performance.
