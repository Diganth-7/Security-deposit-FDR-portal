"""
Demo data for the prototype (development only; refuses to run in production).

Everything here is invented: institutions, people, FDR numbers and amounts are
fictional and no real personal or banking data is used. Accounts share the
password in DEMO_PASSWORD (or a random one that is logged once if it is unset);
no password is stored in source code.

Records are created by calling the real workflow code (approval requests, audit
trail, reminders), so statuses, notifications and audit history are consistent with
what the API would have produced. The seed runs only on an empty database.
"""
import logging
import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Callable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.auth.security import get_password_hash
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.document import Document, DocumentType, DocumentVerificationStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.routers import approval_requests as wf
from backend.app.services.audit_service import record_audit_log
from backend.app.services.reminder_service import process_maturity_reminders
from backend.app.services.storage_service import storage_service
from backend.app.utils.clock import today, utc_now

logger = logging.getLogger("aicte_fdr.seed")

# A tiny but valid PDF so demo documents can really be downloaded.
_DEMO_PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
             b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")

DEMO_ACCOUNTS = [  # (email, role, label) - shown in the README and on the login page
    ("admin@aicte.gov.in", "ADMIN", "Administrator"),
    ("officer.sharma@aicte.gov.in", "OFFICER", "Scrutiny Officer"),
    ("officer.rao@aicte.gov.in", "OFFICER", "Second Officer (for maker-checker)"),
    ("registrar@dtu.ac.in", "INSTITUTION", "Delhi Technological University"),
    ("finance@coep.ac.in", "INSTITUTION", "College of Engineering, Pune"),
    ("accounts@bmsce.ac.in", "INSTITUTION", "BMS College of Engineering"),
]


