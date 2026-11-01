import pytest
from datetime import date, timedelta
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.approval_request import ApprovalRequest, RequestType, RequestStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.notification import Notification

@pytest.fixture()
def active_fdr(db_session, test_institution, test_institution_user):
    """Fixture creating an active FDR deposit for test_institution."""
    today = date.today()
    dep = Deposit(
        fdr_number="FDR-WF-TEST-001",
        amount=2500000.0,
        bank_name="State Bank of India",
        branch_name="Parliament Street, New Delhi",
        ifsc_code="SBIN0000691",
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=30),  # Maturing in 30 days
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)
    return dep

@pytest.fixture()
def second_college_fdr(db_session, second_institution, second_institution_user):
    """Fixture creating an FDR deposit belonging to second_institution."""
    today = date.today()
    dep = Deposit(
        fdr_number="FDR-WF-SECOND-002",
        amount=3000000.0,
        bank_name="Bank of Baroda",
        branch_name="Shivajinagar Pune",
        ifsc_code="BARB0001001",
        issue_date=today - timedelta(days=200),
        maturity_date=today + timedelta(days=165),
        status=DepositStatus.ACTIVE,
        institution_id=second_institution.id,
        submitted_by_id=second_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)
    return dep

# 1. Institution Request Submissions
def test_institution_submit_renewal_request(client, institution_token, active_fdr, db_session):
    """Test institution submitting an FDR renewal extension request."""
    payload = {
        "deposit_id": active_fdr.id,
        "requested_tenure_months": 36,
        "description": "Requesting 3-year extension for NBA accreditation compliance.",
        "supporting_document_ids": [1, 2]
    }
    res = client.post(
        "/api/requests/renewal",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["deposit_id"] == active_fdr.id
    assert data["request_type"] == "RENEWAL"
    assert data["status"] == "SUBMITTED"
    assert data["requested_tenure_months"] == 36
    assert data["fdr_number"] == active_fdr.fdr_number

    # Verify FDR status was updated to RENEWAL_REQUESTED
    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.RENEWAL_REQUESTED

    # Verify AuditLog created
    audit = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == active_fdr.id,
        AuditLog.action == "REQUEST_SUBMITTED_RENEWAL"
    ).first()
    assert audit is not None
    assert "36 months" in audit.details

