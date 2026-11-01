from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field
from backend.app.models.approval_request import RequestType, RequestStatus
from backend.app.schemas.common import MoneyOut

class RenewalRequestCreate(BaseModel):
    deposit_id: int = Field(..., description="Target FDR ID")
    requested_tenure_months: int = Field(..., ge=1, le=120, description="Renewal extension duration in months (e.g. 12, 36, 60)")
    description: Optional[str] = Field(None, max_length=1000, description="Justification and notes for FDR tenure renewal")
    supporting_document_ids: Optional[List[int]] = Field(None, description="Optional IDs of uploaded supporting verification documents")

class ReleaseRequestCreate(BaseModel):
    deposit_id: int = Field(..., description="Target FDR ID")
    justification: str = Field(..., min_length=5, max_length=1000, description="Reason for requesting security deposit release")
    compliance_reference: Optional[str] = Field(None, max_length=255, description="AICTE closure or compliance order number")
    description: Optional[str] = Field(None, max_length=1000, description="Additional context or notes")
    supporting_document_ids: Optional[List[int]] = Field(None, description="Optional IDs of uploaded closure / NOC documents")

class ForfeitureRequestCreate(BaseModel):
    deposit_id: int = Field(..., description="Target FDR ID")
    violation_reason: str = Field(..., min_length=5, max_length=1000, description="Statutory or regulatory violation justifying forfeiture")
    statutory_clause: str = Field(..., min_length=3, max_length=255, description="Clause in AICTE Approval Process Handbook (e.g. Clause 4.8.1)")
    description: Optional[str] = Field(None, max_length=1000, description="Notice reference and inspection details")
    supporting_document_ids: Optional[List[int]] = Field(None, description="Optional IDs of show cause / penalty orders")

class AssignOfficerRequest(BaseModel):
    officer_id: Optional[int] = Field(None, description="Target Officer User ID (defaults to self-assign if omitted)")

class ApprovalDecisionRequest(BaseModel):
    decision_remarks: Optional[str] = Field(None, max_length=1000, description="Officer scrutiny audit remarks")
    extended_maturity_date: Optional[date] = Field(None, description="New approved maturity date for renewal requests")

class RejectionDecisionRequest(BaseModel):
    rejection_reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Mandatory clear explanation why the approval request is rejected"
    )

class ApprovalRequestResponse(BaseModel):
    id: int
    deposit_id: int
    institution_id: int
    contract_id: Optional[int] = None
    request_type: RequestType
    status: RequestStatus
    description: Optional[str] = None
    supporting_document_ids: Optional[str] = None
    
    requested_tenure_months: Optional[int] = None
    extended_maturity_date: Optional[date] = None
    compliance_reference: Optional[str] = None
    statutory_clause: Optional[str] = None
    violation_reason: Optional[str] = None
    
    requested_by_id: int
    assigned_officer_id: Optional[int] = None
    decided_by_id: Optional[int] = None
    
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    decision_reason: Optional[str] = None

    # Contextual metadata for UI & Officer Scrutiny Queue
    fdr_number: Optional[str] = None
    deposit_amount: Optional[MoneyOut] = None
    institution_name: Optional[str] = None
    requested_by_name: Optional[str] = None
    assigned_officer_name: Optional[str] = None
    decided_by_name: Optional[str] = None

    model_config = {"from_attributes": True}