def seed_database(session_factory: Optional[Callable[[], Session]] = None) -> bool:
    """Seeds demo data into an empty database. Returns True if anything was created."""
    if settings.APP_ENV == "production":
        raise RuntimeError("Demo seeding is disabled in production.")
    db: Session = (session_factory or SessionLocal)()
    try:
        if db.query(User).count() > 0 or db.query(Institution).count() > 0:
            logger.info("Database already has data; demo seed skipped.")
            return False
        _seed(db)
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed(db: Session) -> None:
    password = settings.DEMO_PASSWORD
    generated = not password
    if generated:
        password = secrets.token_urlsafe(9) + "aA1"
    pw_hash = get_password_hash(password)
    t = today()

    def inst(aicte_id, name, state, city, address, kind, email, phone):
        row = Institution(aicte_id=aicte_id, name=name, state=state, city=city, address=address,
                          institute_type=kind, contact_email=email, contact_phone=phone)
        db.add(row)
        db.flush()
        return row

    dtu = inst("1-3329182741", "Delhi Technological University (DTU)", "Delhi", "New Delhi",
               "Shahbad Daulatpur, Main Bawana Road, Delhi 110042", "Government State University", "registrar@dtu.ac.in", "+91-11-27871018")
    coep = inst("1-4581290332", "College of Engineering, Pune (COEP Tech)", "Maharashtra", "Pune",
                "Wellesley Rd, Shivajinagar, Pune 411005", "Unitary Public University", "accounts@coep.ac.in", "+91-20-25507000")
    bms = inst("1-9872145561", "BMS College of Engineering", "Karnataka", "Bengaluru",
               "Bull Temple Rd, Basavanagudi, Bengaluru 560019", "Autonomous Private Aided", "finance@bmsce.ac.in", "+91-80-26622130")

    def user(email, name, role, inst_id=None):
        row = User(email=email, full_name=name, hashed_password=pw_hash, role=role, institution_id=inst_id, is_active=True)
        db.add(row)
        db.flush()
        return row

    admin = user("admin@aicte.gov.in", "Dr. Alok Verma (Director Approval)", UserRole.ADMIN)
    off1 = user("officer.sharma@aicte.gov.in", "Rajesh Sharma (Regional Scrutiny Officer)", UserRole.OFFICER)
    off2 = user("officer.rao@aicte.gov.in", "Meera Rao (Senior Scrutiny Officer)", UserRole.OFFICER)
    u_dtu = user("registrar@dtu.ac.in", "Prof. S. K. Garg (DTU Registrar)", UserRole.INSTITUTION, dtu.id)
    u_coep = user("finance@coep.ac.in", "Dr. V. N. Pande (Finance Officer COEP)", UserRole.INSTITUTION, coep.id)
    u_bms = user("accounts@bmsce.ac.in", "Ms. R. Iyer (Accounts Head BMSCE)", UserRole.INSTITUTION, bms.id)

    def contract(number, title, inst_row, required, amount, status, start_days, end_days):
        row = Contract(contract_number=number, title=title, institution_id=inst_row.id,
                       contract_type="Institutional Affiliation", contract_amount=Decimal(amount),
                       required_deposit_amount=Decimal(required), start_date=t + timedelta(days=start_days),
                       end_date=t + timedelta(days=end_days), status=status,
                       description="Fictional demo contract.")
        db.add(row)
        db.flush()
        record_audit_log(db, action="CONTRACT_CREATED", actor_id=admin.id, entity_type="CONTRACT", entity_id=row.id,
                         institution_id=inst_row.id, details=f"Contract {number} created.", commit=False)
        return row

    c_dtu = contract("DTU-AFF-2026-001", "DTU Affiliation 2026-29", dtu, "5000000.00", "80000000.00", ContractStatus.ACTIVE, -200, 900)
    c_dtu_done = contract("DTU-AFF-2023-014", "DTU Short Course 2023-26 (completed)", dtu, "1500000.00", "20000000.00", ContractStatus.COMPLETED, -1000, -30)
    c_coep = contract("COEP-AFF-2026-007", "COEP Affiliation 2026-29", coep, "9000000.00", "90000000.00", ContractStatus.ACTIVE, -150, 950)
    c_coep_bad = contract("COEP-AFF-2022-003", "COEP Programme 2022-25 (terminated)", coep, "1000000.00", "15000000.00", ContractStatus.TERMINATED, -1200, -20)
    c_bms = contract("BMS-AFF-2025-011", "BMSCE Programme 2025 (expired)", bms, "2000000.00", "30000000.00", ContractStatus.EXPIRED, -900, -60)

    def fdr(number, amount, bank, branch, ifsc, issue_days, mat_days, status, inst_row, by, contract_row=None, verified=True, remarks=None):
        row = Deposit(fdr_number=number, amount=Decimal(amount), bank_name=bank, branch_name=branch, ifsc_code=ifsc,
                      issue_date=t + timedelta(days=issue_days), maturity_date=t + timedelta(days=mat_days),
                      status=status, institution_id=inst_row.id, submitted_by_id=by.id,
                      contract_id=contract_row.id if contract_row else None,
                      contract_reference=contract_row.contract_number if contract_row else None,
                      verified_by_id=off1.id if verified else None, verified_at=utc_now() - timedelta(days=30) if verified else None,
                      verification_remarks=remarks if verified else None)
        db.add(row)
        db.flush()
        record_audit_log(db, deposit_id=row.id, action="FDR_SUBMITTED", actor_id=by.id,
                         details=f"FDR {number} submitted for INR {amount}.", commit=False)
        if verified:
            record_audit_log(db, deposit_id=row.id, action="FDR_VERIFIED", actor_id=off1.id,
                             details=f"FDR {number} verified by officer (document check only; no bank integration).", commit=False)
        return row

    A = fdr("FDR-SBI-2025-99410", "3500000.00", "State Bank of India", "Delhi University Branch", "SBIN0001067", -180, 1095, DepositStatus.ACTIVE, dtu, u_dtu, c_dtu, remarks="Certificate checked against uploaded document.")
    B = fdr("FDR-HDFC-2025-30DAYS", "4000000.00", "HDFC Bank", "Kashmere Gate Delhi", "HDFC0000030", -335, 30, DepositStatus.ACTIVE, dtu, u_dtu, c_dtu)
    C = fdr("FDR-PNB-2026-10482", "1500000.00", "Punjab National Bank", "Connaught Place New Delhi", "PUNB0000100", -14, 1825, DepositStatus.PENDING_VERIFICATION, dtu, u_dtu, verified=False)
    D = fdr("FDR-ICICI-2023-RELEASE", "1500000.00", "ICICI Bank", "Rohini Delhi", "ICIC0000011", -1000, 60, DepositStatus.ACTIVE, dtu, u_dtu, c_dtu_done)
    E = fdr("FDR-BOB-2025-78219", "5000000.00", "Bank of Baroda", "Shivajinagar Pune", "BARB0SHIVAJ", -400, 1460, DepositStatus.VERIFIED, coep, u_coep, c_coep)
    F = fdr("FDR-AXIS-2025-07DAYS", "2500000.00", "Axis Bank", "FC Road Pune", "UTIB0000077", -358, 7, DepositStatus.ACTIVE, coep, u_coep, c_coep)
    G = fdr("FDR-UBI-2022-FORFEIT", "1000000.00", "Union Bank of India", "Deccan Pune", "UBIN0531120", -1100, 500, DepositStatus.ACTIVE, coep, u_coep, c_coep_bad)
    H = fdr("FDR-KOT-2025-01DAY", "1200000.00", "Kotak Mahindra Bank", "Camp Pune", "KKBK0000001", -364, 1, DepositStatus.ACTIVE, coep, u_coep)
    I = fdr("FDR-CAN-2024-33120", "2000000.00", "Canara Bank", "Basavanagudi Bengaluru", "CNRB0000542", -800, -70, DepositStatus.MATURED_ACTION_REQUIRED, bms, u_bms, c_bms)
    J = fdr("FDR-SBI-2025-RENEW", "3000000.00", "State Bank of India", "Jayanagar Bengaluru", "SBIN0000876", -345, 20, DepositStatus.ACTIVE, bms, u_bms)
    K = fdr("FDR-IOB-2025-REJECT", "800000.00", "Indian Overseas Bank", "Malleswaram Bengaluru", "IOBA0000045", -300, 400, DepositStatus.ACTIVE, bms, u_bms)

    def doc(deposit, uploader, kind, status, name, reason=None):
        n = db.query(Document).count() + 1
        stored = f"demo_doc_{n:03d}_{secrets.token_hex(4)}.pdf"
        (storage_service.base_dir / stored).write_bytes(_DEMO_PDF)
        row = Document(deposit_id=deposit.id, institution_id=deposit.institution_id, original_filename=name, stored_filename=stored,
                       document_type=kind, file_size=len(_DEMO_PDF), mime_type="application/pdf", uploaded_by_id=uploader.id,
                       verification_status=status, rejection_reason=reason,
                       verified_by_id=off1.id if status != DocumentVerificationStatus.PENDING else None,
                       verification_timestamp=utc_now() if status != DocumentVerificationStatus.PENDING else None)
        db.add(row)
        db.flush()
        record_audit_log(db, deposit_id=deposit.id, action="DOCUMENT_UPLOADED", actor_id=uploader.id, entity_type="DOCUMENT",
                         entity_id=row.id, institution_id=deposit.institution_id, details=f"Uploaded {kind.value}: '{name}'.", commit=False)
        if status != DocumentVerificationStatus.PENDING:
            record_audit_log(db, deposit_id=deposit.id, action=f"DOCUMENT_{status.value}", actor_id=off1.id, entity_type="DOCUMENT",
                             entity_id=row.id, institution_id=deposit.institution_id, details=reason or "Checked by officer.", commit=False)
        return row

    V, P, R = DocumentVerificationStatus.VERIFIED, DocumentVerificationStatus.PENDING, DocumentVerificationStatus.REJECTED
    doc(A, u_dtu, DocumentType.FDR_CERTIFICATE, V, "fdr-certificate-sbi-99410.pdf")
    doc(B, u_dtu, DocumentType.FDR_CERTIFICATE, V, "fdr-certificate-hdfc.pdf")
    doc(B, u_dtu, DocumentType.BANK_RECEIPT, P, "bank-receipt-hdfc.pdf")
    doc(C, u_dtu, DocumentType.FDR_CERTIFICATE, P, "fdr-certificate-pnb.pdf")
    doc(D, u_dtu, DocumentType.RELEASE_DOCUMENT, V, "closure-order-2023-014.pdf")
    doc(E, u_coep, DocumentType.FDR_CERTIFICATE, V, "fdr-certificate-bob.pdf")
    doc(F, u_coep, DocumentType.FDR_CERTIFICATE, P, "fdr-certificate-axis.pdf")
    doc(G, u_coep, DocumentType.CONTRACT_DOCUMENT, V, "show-cause-and-order.pdf")
    doc(I, u_bms, DocumentType.FDR_CERTIFICATE, R, "fdr-certificate-canara-scan.pdf", reason="Scan is unreadable; please upload a clear copy.")
    doc(J, u_bms, DocumentType.FDR_CERTIFICATE, V, "fdr-certificate-sbi-renew.pdf")
    doc(K, u_bms, DocumentType.FDR_CERTIFICATE, P, "fdr-certificate-iob.pdf")
    db.commit()

    # Approval requests, created through the real workflow so every rule, audit entry and notification applies.
    def run(fn, *args, **kwargs):
        try:
            return fn(*args, db=db, **kwargs)
        except HTTPException as exc:  # a demo scenario must not stop the whole seed
            logger.warning("Demo scenario skipped (%s): %s", getattr(fn, "__name__", fn), exc.detail)
            return None

    r_release = run(wf.submit_release_request, wf.ReleaseRequestCreate(
        deposit_id=D.id, justification="Short course completed and closure order issued.", compliance_reference="AICTE/CLOSURE/2026/114"), current_user=u_dtu)
    if r_release:
        run(wf.assign_officer, r_release.id, wf.AssignOfficerRequest(officer_id=off1.id), current_user=off1)
    run(wf.submit_renewal_request, wf.RenewalRequestCreate(
        deposit_id=B.id, requested_tenure_months=24, description="Renewal for the next affiliation cycle."), current_user=u_dtu)
    run(wf.submit_forfeiture_request, wf.ForfeitureRequestCreate(
        deposit_id=G.id, violation_reason="Programme terminated after repeated non-compliance notices.",
        statutory_clause="Clause 4.8.2 (demo reference)", description="Contract terminated; see order."), current_user=off2)
    r_renew = run(wf.submit_renewal_request, wf.RenewalRequestCreate(
        deposit_id=J.id, requested_tenure_months=12, description="Routine renewal."), current_user=u_bms)
    if r_renew:
        run(wf.approve_request, r_renew.id, wf.ApprovalDecisionRequest(decision_remarks="Bank lien letter checked; renewal approved."), current_user=off1)
    r_rej = run(wf.submit_release_request, wf.ReleaseRequestCreate(
        deposit_id=K.id, justification="Requesting early return of the deposit."), current_user=u_bms)
    if r_rej:
        run(wf.reject_request, r_rej.id, wf.RejectionDecisionRequest(
            rejection_reason="No closure order or compliance reference supplied."), current_user=off2)

    process_maturity_reminders(db)  # creates the approaching-maturity notifications
    db.commit()

    logger.info("Demo data created: 3 institutions, 6 accounts, 5 contracts, 11 FDRs, 11 documents, 5 requests.")
    lines = [f"  {e:<32} {r:<12} {label}" for e, r, label in DEMO_ACCOUNTS]
    logger.info("Demo accounts (all use the same password):\n%s", "\n".join(lines))
    if generated:
        logger.warning("DEMO_PASSWORD was not set. Generated demo password (shown once): %s", password)
