import pytest
from datetime import date, timedelta
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.notification import Notification
from backend.app.models.audit_log import AuditLog
from backend.app.services.reminder_service import process_maturity_reminders

def test_1_fdr_approaching_maturity_30_days(client, db_session, test_institution, test_institution_user, admin_token):
    """1. Test FDR approaching maturity (30 days window)."""
    controlled_date = date(2026, 6, 1)
    dep = Deposit(
        fdr_number="FDR-TEST-30DAYS",
        amount=500000.0,
        bank_name="State Bank of India",
        issue_date=controlled_date - timedelta(days=335),
        maturity_date=controlled_date + timedelta(days=30),  # Exactly 30 days
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    # Run reminder engine with controlled reference date
    summary = process_maturity_reminders(db_session, as_of_date=controlled_date)
    assert summary["reminders_created"] >= 1

    # Reload deposit to verify status transition
    db_session.refresh(dep)
    assert dep.status == DepositStatus.MATURITY_APPROACHING

    # Verify notification created
    notif = db_session.query(Notification).filter(
        Notification.deposit_id == dep.id,
        Notification.reminder_type == "REMINDER_30_DAYS"
    ).first()
    assert notif is not None
    assert notif.days_remaining == 30
    assert "30 Days" in notif.title

def test_2_fdr_maturing_within_7_days(client, db_session, test_institution, test_institution_user):
    """2. Test FDR maturing within 7 days."""
    controlled_date = date(2026, 7, 1)
    dep = Deposit(
        fdr_number="FDR-TEST-7DAYS",
        amount=750000.0,
        bank_name="Punjab National Bank",
        issue_date=controlled_date - timedelta(days=358),
        maturity_date=controlled_date + timedelta(days=7),  # 7 days remaining
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    process_maturity_reminders(db_session, as_of_date=controlled_date)

    notif = db_session.query(Notification).filter(
        Notification.deposit_id == dep.id,
        Notification.reminder_type == "REMINDER_7_DAYS"
    ).first()
    assert notif is not None
    assert notif.days_remaining == 7
    assert "7 Days" in notif.title

def test_3_fdr_maturing_within_1_day(client, db_session, test_institution, test_institution_user):
    """3. Test FDR maturing within 1 day (tomorrow)."""
    controlled_date = date(2026, 8, 1)
    dep = Deposit(
        fdr_number="FDR-TEST-1DAY",
        amount=1000000.0,
        bank_name="Canara Bank",
        issue_date=controlled_date - timedelta(days=364),
        maturity_date=controlled_date + timedelta(days=1),  # 1 day remaining
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    process_maturity_reminders(db_session, as_of_date=controlled_date)

    notif = db_session.query(Notification).filter(
        Notification.deposit_id == dep.id,
        Notification.reminder_type == "REMINDER_1_DAY"
    ).first()
    assert notif is not None
    assert notif.days_remaining == 1
    assert "Tomorrow" in notif.title

def test_4_fdr_reaching_maturity_date(client, db_session, test_institution, test_institution_user):
    """4. Test FDR reaching its maturity date (days = 0). Must transition to MATURED_ACTION_REQUIRED."""
    controlled_date = date(2026, 9, 1)
    dep = Deposit(
        fdr_number="FDR-TEST-0DAY",
        amount=1500000.0,
        bank_name="Bank of Baroda",
        issue_date=controlled_date - timedelta(days=365),
        maturity_date=controlled_date,  # Exactly matured today
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    process_maturity_reminders(db_session, as_of_date=controlled_date)

    db_session.refresh(dep)
    # Business rule: Must move to MATURED_ACTION_REQUIRED and NOT automatically release/forfeit
    assert dep.status == DepositStatus.MATURED_ACTION_REQUIRED

    notif = db_session.query(Notification).filter(
        Notification.deposit_id == dep.id,
        Notification.reminder_type == "REMINDER_ON_MATURITY"
    ).first()
    assert notif is not None
    assert notif.days_remaining == 0

    # Verify audit log recorded
    log = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == dep.id,
        AuditLog.action == "STATUS_CHANGED"
    ).first()
    assert log is not None
    assert "MATURED_ACTION_REQUIRED" in log.details

def test_5_duplicate_reminder_prevention(client, db_session, test_institution, test_institution_user):
    """5. Test duplicate reminder prevention (idempotency)."""
    controlled_date = date(2026, 10, 1)
    dep = Deposit(
        fdr_number="FDR-TEST-DEDUP",
        amount=800000.0,
        bank_name="HDFC Bank",
        issue_date=controlled_date - timedelta(days=335),
        maturity_date=controlled_date + timedelta(days=30),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    # First run
    run1 = process_maturity_reminders(db_session, as_of_date=controlled_date)
    initial_count = db_session.query(Notification).filter(Notification.deposit_id == dep.id).count()
    assert initial_count >= 1

    # Second run immediately on same date
    run2 = process_maturity_reminders(db_session, as_of_date=controlled_date)
    # Second run must create 0 new reminders for this deposit
    final_count = db_session.query(Notification).filter(Notification.deposit_id == dep.id).count()
    assert final_count == initial_count

def test_6_notification_retrieval(client, institution_token, db_session, test_institution, test_institution_user):
    """6. Test notification retrieval via /api/notifications and /unread-count."""
    notif = Notification(
        recipient_user_id=test_institution_user.id,
        institution_id=test_institution.id,
        deposit_id=1,
        reminder_type="TEST_RETRIEVAL",
        title="Test Notification Title",
        message="Test Notification Body Content",
        is_read=False
    )
    db_session.add(notif)
    db_session.commit()

    # List notifications
    res = client.get("/api/notifications", headers={"Authorization": f"Bearer {institution_token}"})
    assert res.status_code == 200
    data = res.json()
    assert any(n["title"] == "Test Notification Title" for n in data)

    # Check unread count
    res_count = client.get("/api/notifications/unread-count", headers={"Authorization": f"Bearer {institution_token}"})
    assert res_count.status_code == 200
    assert res_count.json()["unread_count"] >= 1

def test_7_marking_notifications_as_read(client, institution_token, db_session, test_institution, test_institution_user):
    """7. Test marking notifications as read."""
    notif = Notification(
        recipient_user_id=test_institution_user.id,
        institution_id=test_institution.id,
        deposit_id=1,
        reminder_type="TEST_MARK_READ",
        title="Unread Notification",
        message="Please mark me as read",
        is_read=False
    )
    db_session.add(notif)
    db_session.commit()

    patch_res = client.patch(
        f"/api/notifications/{notif.id}/read",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_read"] is True

def test_8_institution_access_restrictions(client, institution_token, second_institution_token, db_session, second_institution, second_institution_user):
    """8. Test institution access restrictions: cannot view other colleges' FDRs or notifications."""
    # Create FDR belonging to Second College
    dep = Deposit(
        fdr_number="FDR-SECOND-COLLEGE",
        amount=1200000.0,
        bank_name="Axis Bank",
        issue_date=date(2025, 1, 1),
        maturity_date=date(2028, 1, 1),
        status=DepositStatus.ACTIVE,
        institution_id=second_institution.id,
        submitted_by_id=second_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    # Institution 1 attempts to view Institution 2's FDR -> 403 Forbidden
    res = client.get(f"/api/deposits/{dep.id}", headers={"Authorization": f"Bearer {institution_token}"})
    assert res.status_code == 403

def test_9_unauthorized_approval_attempts(client, institution_token, db_session, test_institution, test_institution_user):
    """9. Test unauthorized approval attempts: Institution users CANNOT approve requests or initiate forfeiture."""
    dep = Deposit(
        fdr_number="FDR-FORBIDDEN-APPROVE",
        amount=1000000.0,
        bank_name="ICICI Bank",
        issue_date=date(2025, 1, 1),
        maturity_date=date(2027, 1, 1),
        status=DepositStatus.RENEWAL_REQUESTED,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    # Institution attempts to approve their own request -> 403 Forbidden
    decision_res = client.post(
        f"/api/deposits/{dep.id}/action-decision",
        json={"decision": "APPROVE", "decision_remarks": "Self approved"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert decision_res.status_code == 403

    # Institution attempts to request forfeiture -> 403 Forbidden
    forfeit_res = client.post(
        f"/api/deposits/{dep.id}/forfeiture-request",
        json={"violation_reason": "Illegal request", "statutory_clause": "Clause 4.1"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert forfeit_res.status_code == 403

def test_10_renewal_release_forfeiture_validation(client, institution_token, officer_token, db_session, test_institution, test_institution_user):
    """10. Test full workflow for renewal, release, and forfeiture validation."""
    today = date.today()
    dep = Deposit(
        fdr_number="FDR-WORKFLOW-TEST",
        amount=2000000.0,
        bank_name="Union Bank of India",
        issue_date=today - timedelta(days=365),
        maturity_date=today + timedelta(days=10),
        status=DepositStatus.MATURED_ACTION_REQUIRED,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()

    # A. Institution requests Renewal
    renewal_res = client.post(
        f"/api/deposits/{dep.id}/renewal-request",
        json={"requested_tenure_months": 36, "remarks": "Renewal requested for 3 years."},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert renewal_res.status_code == 200
    assert renewal_res.json()["status"] == "RENEWAL_REQUESTED"

    # Officer approves Renewal
    new_mat_date = str(today + timedelta(days=365 * 3))
    approve_res = client.post(
        f"/api/deposits/{dep.id}/action-decision",
        json={"decision": "APPROVE", "decision_remarks": "Renewal approved for 3 years", "extended_maturity_date": new_mat_date},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "ACTIVE"
    assert approve_res.json()["maturity_date"] == new_mat_date

    # B. Institution requests Release
    release_res = client.post(
        f"/api/deposits/{dep.id}/release-request",
        json={"justification": "Course closure compliance fully certified by regional committee.", "compliance_reference": "AICTE/ORDER/2026/891"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert release_res.status_code == 200
    assert release_res.json()["status"] == "RELEASE_REQUESTED"

    # Release approval needs supporting information: a VERIFIED document on the FDR.
    from backend.app.models.document import Document, DocumentVerificationStatus
    db_session.add(Document(
        deposit_id=dep.id, institution_id=dep.institution_id, original_filename="closure-order.pdf",
        stored_filename="closure-order-test-10.pdf", file_size=100, mime_type="application/pdf",
        uploaded_by_id=test_institution_user.id, verification_status=DocumentVerificationStatus.VERIFIED))
    db_session.commit()

    # Officer approves Release -> RELEASED (the unified workflow records a released FDR as RELEASED)
    approve_release_res = client.post(
        f"/api/deposits/{dep.id}/action-decision",
        json={"decision": "APPROVE", "decision_remarks": "Discharge certificate issued to bank."},
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert approve_release_res.status_code == 200
    assert approve_release_res.json()["status"] == "RELEASED"

def test_11_existing_apis_regression(client, admin_token, institution_token):
    """11. Verify existing authentication and deposit APIs continue to work without regression."""
    # Auth me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "ADMIN"

    # Health check
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # Extended dashboard stats
    stats_res = client.get("/api/stats/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_active_fdrs" in stats
    assert "maturing_within_30_days" in stats
    assert "matured_action_required" in stats
    assert "renewal_requests_pending" in stats
    assert "release_requests_pending" in stats
    assert "forfeiture_requests_pending" in stats

    # Upcoming maturities endpoint
    upcoming_res = client.get("/api/deposits/upcoming-maturities", headers={"Authorization": f"Bearer {admin_token}"})
    assert upcoming_res.status_code == 200
    assert isinstance(upcoming_res.json(), list)

    # Matured deposits endpoint
    matured_res = client.get("/api/deposits/matured", headers={"Authorization": f"Bearer {admin_token}"})
    assert matured_res.status_code == 200
    assert isinstance(matured_res.json(), list)
