import io
import pytest
from datetime import date, timedelta
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.document import Document, DocumentType, DocumentVerificationStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.notification import Notification

@pytest.fixture()
def sample_deposit(db_session, test_institution, test_institution_user):
    """Fixture creating an active FDR deposit for test_institution."""
    today = date.today()
    dep = Deposit(
        fdr_number="FDR-DOC-TEST-001",
        amount=1500000.0,
        bank_name="Punjab National Bank",
        branch_name="Connaught Place, New Delhi",
        ifsc_code="PUNB0000100",
        issue_date=today - timedelta(days=180),
        maturity_date=today + timedelta(days=185),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)
    return dep

@pytest.fixture()
def second_college_deposit(db_session, second_institution, second_institution_user):
    """Fixture creating an FDR deposit belonging to second_institution."""
    today = date.today()
    dep = Deposit(
        fdr_number="FDR-SECOND-COLLEGE-002",
        amount=2000000.0,
        bank_name="Canara Bank",
        branch_name="Shivajinagar Pune",
        ifsc_code="CNRB0001234",
        issue_date=today - timedelta(days=90),
        maturity_date=today + timedelta(days=275),
        status=DepositStatus.ACTIVE,
        institution_id=second_institution.id,
        submitted_by_id=second_institution_user.id
    )
    db_session.add(dep)
    db_session.commit()
    db_session.refresh(dep)
    return dep

def test_document_upload_pdf_success(client, institution_token, sample_deposit, db_session):
    """Test valid PDF FDR certificate upload with magic bytes verification."""
    # Valid PDF signature header
    valid_pdf_content = b"%PDF-1.4\n%AICTE FDR Certificate Mock Content\n%%EOF"
    file_bytes = io.BytesIO(valid_pdf_content)

    res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={
            "deposit_id": sample_deposit.id,
            "document_type": "FDR_CERTIFICATE"
        },
        files={
            "file": ("fdr_certificate_2026.pdf", file_bytes, "application/pdf")
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["deposit_id"] == sample_deposit.id
    assert data["original_filename"] == "fdr_certificate_2026.pdf"
    assert data["document_type"] == "FDR_CERTIFICATE"
    assert data["mime_type"] == "application/pdf"
    assert data["verification_status"] == "PENDING"
    assert data["download_url"] == f"/api/documents/{data['id']}/download"
    # Ensure physical path is not exposed in JSON
    assert "stored_filename" not in data
    assert "/storage" not in str(data)

    # Check Audit Log was recorded
    audit = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == sample_deposit.id,
        AuditLog.action == "DOCUMENT_UPLOADED"
    ).first()
    assert audit is not None
    assert "fdr_certificate_2026.pdf" in audit.details

def test_document_upload_png_and_jpg_success(client, institution_token, sample_deposit):
    """Test uploading valid image receipts (PNG and JPEG)."""
    # PNG upload
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    res_png = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "BANK_RECEIPT"},
        files={"file": ("bank_counterfoil.png", io.BytesIO(png_bytes), "image/png")}
    )
    assert res_png.status_code == 201
    assert res_png.json()["mime_type"] == "image/png"

    # JPG upload
    jpg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB"
    res_jpg = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "BANK_RECEIPT"},
        files={"file": ("acknowledgment.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}
    )
    assert res_jpg.status_code == 201
    assert res_jpg.json()["mime_type"] == "image/jpeg"

def test_document_upload_invalid_extension(client, institution_token, sample_deposit):
    """Test rejection of non-whitelisted extensions (e.g. .exe, .sh, .txt)."""
    fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "OTHER"},
        files={"file": ("malicious_payload.exe", fake_exe, "application/octet-stream")}
    )
    assert res.status_code == 400
    assert "Invalid file extension" in res.json()["detail"] or "Unsupported file format" in res.json()["detail"]

def test_document_upload_spoofed_file_type(client, institution_token, sample_deposit):
    """Test spoofed extension detection: a text file renamed to .pdf must fail magic byte check."""
    fake_pdf = io.BytesIO(b"This is a plain text file pretending to be a PDF")
    res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("spoofed.pdf", fake_pdf, "application/pdf")}
    )
    assert res.status_code == 400
    assert "magic bytes" in res.json()["detail"].lower()

def test_document_upload_cross_institution_forbidden(client, institution_token, second_college_deposit):
    """Test that Institution 1 cannot upload documents for an FDR belonging to Institution 2."""
    valid_pdf_content = b"%PDF-1.4\nAICTE Private Document\n%%EOF"
    res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": second_college_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("illegal_cross_upload.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]

def test_document_upload_nonexistent_fdr(client, institution_token):
    """Test uploading document for a non-existent deposit ID returns 404."""
    valid_pdf_content = b"%PDF-1.4\nContent\n%%EOF"
    res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": 999999, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("orphan.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    assert res.status_code == 404

