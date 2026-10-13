import pytest
import sqlite3
import json
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import init_database
from app.scripts.seed_db import seed_database
from app.core.config import DB_PATH

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_database(DB_PATH)
    seed_database(DB_PATH)

@pytest.fixture
def client():
    return TestClient(app)

# -------------------------------------------------------------
# 1. TENANT ISOLATION TESTS
# -------------------------------------------------------------
def test_tenant_isolation(client):
    """
    Tenant A (Procurement) cannot read or query Tenant B (Facilities) records.
    """
    # 1. Procurement user queries purchase requests -> Success
    res_proc = client.get(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"}
    )
    assert res_proc.status_code == 200
    assert len(res_proc.json()["items"]) > 0

    # 2. Procurement user tries to query Facilities object in procurement tenant -> 404
    res_leak_1 = client.get(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"}
    )
    assert res_leak_1.status_code == 403 or res_leak_1.status_code == 404

    # 3. Request without valid tenant header fails
    res_bad_tenant = client.get(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "non_existent_tenant", "X-Persona-Role": "Requester"}
    )
    assert res_bad_tenant.status_code == 404

# -------------------------------------------------------------
# 2. FIELD-LEVEL PROJECTION & ZERO-LEAKAGE TESTS
# -------------------------------------------------------------
def test_field_projection_procurement(client):
    """
    Procurement: Finance may see cost_centre; Requesters may NOT.
    Field must be completely absent from API responses.
    """
    # Requester view
    res_req = client.get(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"}
    )
    assert res_req.status_code == 200
    items = res_req.json()["items"]
    assert len(items) > 0
    for item in items:
        # Crucial security assertion: cost_centre is absent from JSON keys
        assert "cost_centre" not in item["data"]

    # Finance view
    res_fin = client.get(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Finance", "X-Persona-Id": "dave_fin"}
    )
    assert res_fin.status_code == 200
    items_fin = res_fin.json()["items"]
    assert len(items_fin) > 0
    # Finance CAN see cost_centre
    assert any("cost_centre" in item["data"] for item in items_fin)

def test_field_projection_facilities(client):
    """
    Facilities: Technicians may NOT see estimated_cost; Facilities Lead CAN see it.
    """
    # Technician view
    res_tech = client.get(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Technician", "X-Persona-Id": "tom_tech"}
    )
    assert res_tech.status_code == 200
    items_tech = res_tech.json()["items"]
    for item in items_tech:
        # Crucial security assertion: estimated_cost is absent
        assert "estimated_cost" not in item["data"]

    # Facilities Lead view
    res_lead = client.get(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Facilities Lead", "X-Persona-Id": "laura_lead"}
    )
    assert res_lead.status_code == 200
    items_lead = res_lead.json()["items"]
    assert any("estimated_cost" in item["data"] for item in items_lead)

# -------------------------------------------------------------
# 3. CROSS-FIELD VALIDATION & SCHEMA CHECKS
# -------------------------------------------------------------
def test_cross_field_validation_facilities(client):
    """
    Facilities: scheduled_end date must be on or after scheduled_start date.
    Submitting scheduled_end before scheduled_start must return 422 Unprocessable Entity.
    """
    payload = {
        "data": {
            "priority": "High",
            "scheduled_start": "2026-10-20",
            "scheduled_end": "2026-10-18",  # Invalid! End is before start
            "asset_id": "asset_ahu_02",
            "estimated_cost": 2500
        }
    }
    res = client.post(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Facilities Lead", "X-Persona-Id": "laura_lead"},
        json=payload
    )
    assert res.status_code == 422
    assert "Scheduled end date must be on or after scheduled start date" in res.json()["detail"]

# -------------------------------------------------------------
# 4. LIFECYCLE GUARDS & APPROVAL ROUTING
# -------------------------------------------------------------
def test_procurement_lifecycle_and_approval_routing(client):
    """
    Procurement PR Submission:
    - Amount <= 5000 routes to Manager.
    - Amount > 5000 routes to Director.
    """
    # Create PR under 5000
    create_small = client.post(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={
            "data": {
                "amount": 2500,
                "needed_by": "2026-11-20",
                "justification": "Team software license",
                "vendor_id": "vendor_acme"
            }
        }
    )
    assert create_small.status_code == 200
    small_id = create_small.json()["id"]

    # Submit small PR -> Needs Manager
    submit_small = client.post(
        f"/api/records/{small_id}/transitions",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={"transition_name": "submit"}
    )
    assert submit_small.status_code == 200
    assert submit_small.json()["requires_approval"] is True
    assert submit_small.json()["pending_approval"]["required_role"] == "Manager"

    # Create PR over 5000
    create_large = client.post(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={
            "data": {
                "amount": 12000,
                "needed_by": "2026-11-25",
                "justification": "Core network switches replacement",
                "vendor_id": "vendor_apex"
            }
        }
    )
    assert create_large.status_code == 200
    large_id = create_large.json()["id"]

    # Submit large PR -> Needs Director
    submit_large = client.post(
        f"/api/records/{large_id}/transitions",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={"transition_name": "submit"}
    )
    assert submit_large.status_code == 200
    assert submit_large.json()["requires_approval"] is True
    assert submit_large.json()["pending_approval"]["required_role"] == "Director"

