"""Reports and CSV export. Every role may use them; what they see is scoped by role."""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.database import get_db
from backend.app.models.approval_request import RequestStatus
from backend.app.models.contract import Contract
from backend.app.models.deposit import DepositStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.services import report_service as rs
from backend.app.services.audit_service import record_audit_log

router = APIRouter(prefix="/reports", tags=["Reports & Export"])


def report_filters(
    date_from: Optional[date] = Query(None, description="Inclusive start date (field depends on the report)"),
    date_to: Optional[date] = Query(None, description="Inclusive end date"),
    institution_id: Optional[int] = Query(None, ge=1),
    contract_id: Optional[int] = Query(None, ge=1),
    fdr_status: Optional[DepositStatus] = Query(None),
    request_status: Optional[RequestStatus] = Query(None),
    days_ahead: int = Query(30, ge=1, le=365, description="Window for 'approaching maturity'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> rs.ReportFilters:
    """Validates filters and applies role scoping. Institutions are always limited to their own institution."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must not be after date_to.")

    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is not linked to an institution.")
        if institution_id is not None and institution_id != current_user.institution_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only report on your own institution.")
        institution_id = current_user.institution_id
    elif institution_id is not None and not db.query(Institution.id).filter(Institution.id == institution_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    if contract_id is not None:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract or (institution_id is not None and contract.institution_id != institution_id):
            # Same answer for "missing" and "someone else's" so existence is not revealed.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found in your scope.")

    return rs.ReportFilters(date_from=date_from, date_to=date_to, institution_id=institution_id, contract_id=contract_id,
                            fdr_status=fdr_status, request_status=request_status, days_ahead=days_ahead)


@router.get("/fdr-summary", summary="Institution-wise FDR summary (date range = FDR issue date)")
def fdr_summary(f: rs.ReportFilters = Depends(report_filters), db: Session = Depends(get_db)):
    return rs.fdr_summary(db, f)


@router.get("/maturity", summary="FDRs approaching maturity and matured FDRs needing action (date range = maturity date)")
def maturity(f: rs.ReportFilters = Depends(report_filters), db: Session = Depends(get_db)):
    return rs.maturity(db, f)


@router.get("/approvals", summary="Pending, approved and rejected requests (date range = submission date)")
def approvals(f: rs.ReportFilters = Depends(report_filters), db: Session = Depends(get_db)):
    return rs.approvals(db, f)


@router.get("/document-status", summary="Documents awaiting verification (date range = upload date)")
def document_status(f: rs.ReportFilters = Depends(report_filters), db: Session = Depends(get_db)):
    return rs.document_status(db, f)


@router.get("/contract-coverage", summary="Contract-wise deposit coverage (date range = contract start date)")
def contract_coverage(f: rs.ReportFilters = Depends(report_filters), db: Session = Depends(get_db)):
    return rs.contract_coverage(db, f)


@router.get("/export/csv", summary="Export any report as CSV")
def export_csv(
    report: str = Query(..., description="fdr-summary | maturity | approvals | document-status | contract-coverage"),
    f: rs.ReportFilters = Depends(report_filters),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CSV of the same data as the JSON report, with the same role scoping and filters."""
    builder = rs.REPORTS.get(report)
    if builder is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"report must be one of {sorted(rs.REPORTS)}.")
    data = builder(db, f)
    record_audit_log(
        db, action="REPORT_EXPORTED", actor_id=current_user.id, entity_type="REPORT",
        institution_id=f.institution_id or current_user.institution_id,
        details=f"CSV export of '{report}' ({len(data['rows'])} rows).", after={"filters": f.as_dict()},
    )
    filename = re.sub(r"[^a-z0-9\-]", "", report) + "-" + data["generated_at"][:10] + ".csv"
    return Response(
        content="﻿" + rs.to_csv(data),  # BOM so Excel reads UTF-8 correctly
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
