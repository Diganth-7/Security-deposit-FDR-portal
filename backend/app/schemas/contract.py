from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from backend.app.models.contract import ContractStatus
from backend.app.schemas.institution import InstitutionResponse

class ContractBase(BaseModel):
    contract_number: str = Field(..., min_length=3, max_length=100, description="Unique contract reference code")
    title: str = Field(..., min_length=2, max_length=255, description="Contract or statutory agreement title")
    description: Optional[str] = Field(None, max_length=2000)
    contract_type: str = Field("Institutional Affiliation", min_length=2, max_length=100)
    contract_amount: float = Field(0.0, ge=0.0, description="Total contract monetary valuation in INR")
    required_deposit_amount: float = Field(0.0, ge=0.0, description="Statutory FDR security deposit required in INR")
    start_date: date = Field(..., description="Contract commencement date")
    end_date: date = Field(..., description="Contract expiration/completion date")
    status: ContractStatus = ContractStatus.DRAFT

    @model_validator(mode="after")
    def validate_contract_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("Contract end date must be strictly after the start date")
        return self

class ContractCreate(ContractBase):
    institution_id: Optional[int] = Field(
        None,
        description="Target institution ID. If submitted by an Institution user, automatically binds to their institution."
    )

class ContractUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    contract_type: Optional[str] = Field(None, min_length=2, max_length=100)
    contract_amount: Optional[float] = Field(None, ge=0.0)
    required_deposit_amount: Optional[float] = Field(None, ge=0.0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[ContractStatus] = None

    @model_validator(mode="after")
    def validate_update_dates(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValueError("Contract end date must be strictly after the start date")
        return self

class ContractResponse(BaseModel):
    id: int
    contract_number: str
    title: str
    description: Optional[str] = None
    institution_id: int
    contract_type: str
    contract_amount: float
    required_deposit_amount: float
    start_date: date
    end_date: date
    status: ContractStatus
    created_at: datetime
    updated_at: datetime
    
    # Computed security deposit sufficiency metrics
    total_deposited_amount: float = 0.0
    is_deposit_sufficient: bool = True
    deposit_shortfall: float = 0.0
    linked_deposits_count: int = 0
    
    # Optional nested institution info
    institution: Optional[InstitutionResponse] = None

    model_config = {"from_attributes": True}