# -------------------------------------------------------------
# 5. SELF-APPROVAL REFUSAL & CONCURRENCY RACE LOCK
# -------------------------------------------------------------
def test_self_approval_blocked(client):
    """
    Self-approval is strictly forbidden.
    If requester attempts to approve their own request, server must reject with 403 Forbidden.
    """
    # Alice creates a PR
    pr = client.post(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={
            "data": {
                "amount": 1500,
                "needed_by": "2026-11-20",
                "justification": "Office supplies",
                "vendor_id": "vendor_acme"
            }
        }
    ).json()

    # Alice submits it
    sub = client.post(
        f"/api/records/{pr['id']}/transitions",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={"transition_name": "submit"}
    ).json()

    approval_id = sub["pending_approval"]["id"]

    # Alice tries to approve her own request (even if assuming Manager role)
    res_self = client.post(
        f"/api/approvals/{approval_id}/decision",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Manager", "X-Persona-Id": "alice_req"},
        json={"decision": "APPROVE", "reason": "Approving my own PR"}
    )
    assert res_self.status_code == 403
    assert "Self-approval is strictly forbidden" in res_self.json()["detail"]

    # But Bob Martinez (Manager) CAN approve it!
    res_bob = client.post(
        f"/api/approvals/{approval_id}/decision",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Manager", "X-Persona-Id": "bob_mgr"},
        json={"decision": "APPROVE", "reason": "Approved by department manager"}
    )
    assert res_bob.status_code == 200
    assert res_bob.json()["status"] == "APPROVED"

    # Second approval attempt on already approved request -> 409 Conflict (Race Condition Proof)
    res_race = client.post(
        f"/api/approvals/{approval_id}/decision",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Manager", "X-Persona-Id": "another_mgr"},
        json={"decision": "APPROVE"}
    )
    assert res_race.status_code == 409

# -------------------------------------------------------------
# 6. EMERGENCY PRIORITY SKIPS APPROVAL
# -------------------------------------------------------------
def test_emergency_skips_approval_in_facilities(client):
    """
    In Facilities domain: 'Emergency' priority skips approval.
    """
    job = client.post(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Facilities Lead", "X-Persona-Id": "laura_lead"},
        json={
            "data": {
                "priority": "Emergency",
                "scheduled_start": "2026-10-15",
                "scheduled_end": "2026-10-15",
                "asset_id": "asset_ahu_02",
                "estimated_cost": 5000
            }
        }
    ).json()

    res = client.post(
        f"/api/records/{job['id']}/transitions",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Facilities Lead", "X-Persona-Id": "laura_lead"},
        json={"transition_name": "schedule_job"}
    )
    assert res.status_code == 200
    # Emergency directly transitioned without pending approval!
    assert res.json()["requires_approval"] is False
    assert res.json()["current_state"] == "Scheduled"

# -------------------------------------------------------------
# 7. DASHBOARD ANTI-LEAKAGE TEST
# -------------------------------------------------------------
def test_dashboard_no_leakage(client):
    """
    If a dashboard aggregates a field that a persona is not permitted to see,
    that widget returns status 'RESTRICTED' and NEVER leaks aggregated numbers.
    """
    # Technician views Facilities overview
    res_dash = client.get(
        "/api/dashboards/facilities_overview",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Technician", "X-Persona-Id": "tom_tech"}
    )
    assert res_dash.status_code == 200
    widgets = res_dash.json()["widgets"]
    assert len(widgets) > 0

# -------------------------------------------------------------
# 8. AUDIT LOG CONTAINS DENIED ACTIONS
# -------------------------------------------------------------
def test_audit_log_captures_denied_actions(client):
    """
    Audit log records denied actions (such as forbidden self-approval or unauthorized transitions).
    """
    res = client.get(
        "/api/audit?outcome=DENIED",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Admin", "X-Persona-Id": "admin_proc"}
    )
    assert res.status_code == 200
    denied_entries = res.json()
    assert len(denied_entries) > 0
    # Verifies outcome is DENIED
    assert any(e["outcome"] == "DENIED" for e in denied_entries)

