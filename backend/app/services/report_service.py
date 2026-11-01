"""
Report builders. Each report is computed once here and returned in one shape:

    {"report", "title", "generated_at", "filters", "summary", "columns", "rows", "truncated"}

The JSON endpoints return it as-is and the CSV export writes the same rows, so the
two can never disagree. Callers must resolve role scoping first (see routers/reports.py):
an INSTITUTION user's filters always carry their own institution_id.
"""
import csv
import io
from dataclasses import dataclass, asdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from backend.app.models.approval_request import ApprovalRequest, RequestStatus, RequestType
from backend.app.models.contract import Contract
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.document import Document, DocumentVerificationStatus
from backend.app.services.contract_service import compute_contract_metrics
from backend.app.utils.clock import today, utc_now

MAX_ROWS = 10000
ACTIVE_SCOPE = (DepositStatus.ACTIVE, DepositStatus.VERIFIED, DepositStatus.MATURITY_APPROACHING)
OPEN_REQUEST_STATES = (RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW)
ZERO = Decimal("0")


@dataclass
class ReportFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    institution_id: Optional[int] = None
    contract_id: Optional[int] = None
    fdr_status: Optional[DepositStatus] = None
    request_status: Optional[RequestStatus] = None
    days_ahead: int = 30  # "approaching maturity" window

    def as_dict(self) -> dict:
        return {k: (v.value if isinstance(v, Enum) else (v.isoformat() if isinstance(v, date) else v))
                for k, v in asdict(self).items() if v is not None}


def _col(key: str, label: str) -> dict:
    return {"key": key, "label": label}


def _envelope(report: str, title: str, f: ReportFilters, columns: List[dict], rows: List[dict],
              summary: dict, truncated: bool = False) -> dict:
    return {
        "report": report, "title": title,
        "generated_at": utc_now().isoformat(timespec="seconds") + "Z",
        "filters": f.as_dict(), "summary": summary, "columns": columns, "rows": rows, "truncated": truncated,
    }


def _in_range(column, f: ReportFilters, query, as_datetime: bool = False):
    """Inclusive date range on a Date column, or on a DateTime column when as_datetime is set."""
    if f.date_from:
        low = datetime.combine(f.date_from, time.min) if as_datetime else f.date_from
        query = query.filter(column >= low)
    if f.date_to:
        if as_datetime:
            query = query.filter(column < datetime.combine(f.date_to + timedelta(days=1), time.min))
        else:
            query = query.filter(column <= f.date_to)
    return query


def _fetch(query) -> Tuple[list, bool]:
    """Rows up to MAX_ROWS, and whether more existed."""
    rows = query.limit(MAX_ROWS + 1).all()
    return rows[:MAX_ROWS], len(rows) > MAX_ROWS


def _deposit_query(db: Session, f: ReportFilters):
    q = db.query(Deposit).options(joinedload(Deposit.institution), joinedload(Deposit.contract))
    if f.institution_id:
        q = q.filter(Deposit.institution_id == f.institution_id)
    if f.contract_id:
        q = q.filter(Deposit.contract_id == f.contract_id)
    if f.fdr_status:
        q = q.filter(Deposit.status == f.fdr_status)
    return q


