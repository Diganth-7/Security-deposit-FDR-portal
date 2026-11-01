import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.auth.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.models.deposit import Deposit
from backend.app.models.contract import Contract
from backend.app.models.document import Document, DocumentType, DocumentVerificationStatus
from backend.app.services.audit_service import record_audit_log
from backend.app.models.notification import Notification
from backend.app.schemas.document import DocumentResponse, DocumentVerifyRequest, DocumentRejectRequest
from backend.app.services.storage_service import storage_service
from backend.app.utils.clock import utc_now

logger = logging.getLogger("aicte_fdr.documents")

router = APIRouter(prefix="/documents", tags=["FDR Document Management"])

def _to_document_response(doc: Document) -> DocumentResponse:
    """Builds DocumentResponse safely without exposing local filesystem path."""
    return DocumentResponse(
        id=doc.id,
        deposit_id=doc.deposit_id,
        institution_id=doc.institution_id,
        contract_id=doc.contract_id,
        original_filename=doc.original_filename,
        document_type=doc.document_type,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        upload_timestamp=doc.upload_timestamp,
        uploaded_by_id=doc.uploaded_by_id,
        verification_status=doc.verification_status,
        verified_by_id=doc.verified_by_id,
        verification_timestamp=doc.verification_timestamp,
        rejection_reason=doc.rejection_reason,
        download_url=f"/api/documents/{doc.id}/download"
    )

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload FDR verification document"
)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, JPG, JPEG, PNG)"),
    deposit_id: int = Form(..., description="ID of associated FDR deposit"),
    document_type: DocumentType = Form(DocumentType.FDR_CERTIFICATE, description="Category of uploaded file"),
    contract_id: Optional[int] = Form(None, description="Optional contract ID associated with this document"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Securely uploads an FDR certificate, bank receipt, renewal document, or contract document.
    Validates mime type, magic byte signatures, file size, and enforces institution-level tenancy.
    """
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target deposit with ID {deposit_id} not found."
        )

    # Tenancy check: Institutions can only upload documents for their own FDRs
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id or deposit.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot upload documents for an FDR belonging to another institution."
            )

    # Optional contract tenancy check
    if contract_id is not None:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Specified contract ID {contract_id} not found."
            )
        if contract.institution_id != deposit.institution_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contract institution does not match the deposit institution."
            )

    # Save and validate file safely via storage service
    stored_filename, original_filename, file_size, mime_type = await storage_service.save_upload(file)

    try:
        doc = Document(
            deposit_id=deposit.id,
            institution_id=deposit.institution_id,
            contract_id=contract_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            document_type=document_type,
            file_size=file_size,
            mime_type=mime_type,
            upload_timestamp=utc_now(),
            uploaded_by_id=current_user.id,
            verification_status=DocumentVerificationStatus.PENDING
        )
        db.add(doc)
        db.flush()

        # Record Audit Log
        record_audit_log(
            db, deposit_id=deposit.id, action="DOCUMENT_UPLOADED", actor_id=current_user.id,
            details=f"Uploaded {document_type.value}: '{original_filename}' ({file_size} bytes). Document ID: {doc.id}.",
            entity_type="DOCUMENT", entity_id=doc.id, institution_id=deposit.institution_id,
            after={"verification_status": DocumentVerificationStatus.PENDING, "document_type": document_type}, commit=False,
        )
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        storage_service.delete_file(stored_filename)  # do not leave an orphaned file behind
        raise

    logger.info(f"User {current_user.email} uploaded document {doc.id} ({original_filename}) for deposit {deposit.fdr_number}")
    return _to_document_response(doc)

@router.get(
    "/pending",
    response_model=List[DocumentResponse],
    summary="List documents pending officer verification"
)
def list_pending_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer Scrutiny Queue: Lists all pending documents awaiting review across institutions.
    Strictly restricted to Officer and Admin users.
    """
    pending_docs = (
        db.query(Document)
        .filter(Document.verification_status == DocumentVerificationStatus.PENDING)
        .order_by(Document.upload_timestamp.asc())
        .all()
    )
    return [_to_document_response(doc) for doc in pending_docs]

@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="List documents with filters"
)
def list_documents(
    deposit_id: Optional[int] = Query(None, description="Filter by FDR ID"),
    institution_id: Optional[int] = Query(None, description="Filter by Institution ID"),
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentVerificationStatus] = Query(None, description="Filter by verification status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists uploaded documents.
    Institutions are strictly isolated to documents belonging to their own college.
    Officers and Admins can query across institutions.
    """
    query = db.query(Document)

    # Isolation by role
    if current_user.role == UserRole.INSTITUTION:
        query = query.filter(Document.institution_id == current_user.institution_id)
    elif institution_id is not None:
        query = query.filter(Document.institution_id == institution_id)

    if deposit_id is not None:
        query = query.filter(Document.deposit_id == deposit_id)
    if document_type is not None:
        query = query.filter(Document.document_type == document_type)
    if status is not None:
        query = query.filter(Document.verification_status == status)

    docs = query.order_by(Document.upload_timestamp.desc()).all()
    return [_to_document_response(doc) for doc in docs]

@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata"
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves metadata of a specific document, enforcing institution tenancy."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    if current_user.role == UserRole.INSTITUTION:
        if doc.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access documents belonging to another institution."
            )

    return _to_document_response(doc)

@router.get(
    "/{document_id}/download",
    summary="Download or view document file"
)
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Streams the requested document file securely.
    Guarantees isolation: Institutions can only download their own documents.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    if current_user.role == UserRole.INSTITUTION:
        if doc.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot download documents belonging to another institution."
            )

    file_path = storage_service.get_file_path(doc.stored_filename)

    record_audit_log(
        db, deposit_id=doc.deposit_id, action="DOCUMENT_DOWNLOADED", actor_id=current_user.id,
        details=f"Document '{doc.original_filename}' (ID: {doc.id}) downloaded.",
        entity_type="DOCUMENT", entity_id=doc.id, institution_id=doc.institution_id,
    )
    return FileResponse(
        path=str(file_path),
        media_type=doc.mime_type,
        filename=doc.original_filename,
        content_disposition_type="attachment"
    )

@router.patch(
    "/{document_id}/verify",
    response_model=DocumentResponse,
    summary="Officer marks document as VERIFIED"
)
def verify_document(
    document_id: int,
    payload: DocumentVerifyRequest = DocumentVerifyRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer review confirms that the FDR document has been examined and verified.
    Does not claim actual bank verification. Records audit trail.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    prior_status = doc.verification_status
    doc.verification_status = DocumentVerificationStatus.VERIFIED
    doc.verified_by_id = current_user.id
    doc.verification_timestamp = utc_now()
    doc.rejection_reason = None

    remarks_text = f" Remarks: {payload.remarks}" if payload.remarks else ""
    record_audit_log(
        db, deposit_id=doc.deposit_id, action="DOCUMENT_VERIFIED", actor_id=current_user.id,
        details=f"Document '{doc.original_filename}' (ID: {doc.id}) verified by Officer {current_user.full_name}.{remarks_text}",
        entity_type="DOCUMENT", entity_id=doc.id, institution_id=doc.institution_id,
        before={"verification_status": prior_status}, after={"verification_status": DocumentVerificationStatus.VERIFIED},
        commit=False,
    )

    # Send Notification to institution users
    inst_users = db.query(User).filter(
        User.institution_id == doc.institution_id,
        User.role == UserRole.INSTITUTION
    ).all()
    for u in inst_users:
        db.add(Notification(
            recipient_user_id=u.id,
            institution_id=doc.institution_id,
            deposit_id=doc.deposit_id,
            reminder_type="DOCUMENT_VERIFIED",
            title="Document Verified",
            message=f"Your uploaded document '{doc.original_filename}' has been reviewed and verified by AICTE.",
            created_at=utc_now()
        ))

    db.commit()
    db.refresh(doc)
    logger.info(f"Officer {current_user.email} verified document {doc.id}")
    return _to_document_response(doc)

@router.patch(
    "/{document_id}/reject",
    response_model=DocumentResponse,
    summary="Officer marks document as REJECTED"
)
def reject_document(
    document_id: int,
    payload: DocumentRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer rejects an FDR document with a mandatory rejection explanation.
    Records audit trail and notifies the submitting institution.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    prior_status = doc.verification_status
    doc.verification_status = DocumentVerificationStatus.REJECTED
    doc.verified_by_id = current_user.id
    doc.verification_timestamp = utc_now()
    doc.rejection_reason = payload.rejection_reason.strip()

    record_audit_log(
        db, deposit_id=doc.deposit_id, action="DOCUMENT_REJECTED", actor_id=current_user.id,
        details=f"Document '{doc.original_filename}' (ID: {doc.id}) rejected by Officer {current_user.full_name}. Reason: {doc.rejection_reason}",
        entity_type="DOCUMENT", entity_id=doc.id, institution_id=doc.institution_id,
        before={"verification_status": prior_status}, after={"verification_status": DocumentVerificationStatus.REJECTED},
        commit=False,
    )

    # Notify institution
    inst_users = db.query(User).filter(
        User.institution_id == doc.institution_id,
        User.role == UserRole.INSTITUTION
    ).all()
    for u in inst_users:
        db.add(Notification(
            recipient_user_id=u.id,
            institution_id=doc.institution_id,
            deposit_id=doc.deposit_id,
            reminder_type="DOCUMENT_REJECTED",
            title="Document Rejected - Action Required",
            message=f"Uploaded document '{doc.original_filename}' was rejected. Reason: {doc.rejection_reason}. Please upload a rectified document.",
            created_at=utc_now()
        ))

    db.commit()
    db.refresh(doc)
    logger.info(f"Officer {current_user.email} rejected document {doc.id} with reason: {doc.rejection_reason}")
    return _to_document_response(doc)
