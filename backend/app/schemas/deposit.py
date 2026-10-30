from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.models.deposit import DepositStatus
from app.schemas.institution import InstitutionResponse
from app.schemas.user import UserResponse

class DepositBase(BaseModel):
    amount: float = Field(..., gt=0, description="Security deposit value in INR (e.g., 1500000.00)")
    fdr_number: str = Field(..., min_length=4, max_length=100, description="Fixed Deposit Receipt Certificate Number")
    bank_name: str = Field(..., min_length=2, max_length=255, description="Issuing Scheduled Commercial Bank")
    branch_name: Optional[str] = Field(None, max_length=255)
    ifsc_code: Optional[str] = Field(None, min_length=4, max_length=50)
    issue_date: date = Field(..., description="Date FDR was issued by bank")
    maturity_date: date = Field(..., description="Date of FDR maturity")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.maturity_date <= self.issue_date:
            raise ValueError("Maturity date must be strictly after the issue date")
        return self

class DepositCreate(DepositBase):
    institution_id: Optional[int] = Field(
        None,
        description="Target institution ID. If submitted by an Institution user, automatically binds to their institution."
    )

class DepositStatusUpdate(BaseModel):
    status: DepositStatus = Field(..., description="New status (VERIFIED, ACTIVE, REJECTED, RELEASED, MATURED)")
    verification_remarks: Optional[str] = Field(None, max_length=1000, description="Audit note or verification remarks")

class DepositResponse(DepositBase):
    id: int
    status: DepositStatus
    institution_id: int
    submitted_by_id: int
    verified_by_id: Optional[int] = None
    verification_remarks: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Optional nested details
    institution: Optional[InstitutionResponse] = None
    submitted_by: Optional[UserResponse] = None
    verified_by: Optional[UserResponse] = None

    model_config = {"from_attributes": True}