def test_institution_submit_release_request(client, institution_token, active_fdr, db_session):
    """Test institution submitting an FDR release request."""
    payload = {
        "deposit_id": active_fdr.id,
        "justification": "Academic program tenure completed without statutory liabilities.",
        "compliance_reference": "AICTE-NOC-2026-9912",
        "description": "Program closure approved by State DTE."
    }
    res = client.post(
        "/api/requests/release",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["request_type"] == "RELEASE"
    assert data["status"] == "SUBMITTED"
    assert data["compliance_reference"] == "AICTE-NOC-2026-9912"

    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.RELEASED or active_fdr.status == DepositStatus.RELEASE_REQUESTED

def test_forfeiture_request(client, officer_token, active_fdr, db_session):
    """Test statutory forfeiture request initiation."""
    payload = {
        "deposit_id": active_fdr.id,
        "violation_reason": "Non-compliance with faculty-student ratio norms despite 3 notices.",
        "statutory_clause": "Clause 4.8.2 APH 2026-27",
        "description": "Show cause notice deadline expired without satisfactory response."
    }
    res = client.post(
        "/api/requests/forfeiture",
        json=payload,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["request_type"] == "FORFEITURE"
    assert data["statutory_clause"] == "Clause 4.8.2 APH 2026-27"

    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.FORFEITURE_REQUESTED

# 2. Duplicate Request Prevention
def test_duplicate_pending_request_prevention(client, institution_token, active_fdr):
    """Test that a second request cannot be submitted while one is already pending."""
    # First renewal request
    res1 = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res1.status_code == 201

    # Second renewal attempt on same FDR -> 400 Bad Request
    res2 = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 24},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res2.status_code == 400
    assert "already pending" in res2.json()["detail"].lower()

    # Conflicting release attempt on same FDR -> 400 Bad Request
    res3 = client.post(
        "/api/requests/release",
        json={"deposit_id": active_fdr.id, "justification": "Closure request conflict test"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res3.status_code == 400
    assert "already pending" in res3.json()["detail"].lower()

# 3. Officer Queue & Scrutiny
def test_officer_view_pending_queue(client, officer_token, institution_token, active_fdr):
    """Test officer viewing pending requests and institution prohibited from accessing queue."""
    # Submit a request
    client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )

    # Officer accesses /api/requests/pending -> 200 OK
    res_officer = client.get(
        "/api/requests/pending",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res_officer.status_code == 200
    pending_list = res_officer.json()
    assert len(pending_list) >= 1
    assert any(r["deposit_id"] == active_fdr.id for r in pending_list)

    # Institution accesses /api/requests/pending -> 403 Forbidden
    res_inst = client.get(
        "/api/requests/pending",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_inst.status_code == 403

# 4. Officer Assignment
def test_officer_assignment_workflow(client, officer_token, institution_token, active_fdr, test_officer_user):
    """Test assigning an officer transitions status to UNDER_REVIEW."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    # Assign officer
    assign_res = client.patch(
        f"/api/requests/{req_id}/assign",
        json={"officer_id": test_officer_user.id},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert assign_res.status_code == 200
    data = assign_res.json()
    assert data["status"] == "UNDER_REVIEW"
    assert data["assigned_officer_id"] == test_officer_user.id

# 5. Unauthorized Approval & Decision Control
def test_institution_cannot_approve_or_reject_requests(client, institution_token, active_fdr):
    """Test that institutions CANNOT approve or reject their own requests (403 Forbidden)."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    # Institution tries to approve -> 403 Forbidden
    appr_res = client.patch(
        f"/api/requests/{req_id}/approve",
        json={"decision_remarks": "Self-approval attempt"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert appr_res.status_code == 403

    # Institution tries to reject -> 403 Forbidden
    rej_res = client.patch(
        f"/api/requests/{req_id}/reject",
        json={"rejection_reason": "Self-rejection attempt"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert rej_res.status_code == 403

# 6. Rejection Without Reason Rejection
def test_rejection_requires_mandatory_reason(client, officer_token, institution_token, active_fdr):
    """Test rejection fails with 422 if rejection_reason is empty or missing."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    res = client.patch(
        f"/api/requests/{req_id}/reject",
        json={"rejection_reason": ""},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res.status_code == 422

# 7. Complete Officer Approval Workflow
def test_officer_approve_renewal_workflow(client, officer_token, institution_token, active_fdr, db_session):
    """Test officer approval extends maturity date, sets FDR to ACTIVE, and audits."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 24},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    target_new_maturity = date.today() + timedelta(days=730)
    appr_res = client.patch(
        f"/api/requests/{req_id}/approve",
        json={
            "decision_remarks": "Tenure extension approved for 24 months after verification of bank lien.",
            "extended_maturity_date": str(target_new_maturity)
        },
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert appr_res.status_code == 200
    data = appr_res.json()
    assert data["status"] == "APPROVED"
    assert data["extended_maturity_date"] == str(target_new_maturity)

    # Verify FDR status updated to ACTIVE with new maturity date
    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.ACTIVE
    assert active_fdr.maturity_date == target_new_maturity

    # Verify AuditLog created
    audit = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == active_fdr.id,
        AuditLog.action == "REQUEST_APPROVED_RENEWAL"
    ).first()
    assert audit is not None
    assert "verification of bank lien" in audit.details

# 8. Complete Officer Rejection Workflow
def test_officer_reject_workflow(client, officer_token, institution_token, active_fdr, db_session):
    """Test officer rejection reverts FDR status, records mandatory reason, and notifies."""
    submit_res = client.post(
        "/api/requests/release",
        json={"deposit_id": active_fdr.id, "justification": "Premature release justification."},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    reason = "Pending student grievance regarding fee refund unresolved. Release denied."
    rej_res = client.patch(
        f"/api/requests/{req_id}/reject",
        json={"rejection_reason": reason},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert rej_res.status_code == 200
    data = rej_res.json()
    assert data["status"] == "REJECTED"
    assert data["decision_reason"] == reason

    # Verify FDR reverted to ACTIVE
    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.ACTIVE
    assert reason in active_fdr.verification_remarks

# 9. Invalid State Transitions
def test_invalid_state_transitions(client, officer_token, institution_token, active_fdr):
    """Test that attempting to re-approve or re-reject a finalized request returns 400."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    # 1. Approve
    client.patch(
        f"/api/requests/{req_id}/approve",
        json={"decision_remarks": "First approval"},
        headers={"Authorization": f"Bearer {officer_token}"}
    )

    # 2. Attempt second approve -> 400 Bad Request
    res_second_approve = client.patch(
        f"/api/requests/{req_id}/approve",
        json={"decision_remarks": "Illegal second approval"},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res_second_approve.status_code == 400
    assert "Cannot approve request with status 'APPROVED'" in res_second_approve.json()["detail"]

    # 3. Attempt reject on already approved request -> 400 Bad Request
    res_reject_approved = client.patch(
        f"/api/requests/{req_id}/reject",
        json={"rejection_reason": "Illegal reject on approved"},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert res_reject_approved.status_code == 400

# 10. Request Cancellation Workflow
def test_institution_cancel_request(client, institution_token, active_fdr, db_session):
    """Test institution cancelling a submitted request reverts FDR status."""
    submit_res = client.post(
        "/api/requests/renewal",
        json={"deposit_id": active_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    req_id = submit_res.json()["id"]

    # Cancel request
    cancel_res = client.patch(
        f"/api/requests/{req_id}/cancel",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    db_session.refresh(active_fdr)
    assert active_fdr.status == DepositStatus.ACTIVE

# 11. Cross-Institution Tenancy & Isolation
def test_cross_institution_isolation(client, institution_token, second_institution_token, second_college_fdr):
    """Test cross-institution submission, view, and cancellation prevention."""
    # Institution 1 attempts to submit renewal on Institution 2's FDR -> 403 Forbidden
    res_submit = client.post(
        "/api/requests/renewal",
        json={"deposit_id": second_college_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_submit.status_code == 403

    # Institution 2 submits renewal
    res_inst2_submit = client.post(
        "/api/requests/renewal",
        json={"deposit_id": second_college_fdr.id, "requested_tenure_months": 12},
        headers={"Authorization": f"Bearer {second_institution_token}"}
    )
    assert res_inst2_submit.status_code == 201
    req_id = res_inst2_submit.json()["id"]

    # Institution 1 attempts to view Institution 2's request -> 403 Forbidden
    res_view = client.get(
        f"/api/requests/{req_id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_view.status_code == 403

    # Institution 1 attempts to cancel Institution 2's request -> 403 Forbidden
    res_cancel = client.patch(
        f"/api/requests/{req_id}/cancel",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_cancel.status_code == 403
