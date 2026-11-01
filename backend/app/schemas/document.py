from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from backend.app.models.document import DocumentType, DocumentVerificationStatus

class DocumentResponse(BaseModel):
    id: int
    deposit_id: int
    institution_id: int
    contract_id: Optional[int] = None
    original_filename: str
    document_type: DocumentType
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str
    upload_timestamp: datetime
    uploaded_by_id: int
    verification_status: DocumentVerificationStatus
    verified_by_id: Optional[int] = None
    verification_timestamp: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Computed relative download path (never exposes physical filesystem path)
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}

class DocumentVerifyRequest(BaseModel):
    remarks: Optional[str] = Field(None, max_length=1000, description="Officer verification notes or observation remarks")

class DocumentRejectRequest(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Mandatory clear explanation why the document was rejected"
    )