# --------------------------------------------------------------------------- #
# 1. Institution-wise FDR summary  (date range applies to FDR issue_date)
# --------------------------------------------------------------------------- #
def fdr_summary(db: Session, f: ReportFilters) -> dict:
    q = _in_range(Deposit.issue_date, f, _deposit_query(db, f))
    now = today()
    horizon = now + timedelta(days=f.days_ahead)
    by_inst: Dict[int, dict] = {}
    items, truncated = _fetch(q)
    for d in items:
        row = by_inst.setdefault(d.institution_id, {
            "institution_id": d.institution_id,
            "institution_name": d.institution.name if d.institution else "",
            "aicte_id": d.institution.aicte_id if d.institution else "",
            "total_fdrs": 0, "total_deposit_amount": ZERO, "active_fdrs": 0,
            "approaching_maturity": 0, "matured_needing_action": 0,
            "pending_renewal": 0, "pending_release": 0, "pending_forfeiture": 0,
        })
        row["total_fdrs"] += 1
        row["total_deposit_amount"] += Decimal(d.amount)
        if d.status in ACTIVE_SCOPE:
            row["active_fdrs"] += 1
            if now <= d.maturity_date <= horizon:
                row["approaching_maturity"] += 1
            elif d.maturity_date < now:
                row["matured_needing_action"] += 1
        elif d.status == DepositStatus.MATURED_ACTION_REQUIRED:
            row["matured_needing_action"] += 1
        elif d.status == DepositStatus.RENEWAL_REQUESTED:
            row["pending_renewal"] += 1
        elif d.status == DepositStatus.RELEASE_REQUESTED:
            row["pending_release"] += 1
        elif d.status == DepositStatus.FORFEITURE_REQUESTED:
            row["pending_forfeiture"] += 1
    rows = sorted(by_inst.values(), key=lambda r: r["institution_name"].lower())
    numeric = [k for k in (rows[0] if rows else {}) if k not in ("institution_id", "institution_name", "aicte_id")]
    summary = {k: sum((r[k] for r in rows), ZERO if k == "total_deposit_amount" else 0) for k in numeric}
    summary["institutions"] = len(rows)
    cols = [_col("institution_name", "Institution"), _col("aicte_id", "AICTE ID"), _col("total_fdrs", "Total FDRs"),
            _col("total_deposit_amount", "Total Deposit Amount (INR)"), _col("active_fdrs", "Active FDRs"),
            _col("approaching_maturity", f"Approaching Maturity (next {f.days_ahead} days)"),
            _col("matured_needing_action", "Matured - Action Required"), _col("pending_renewal", "Pending Renewal Requests"),
            _col("pending_release", "Pending Release Requests"), _col("pending_forfeiture", "Pending Forfeiture Requests")]
    return _envelope("fdr-summary", "Institution-wise FDR Summary", f, cols, rows, summary, truncated)


# --------------------------------------------------------------------------- #
# 2. Maturity report  (date range applies to maturity_date)
# --------------------------------------------------------------------------- #
def maturity(db: Session, f: ReportFilters) -> dict:
    now = today()
    horizon = now + timedelta(days=f.days_ahead)
    q = _in_range(Deposit.maturity_date, f, _deposit_query(db, f)).order_by(Deposit.maturity_date.asc())
    rows: List[dict] = []
    counts = {"APPROACHING": 0, "MATURED_ACTION_REQUIRED": 0}
    items, truncated = _fetch(q)
    for d in items:
        if d.status in ACTIVE_SCOPE and now <= d.maturity_date <= horizon:
            category = "APPROACHING"
        elif d.status == DepositStatus.MATURED_ACTION_REQUIRED or (d.status in ACTIVE_SCOPE and d.maturity_date < now):
            category = "MATURED_ACTION_REQUIRED"
        else:
            continue
        counts[category] += 1
        rows.append({
            "category": category, "fdr_id": d.id, "fdr_number": d.fdr_number,
            "institution_name": d.institution.name if d.institution else "", "bank_name": d.bank_name,
            "amount": Decimal(d.amount), "issue_date": d.issue_date, "maturity_date": d.maturity_date,
            "days_to_maturity": (d.maturity_date - now).days, "status": d.status,
            "contract_number": d.contract.contract_number if d.contract else "",
        })
    cols = [_col("category", "Category"), _col("fdr_number", "FDR Number"), _col("institution_name", "Institution"),
            _col("bank_name", "Bank"), _col("amount", "Amount (INR)"), _col("issue_date", "Issue Date"),
            _col("maturity_date", "Maturity Date"), _col("days_to_maturity", "Days To Maturity (negative = overdue)"),
            _col("status", "FDR Status"), _col("contract_number", "Contract")]
    summary = {"approaching": counts["APPROACHING"], "matured_action_required": counts["MATURED_ACTION_REQUIRED"],
               "approaching_window_days": f.days_ahead}
    return _envelope("maturity", "FDR Maturity Report", f, cols, rows, summary, truncated)


