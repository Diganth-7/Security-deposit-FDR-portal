from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.schemas.institution import InstitutionCreate, InstitutionResponse
from backend.app.auth.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/institutions", tags=["Institutions"])

@router.get("", response_model=List[InstitutionResponse])
def list_institutions(
    state: Optional[str] = Query(None, description="Filter by State"),
    search: Optional[str] = Query(None, description="Search by name, city, or AICTE ID"),
    db: Session = Depends(get_db)
):
    """
    Lists AICTE approved technical institutions.
    Supports filtering by State and keyword searching.
    """
    query = db.query(Institution)
    if state:
        query = query.filter(Institution.state.ilike(f"%{state}%"))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Institution.name.ilike(search_pattern)) |
            (Institution.aicte_id.ilike(search_pattern)) |
            (Institution.city.ilike(search_pattern))
        )
    return query.order_by(Institution.name.asc()).all()

@router.post("", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    institution_in: InstitutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Creates a new AICTE affiliated institution record.
    Restricted to ADMIN role.
    """
    existing = db.query(Institution).filter(Institution.aicte_id == institution_in.aicte_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Institution with AICTE ID {institution_in.aicte_id} already exists."
        )

    inst = Institution(
        aicte_id=institution_in.aicte_id.strip(),
        name=institution_in.name.strip(),
        state=institution_in.state.strip(),
        city=institution_in.city.strip(),
        address=institution_in.address,
        institute_type=institution_in.institute_type,
        contact_email=institution_in.contact_email,
        contact_phone=institution_in.contact_phone
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

@router.get("/{institution_id}", response_model=InstitutionResponse)
def get_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets details of an institution by internal database ID."""
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution not found"
        )
    return inst