def test_officer_pending_documents_queue(client, officer_token, institution_token, sample_deposit):
    """Test officer retrieving pending document queue and institution access restriction."""
    # 1. Upload a pending document
    valid_pdf_content = b"%PDF-1.4\nPending FDR Verification\n%%EOF"
    upload_res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("pending_fdr.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. Officer accesses /api/documents/pending -> 200 OK
    pending_res = client.get(
        "/api/documents/pending",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert pending_res.status_code == 200
    docs = pending_res.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Institution attempts to access /api/documents/pending -> 403 Forbidden
    inst_res = client.get(
        "/api/documents/pending",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert inst_res.status_code == 403

def test_document_download_and_isolation(client, institution_token, second_institution_token, officer_token, sample_deposit):
    """Test document download access control and data isolation."""
    valid_pdf_content = b"%PDF-1.4\nUnique Binary FDR Content 9982\n%%EOF"
    upload_res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("download_test.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Institution 1 downloads own document -> 200 OK
    down_res = client.get(
        f"/api/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert down_res.status_code == 200
    assert down_res.content == valid_pdf_content

    # Officer downloads document -> 200 OK
    officer_down = client.get(
        f"/api/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert officer_down.status_code == 200
    assert officer_down.content == valid_pdf_content

    # Institution 2 attempts to download Institution 1's document -> 403 Forbidden
    cross_down = client.get(
        f"/api/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {second_institution_token}"}
    )
    assert cross_down.status_code == 403

def test_officer_verify_document_workflow(client, officer_token, institution_token, sample_deposit, db_session):
    """Test officer verifying an FDR document, audit logging and notification creation."""
    valid_pdf_content = b"%PDF-1.4\nFDR Verification Test\n%%EOF"
    upload_res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("to_verify.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    doc_id = upload_res.json()["id"]

    # Institution attempts to verify own document -> 403 Forbidden
    inst_attempt = client.patch(
        f"/api/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {institution_token}"},
        json={"remarks": "Self verification attempt"}
    )
    assert inst_attempt.status_code == 403

    # Officer verifies document -> 200 OK
    verify_res = client.patch(
        f"/api/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"remarks": "Scrutiny complete: Bank seal and joint lien verified."}
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["verified_by_id"] is not None
    assert data["verification_timestamp"] is not None

    # Check Audit Log
    audit = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == sample_deposit.id,
        AuditLog.action == "DOCUMENT_VERIFIED"
    ).first()
    assert audit is not None
    assert "Bank seal and joint lien verified" in audit.details

def test_officer_reject_document_workflow(client, officer_token, institution_token, sample_deposit, db_session):
    """Test officer rejecting an FDR document, mandatory rejection reason, and audit trail."""
    valid_pdf_content = b"%PDF-1.4\nFDR Rejection Test\n%%EOF"
    upload_res = client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "BANK_RECEIPT"},
        files={"file": ("unclear_scan.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )
    doc_id = upload_res.json()["id"]

    # Reject without mandatory reason -> 422 Unprocessable Entity
    reject_no_reason = client.patch(
        f"/api/documents/{doc_id}/reject",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"rejection_reason": ""}
    )
    assert reject_no_reason.status_code == 422

    # Reject with valid mandatory reason -> 200 OK
    reason_msg = "Bank counterfoil is blurred and bank manager signature is missing."
    reject_res = client.patch(
        f"/api/documents/{doc_id}/reject",
        headers={"Authorization": f"Bearer {officer_token}"},
        json={"rejection_reason": reason_msg}
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["verification_status"] == "REJECTED"
    assert data["rejection_reason"] == reason_msg

    # Check Audit Log
    audit = db_session.query(AuditLog).filter(
        AuditLog.deposit_id == sample_deposit.id,
        AuditLog.action == "DOCUMENT_REJECTED"
    ).first()
    assert audit is not None
    assert reason_msg in audit.details

def test_list_fdr_documents_endpoints(client, institution_token, sample_deposit):
    """Test GET /api/deposits/{deposit_id}/documents and GET /api/documents?deposit_id={id}."""
    valid_pdf_content = b"%PDF-1.4\nAttachment 1\n%%EOF"
    client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {institution_token}"},
        data={"deposit_id": sample_deposit.id, "document_type": "FDR_CERTIFICATE"},
        files={"file": ("doc_list_test.pdf", io.BytesIO(valid_pdf_content), "application/pdf")}
    )

    # 1. Via GET /api/deposits/{id}/documents
    res1 = client.get(
        f"/api/deposits/{sample_deposit.id}/documents",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res1.status_code == 200
    assert len(res1.json()) >= 1
    assert res1.json()[0]["original_filename"] == "doc_list_test.pdf"

    # 2. Via GET /api/documents?deposit_id={id}
    res2 = client.get(
        f"/api/documents?deposit_id={sample_deposit.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res2.status_code == 200
    assert any(d["original_filename"] == "doc_list_test.pdf" for d in res2.json())