# --------------------------------------------------------------------------- #
# 3. Approvals report  (date range applies to the request's submission date)
# --------------------------------------------------------------------------- #
def approvals(db: Session, f: ReportFilters) -> dict:
    q = db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.deposit), joinedload(ApprovalRequest.institution),
        joinedload(ApprovalRequest.requested_by), joinedload(ApprovalRequest.decided_by))
    if f.institution_id:
        q = q.filter(ApprovalRequest.institution_id == f.institution_id)
    if f.contract_id:
        q = q.filter(ApprovalRequest.contract_id == f.contract_id)
    if f.request_status:
        q = q.filter(ApprovalRequest.status == f.request_status)
    if f.fdr_status:
        q = q.join(Deposit, Deposit.id == ApprovalRequest.deposit_id).filter(Deposit.status == f.fdr_status)
    q = _in_range(ApprovalRequest.submitted_at, f, q, as_datetime=True).order_by(ApprovalRequest.submitted_at.desc())
    rows, summary = [], {}
    for t in RequestType:
        summary[f"pending_{t.value.lower()}"] = 0
    summary.update({"approved": 0, "rejected": 0, "cancelled": 0})
    items, truncated = _fetch(q)
    for r in items:
        if r.status in OPEN_REQUEST_STATES:
            summary[f"pending_{r.request_type.value.lower()}"] += 1
        elif r.status == RequestStatus.APPROVED:
            summary["approved"] += 1
        elif r.status == RequestStatus.REJECTED:
            summary["rejected"] += 1
        elif r.status == RequestStatus.CANCELLED:
            summary["cancelled"] += 1
        final = r.status not in OPEN_REQUEST_STATES
        rows.append({
            "request_id": r.id, "request_type": r.request_type, "status": r.status,
            "fdr_number": r.deposit.fdr_number if r.deposit else "",
            "amount": Decimal(r.deposit.amount) if r.deposit else None,
            "institution_name": r.institution.name if r.institution else "",
            "requested_by": r.requested_by.full_name if r.requested_by else "",
            "submitted_at": r.submitted_at, "decided_at": r.reviewed_at if final else None,
            "decided_by": r.decided_by.full_name if r.decided_by else "", "decision_reason": r.decision_reason or "",
        })
    cols = [_col("request_id", "Request ID"), _col("request_type", "Type"), _col("status", "Status"),
            _col("fdr_number", "FDR Number"), _col("amount", "FDR Amount (INR)"), _col("institution_name", "Institution"),
            _col("requested_by", "Requested By"), _col("submitted_at", "Submitted At"), _col("decided_at", "Decided At"),
            _col("decided_by", "Decided By"), _col("decision_reason", "Decision Reason")]
    return _envelope("approvals", "Approval Requests Report", f, cols, rows, summary, truncated)


