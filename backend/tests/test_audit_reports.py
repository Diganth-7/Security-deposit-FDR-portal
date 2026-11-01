"""Phase 6: audit trail security, reports, CSV export. Dates are controlled relative to today()."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.models.approval_request import ApprovalRequest, RequestStatus, RequestType
from backend.app.models.audit_log import AuditLog
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.document import Document, DocumentVerificationStatus
from backend.app.services.audit_service import record_audit_log
from backend.app.utils.clock import today


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_fdr(db, inst, user, number, amount="100000.00", status=DepositStatus.ACTIVE, maturity_in=200, bank="SBI", contract=None):
    d = Deposit(fdr_number=number, amount=Decimal(amount), bank_name=bank, issue_date=today() - timedelta(days=100),
                maturity_date=today() + timedelta(days=maturity_in), status=status, institution_id=inst.id,
                submitted_by_id=user.id, contract_id=contract.id if contract else None)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def make_contract(db, inst, number="CON-R-1", required="150000.00", status=ContractStatus.ACTIVE):
    c = Contract(contract_number=number, title="Report contract", institution_id=inst.id,
                 contract_type="Institutional Affiliation", contract_amount=Decimal("1000000"),
                 required_deposit_amount=Decimal(required), start_date=today() - timedelta(days=30),
                 end_date=today() + timedelta(days=300), status=status)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def world(db_session, test_institution, test_institution_user, second_institution, second_institution_user):
    """Two institutions with a spread of FDRs."""
    c1 = make_contract(db_session, test_institution)
    f = {
        "a_near": make_fdr(db_session, test_institution, test_institution_user, "FDR-R-NEAR", "100000.00", maturity_in=10, contract=c1),
        "a_far": make_fdr(db_session, test_institution, test_institution_user, "FDR-R-FAR", "50000.50", maturity_in=300, contract=c1),
        "a_matured": make_fdr(db_session, test_institution, test_institution_user, "FDR-R-MAT", "20000.00",
                              status=DepositStatus.MATURED_ACTION_REQUIRED, maturity_in=-5),
        "a_unverified": make_fdr(db_session, test_institution, test_institution_user, "FDR-R-UNV", "999999.00",
                                 status=DepositStatus.PENDING_VERIFICATION, maturity_in=400, contract=c1),
        "b_near": make_fdr(db_session, second_institution, second_institution_user, "FDR-R-B1", "70000.00", maturity_in=5),
    }
    return {"c1": c1, "fdrs": f}


# ---------------- audit trail ----------------
def test_audit_entries_cannot_be_modified(db_session, test_admin_user, test_institution):
    d = make_fdr(db_session, test_institution, test_admin_user, "FDR-AUD-1")
    entry = record_audit_log(db_session, deposit_id=d.id, action="TEST_ACTION", actor_id=test_admin_user.id, details="x")
    entry.details = "tampered"
    with pytest.raises(PermissionError):
        db_session.commit()


def test_audit_entries_cannot_be_deleted(db_session, test_admin_user, test_institution):
    d = make_fdr(db_session, test_institution, test_admin_user, "FDR-AUD-3")
    entry = record_audit_log(db_session, deposit_id=d.id, action="TEST_ACTION", actor_id=test_admin_user.id, details="x")
    db_session.delete(entry)
    with pytest.raises(PermissionError):
        db_session.commit()


def test_audit_details_never_store_secrets(db_session, test_admin_user):
    e = record_audit_log(db_session, action="X", actor_id=test_admin_user.id, entity_type="USER", entity_id=1,
                         after={"email": "a@b.c", "password": "hunter2", "api_token": "abc", "nested": {"hashed_password": "zzz"}})
    assert "hunter2" not in e.after_data and "zzz" not in e.after_data and "abc" not in e.after_data
    assert "[REDACTED]" in e.after_data


def test_audit_entry_is_filled_in_with_context(db_session, test_officer_user, test_institution):
    d = make_fdr(db_session, test_institution, test_officer_user, "FDR-AUD-2")
    e = record_audit_log(db_session, deposit_id=d.id, action="CTX", actor_id=test_officer_user.id)
    assert e.actor_role == "OFFICER" and e.entity_type == "DEPOSIT" and e.entity_id == d.id
    assert e.institution_id == test_institution.id


def test_audit_api_access_control(client, institution_token, officer_token, admin_token):
    assert client.get("/api/audit-logs", headers=auth(institution_token)).status_code == 403
    assert client.get("/api/audit-logs/DEPOSIT/1", headers=auth(institution_token)).status_code == 403
    assert client.get("/api/audit-logs").status_code == 401
    assert client.get("/api/audit-logs", headers=auth(officer_token)).status_code == 200
    assert client.get("/api/audit-logs", headers=auth(admin_token)).status_code == 200


def test_audit_api_has_no_write_methods(client, admin_token):
    h = auth(admin_token)
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)("/api/audit-logs/1", headers=h).status_code in (404, 405)
    assert client.post("/api/audit-logs", json={}, headers=h).status_code == 405


def test_audit_api_filters_and_correlation_id(client, officer_token, institution_token, test_institution):
    cid = "corr-test-12345678"
    body = {"fdr_number": "FDR-CORR-1", "amount": "250000.00", "bank_name": "HDFC Bank",
            "issue_date": str(today()), "maturity_date": str(today() + timedelta(days=365))}
    r = client.post("/api/deposits", json=body, headers={**auth(institution_token), "X-Request-ID": cid})
    assert r.status_code == 201 and r.headers["X-Request-ID"] == cid
    dep_id = r.json()["id"]

    page = client.get("/api/audit-logs", params={"correlation_id": cid}, headers=auth(officer_token)).json()
    assert page["total"] >= 1 and all(i["correlation_id"] == cid for i in page["items"])
    item = page["items"][0]
    assert item["actor_role"] == "INSTITUTION" and item["entity_type"] == "DEPOSIT" and item["entity_id"] == dep_id

    hist = client.get(f"/api/audit-logs/DEPOSIT/{dep_id}", headers=auth(officer_token)).json()
    assert hist["total"] >= 1
    by_date = client.get("/api/audit-logs", params={"date_from": str(today()), "date_to": str(today()), "entity_type": "deposit"},
                         headers=auth(officer_token)).json()
    assert by_date["total"] >= 1
    assert client.get("/api/audit-logs", params={"date_from": str(today()), "date_to": str(today() - timedelta(days=1))},
                      headers=auth(officer_token)).status_code == 422
    assert client.get("/api/audit-logs", params={"entity_type": "NOPE"}, headers=auth(officer_token)).status_code == 422
    assert client.get("/api/audit-logs", params={"limit": 5000}, headers=auth(officer_token)).status_code == 422


# ---------------- reports ----------------
def test_fdr_summary_officer_sees_all_institutions(client, officer_token, world):
    data = client.get("/api/reports/fdr-summary", headers=auth(officer_token)).json()
    assert data["report"] == "fdr-summary" and data["generated_at"].endswith("Z")
    assert len(data["rows"]) == 2
    total = Decimal("100000.00") + Decimal("50000.50") + Decimal("20000.00") + Decimal("999999.00") + Decimal("70000.00")
    assert Decimal(str(data["summary"]["total_deposit_amount"])) == total
    row_a = next(r for r in data["rows"] if r["total_fdrs"] == 4)
    assert row_a["approaching_maturity"] == 1 and row_a["matured_needing_action"] == 1


def test_institution_is_scoped_to_itself_in_every_report(client, institution_token, second_institution, world):
    h = auth(institution_token)
    for path in ("fdr-summary", "maturity", "approvals", "document-status", "contract-coverage"):
        assert client.get(f"/api/reports/{path}", headers=h).status_code == 200, path
    data = client.get("/api/reports/fdr-summary", headers=h).json()
    assert [r["total_fdrs"] for r in data["rows"]] == [4]
    mat = client.get("/api/reports/maturity", headers=h).json()
    assert all(r["fdr_number"] != "FDR-R-B1" for r in mat["rows"])
    # Asking for another institution is refused, not silently ignored.
    assert client.get("/api/reports/fdr-summary", params={"institution_id": second_institution.id}, headers=h).status_code == 403
    assert client.get("/api/reports/export/csv", params={"report": "fdr-summary", "institution_id": second_institution.id},
                      headers=h).status_code == 403


def test_other_institutions_contract_is_not_reachable(client, institution_token, officer_token, second_institution, db_session):
    other = make_contract(db_session, second_institution, number="CON-OTHER")
    assert client.get("/api/reports/contract-coverage", params={"contract_id": other.id}, headers=auth(institution_token)).status_code == 404
    assert client.get("/api/reports/contract-coverage", params={"contract_id": other.id}, headers=auth(officer_token)).status_code == 200


def test_maturity_report_windows(client, officer_token, world):
    data = client.get("/api/reports/maturity", params={"days_ahead": 30}, headers=auth(officer_token)).json()
    cats = {r["fdr_number"]: r["category"] for r in data["rows"]}
    assert cats == {"FDR-R-NEAR": "APPROACHING", "FDR-R-B1": "APPROACHING", "FDR-R-MAT": "MATURED_ACTION_REQUIRED"}
    overdue = next(r for r in data["rows"] if r["fdr_number"] == "FDR-R-MAT")
    assert overdue["days_to_maturity"] == -5
    narrow = client.get("/api/reports/maturity", params={"days_ahead": 7}, headers=auth(officer_token)).json()
    assert {r["fdr_number"] for r in narrow["rows"] if r["category"] == "APPROACHING"} == {"FDR-R-B1"}
    ranged = client.get("/api/reports/maturity", params={"date_from": str(today()), "date_to": str(today() + timedelta(days=30))},
                        headers=auth(officer_token)).json()
    assert {r["fdr_number"] for r in ranged["rows"]} == {"FDR-R-NEAR", "FDR-R-B1"}


def test_report_filters_validated(client, officer_token):
    h = auth(officer_token)
    assert client.get("/api/reports/fdr-summary", params={"date_from": "2026-05-02", "date_to": "2026-05-01"}, headers=h).status_code == 422
    assert client.get("/api/reports/fdr-summary", params={"fdr_status": "NOT_A_STATUS"}, headers=h).status_code == 422
    assert client.get("/api/reports/approvals", params={"request_status": "MAYBE"}, headers=h).status_code == 422
    assert client.get("/api/reports/maturity", params={"days_ahead": 0}, headers=h).status_code == 422
    assert client.get("/api/reports/fdr-summary", params={"institution_id": 987654}, headers=h).status_code == 404
    assert client.get("/api/reports/fdr-summary", params={"fdr_status": "ACTIVE"}, headers=h).status_code == 200


def test_approvals_report_counts(client, officer_token, world, db_session, test_institution, test_institution_user, test_officer_user):
    f = world["fdrs"]
    for fdr, rtype, st in ((f["a_near"], RequestType.RENEWAL, RequestStatus.SUBMITTED),
                           (f["a_far"], RequestType.RELEASE, RequestStatus.UNDER_REVIEW),
                           (f["a_matured"], RequestType.RENEWAL, RequestStatus.APPROVED),
                           (f["b_near"], RequestType.RENEWAL, RequestStatus.REJECTED)):
        db_session.add(ApprovalRequest(deposit_id=fdr.id, institution_id=fdr.institution_id, request_type=rtype, status=st,
                                       requested_by_id=test_institution_user.id, decision_reason="because" if st in (RequestStatus.APPROVED, RequestStatus.REJECTED) else None))
    db_session.commit()
    s = client.get("/api/reports/approvals", headers=auth(officer_token)).json()["summary"]
    assert (s["pending_renewal"], s["pending_release"], s["pending_forfeiture"], s["approved"], s["rejected"]) == (1, 1, 0, 1, 1)
    only = client.get("/api/reports/approvals", params={"request_status": "APPROVED"}, headers=auth(officer_token)).json()
    assert len(only["rows"]) == 1 and only["rows"][0]["decision_reason"] == "because"


def test_document_status_report_lists_only_unverified(client, officer_token, world, db_session, test_institution_user):
    f = world["fdrs"]["a_near"]
    for i, st in enumerate((DocumentVerificationStatus.PENDING, DocumentVerificationStatus.VERIFIED, DocumentVerificationStatus.REJECTED)):
        db_session.add(Document(deposit_id=f.id, institution_id=f.institution_id, original_filename=f"d{i}.pdf",
                                stored_filename=f"stored-{i}.pdf", file_size=10, mime_type="application/pdf",
                                uploaded_by_id=test_institution_user.id, verification_status=st))
    db_session.commit()
    data = client.get("/api/reports/document-status", headers=auth(officer_token)).json()
    assert data["summary"]["awaiting_verification"] == 1 and data["summary"]["verified"] == 1 and data["summary"]["rejected"] == 1
    assert len(data["rows"]) == 1 and data["rows"][0]["file_name"] == "d0.pdf"
    assert "stored" not in str(data["rows"])  # no internal storage names or paths exposed


def test_contract_coverage_excludes_unverified_fdrs(client, officer_token, world):
    row = client.get("/api/reports/contract-coverage", headers=auth(officer_token)).json()["rows"][0]
    # Counted: 100000.00 + 50000.50. The 999,999 FDR is still PENDING_VERIFICATION and does not count.
    assert row["total_deposited"] == 150000.5 and row["sufficient"] is True and row["shortfall"] == 0
    assert row["linked_fdrs"] == 2


def test_contract_coverage_detects_insufficiency(client, officer_token, world, db_session):
    world["c1"].required_deposit_amount = Decimal("400000.00")
    db_session.commit()
    data = client.get("/api/reports/contract-coverage", headers=auth(officer_token)).json()
    row = data["rows"][0]
    assert row["sufficient"] is False and row["shortfall"] == 249999.5
    assert data["summary"]["insufficient_contracts"] == 1


# ---------------- CSV ----------------
def _read_csv(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text)))


def test_csv_has_clear_headers_and_generation_timestamp(client, officer_token, world):
    rows = _read_csv(client.get("/api/reports/export/csv", params={"report": "maturity"}, headers=auth(officer_token)))
    header = rows[0]
    assert "FDR Number" in header and "Days To Maturity (negative = overdue)" in header
    assert header[-1] == "Report Generated At (UTC)"
    assert all(r[-1].endswith("Z") for r in rows[1:]) and len(rows) == 4


def test_csv_escapes_formula_injection(client, officer_token, db_session, test_institution, test_institution_user):
    evil = ["=HYPERLINK(\"http://evil\",\"x\")", "+1+1", "-2+3", "@SUM(A1)", "\t=1+1"]
    for i, bank in enumerate(evil):
        make_fdr(db_session, test_institution, test_institution_user, f"FDR-EVIL-{i}", bank=bank, maturity_in=3)
    rows = _read_csv(client.get("/api/reports/export/csv", params={"report": "maturity"}, headers=auth(officer_token)))
    bank_col = rows[0].index("Bank")
    cells = [r[bank_col] for r in rows[1:]]
    assert len(cells) == len(evil)
    for cell in cells:
        assert cell.startswith("'"), cell
        assert not cell.startswith(("=", "+", "-", "@"))


def test_csv_unit_escape_rules_and_numbers_untouched():
    from backend.app.services.report_service import csv_safe, _cell
    assert csv_safe("=1") == "'=1" and csv_safe("hello") == "hello" and csv_safe("a=b") == "a=b"
    assert _cell(Decimal("-12.5")) == "-12.50"   # a real negative number is not a formula
    assert _cell(-5) == "-5"
    assert _cell(True) == "Yes" and _cell(None) == ""


def test_csv_scoping_validation_and_audit(client, institution_token, officer_token, world, db_session):
    rows = _read_csv(client.get("/api/reports/export/csv", params={"report": "fdr-summary"}, headers=auth(institution_token)))
    assert len(rows) == 2  # header + own institution only
    assert client.get("/api/reports/export/csv", params={"report": "nope"}, headers=auth(officer_token)).status_code == 422
    assert client.get("/api/reports/export/csv", params={"report": "maturity", "date_from": "2026-02-01", "date_to": "2026-01-01"},
                      headers=auth(officer_token)).status_code == 422
    assert client.get("/api/reports/export/csv", params={"report": "maturity"}).status_code == 401
    assert db_session.query(AuditLog).filter(AuditLog.action == "REPORT_EXPORTED").count() >= 1