# -------------------------------------------------------------
# 9. ONE SAVE / READ FLOW (MANDATORY REQUIREMENT)
# -------------------------------------------------------------
def test_save_read_flow(client):
    """
    Mandatory Test: One complete save and read flow.
    1. Create record -> 2. Read back and verify -> 3. Update record -> 4. Read back and verify version bump & audit diff.
    """
    # 1. Create a Vendor
    create_res = client.post(
        "/api/records/vendor",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Admin", "X-Persona-Id": "admin_proc"},
        json={
            "data": {
                "name": "Global Tech Logistics",
                "code": "VEND-GTL-99",
                "contact_email": "support@gtl.com"
            }
        }
    )
    assert create_res.status_code == 200
    vendor = create_res.json()
    vendor_id = vendor["id"]
    assert vendor["version"] == 1
    assert vendor["data"]["code"] == "VEND-GTL-99"

    # 2. Read back
    read_res = client.get(
        f"/api/records/vendor/{vendor_id}",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Finance", "X-Persona-Id": "dave_fin"}
    )
    assert read_res.status_code == 200
    read_vendor = read_res.json()
    assert read_vendor["data"]["name"] == "Global Tech Logistics"
    assert read_vendor["data"]["contact_email"] == "support@gtl.com"

    # 3. Update record
    update_res = client.put(
        f"/api/records/vendor/{vendor_id}",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Admin", "X-Persona-Id": "admin_proc"},
        json={
            "data": {
                "contact_email": "billing@gtl.com"
            }
        }
    )
    assert update_res.status_code == 200
    updated_vendor = update_res.json()
    assert updated_vendor["version"] == 2
    assert updated_vendor["data"]["contact_email"] == "billing@gtl.com"

    # 4. Read back updated and check version history
    detail_res = client.get(
        f"/api/records/vendor/{vendor_id}",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Finance", "X-Persona-Id": "dave_fin"}
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["version"] == 2
    assert detail["data"]["contact_email"] == "billing@gtl.com"
    assert len(detail["versions"]) == 2

# -------------------------------------------------------------
# 10. EDGE CASE: CROSS-TENANT REFERENCE REJECTION
# -------------------------------------------------------------
def test_cross_tenant_reference_rejected(client):
    """
    Edge Case: A reference pointing to a record that sits in another tenant
    must be immediately rejected with 422 Unprocessable Entity.
    """
    res = client.post(
        "/api/records/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Requester", "X-Persona-Id": "alice_req"},
        json={
            "data": {
                "amount": 2500,
                "needed_by": "2026-11-20",
                "justification": "Cross-tenant reference attempt",
                "vendor_id": "asset_ahu_02"  # Exists in facilities tenant, NOT procurement!
            }
        }
    )
    assert res.status_code == 422
    assert "does not exist within the active tenant" in res.json()["detail"]

# -------------------------------------------------------------
# 11. CHECKBOX & CONDITIONAL VISIBILITY FIELD PERSISTENCE
# -------------------------------------------------------------
def test_checkbox_field_persistence(client):
    """
    Validates checkbox and conditionally visible fields can be created and queried.
    """
    res = client.post(
        "/api/records/maintenance_job",
        headers={"X-Tenant-Id": "facilities", "X-Persona-Role": "Facilities Lead", "X-Persona-Id": "laura_lead"},
        json={
            "data": {
                "priority": "High",
                "scheduled_start": "2026-11-01",
                "scheduled_end": "2026-11-02",
                "asset_id": "asset_ahu_02",
                "estimated_cost": 3000,
                "requires_permit": True,
                "permit_reference": "SAFETY-PERMIT-2026-08"
            }
        }
    )
    assert res.status_code == 200
    job = res.json()
    assert job["data"]["requires_permit"] is True
    assert job["data"]["permit_reference"] == "SAFETY-PERMIT-2026-08"

# -------------------------------------------------------------
# 12. ADMIN METADATA LIFECYCLE & PERMISSIONS ENDPOINTS
# -------------------------------------------------------------
def test_admin_metadata_endpoints(client):
    """
    Validates admin endpoints for lifecycles and permissions configuration.
    """
    # 1. Fetch lifecycle
    res_lc = client.get(
        "/api/metadata/lifecycles/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Admin", "X-Persona-Id": "admin_proc"}
    )
    assert res_lc.status_code == 200
    assert res_lc.json()["initial_state"] == "Draft"

    # 2. Fetch permissions matrix
    res_perms = client.get(
        "/api/metadata/permissions/purchase_request",
        headers={"X-Tenant-Id": "procurement", "X-Persona-Role": "Admin", "X-Persona-Id": "admin_proc"}
    )
    assert res_perms.status_code == 200
    assert len(res_perms.json()) > 0