# --------------------------------------------------------------------------- #
# 4. Document verification status  (date range applies to upload date)
# --------------------------------------------------------------------------- #
def document_status(db: Session, f: ReportFilters) -> dict:
    q = db.query(Document).options(
        joinedload(Document.deposit), joinedload(Document.institution), joinedload(Document.uploaded_by))
    if f.institution_id:
        q = q.filter(Document.institution_id == f.institution_id)
    if f.contract_id:
        q = q.filter(Document.contract_id == f.contract_id)
    if f.fdr_status:
        q = q.join(Deposit, Deposit.id == Document.deposit_id).filter(Deposit.status == f.fdr_status)
    q = _in_range(Document.upload_timestamp, f, q, as_datetime=True).order_by(Document.upload_timestamp.asc())
    now = utc_now()
    summary = {s.value.lower(): 0 for s in DocumentVerificationStatus}
    rows: List[dict] = []
    items, truncated = _fetch(q)
    for d in items:
        summary[d.verification_status.value.lower()] += 1
        if d.verification_status == DocumentVerificationStatus.PENDING:
            rows.append({
                "document_id": d.id, "fdr_number": d.deposit.fdr_number if d.deposit else "",
                "institution_name": d.institution.name if d.institution else "",
                "document_type": d.document_type, "file_name": d.original_filename,
                "uploaded_by": d.uploaded_by.full_name if d.uploaded_by else "",
                "uploaded_at": d.upload_timestamp, "days_waiting": (now - d.upload_timestamp).days,
                "status": d.verification_status,
            })
    summary["awaiting_verification"] = summary["pending"]
    cols = [_col("document_id", "Document ID"), _col("fdr_number", "FDR Number"), _col("institution_name", "Institution"),
            _col("document_type", "Document Type"), _col("file_name", "File Name"), _col("uploaded_by", "Uploaded By"),
            _col("uploaded_at", "Uploaded At"), _col("days_waiting", "Days Waiting"), _col("status", "Verification Status")]
    return _envelope("document-status", "Documents Awaiting Verification", f, cols, rows, summary, truncated)


# --------------------------------------------------------------------------- #
# 5. Contract-wise coverage  (date range applies to contract start_date)
# --------------------------------------------------------------------------- #
def contract_coverage(db: Session, f: ReportFilters) -> dict:
    q = db.query(Contract).options(joinedload(Contract.institution), joinedload(Contract.deposits))
    if f.institution_id:
        q = q.filter(Contract.institution_id == f.institution_id)
    if f.contract_id:
        q = q.filter(Contract.id == f.contract_id)
    q = _in_range(Contract.start_date, f, q).order_by(Contract.contract_number.asc())
    rows, short = [], 0
    items, truncated = _fetch(q)
    for c in items:
        m = compute_contract_metrics(c)
        short += 0 if m["is_deposit_sufficient"] else 1
        rows.append({
            "contract_number": c.contract_number, "title": c.title,
            "institution_name": c.institution.name if c.institution else "", "status": c.status,
            "start_date": c.start_date, "end_date": c.end_date,
            "required_deposit": Decimal(str(m["required_deposit_amount"])),
            "total_deposited": Decimal(str(m["total_deposited_amount"])),
            "shortfall": Decimal(str(m["deposit_shortfall"])), "linked_fdrs": m["linked_deposits_count"],
            "sufficient": m["is_deposit_sufficient"],
        })
    cols = [_col("contract_number", "Contract Ref"), _col("title", "Title"), _col("institution_name", "Institution"),
            _col("status", "Contract Status"), _col("start_date", "Start Date"), _col("end_date", "End Date"),
            _col("required_deposit", "Required Deposit (INR)"), _col("total_deposited", "Total Deposited (INR)"),
            _col("shortfall", "Shortfall (INR)"), _col("linked_fdrs", "Counted FDRs"), _col("sufficient", "Sufficient")]
    summary = {"contracts": len(rows), "insufficient_contracts": short, "sufficient_contracts": len(rows) - short}
    return _envelope("contract-coverage", "Contract-wise Deposit Coverage", f, cols, rows, summary, truncated)


REPORTS = {
    "fdr-summary": fdr_summary, "maturity": maturity, "approvals": approvals,
    "document-status": document_status, "contract-coverage": contract_coverage,
}


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def csv_safe(value: str) -> str:
    """Neutralises spreadsheet formula injection: a cell that would start a formula is prefixed with '."""
    return "'" + value if value.startswith(_FORMULA_PREFIXES) else value


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Enum):
        return csv_safe(str(value.value))
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return str(value)
    return csv_safe(str(value))


def to_csv(report: dict) -> str:
    """CSV text: clear headers plus a 'Report Generated At (UTC)' column on every row."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    cols = report["columns"]
    w.writerow([c["label"] for c in cols] + ["Report Generated At (UTC)"])
    for row in report["rows"]:
        w.writerow([_cell(row.get(c["key"])) for c in cols] + [report["generated_at"]])
    return out.getvalue()
