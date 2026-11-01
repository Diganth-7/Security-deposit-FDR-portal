"""Contract deposit-sufficiency logic, shared by the contracts API and the reports."""
from decimal import Decimal

from backend.app.models.contract import Contract
from backend.app.models.deposit import DepositStatus

# FDRs that count toward a contract's required security deposit. Unverified FDRs
# (PENDING_VERIFICATION) and FDRs under forfeiture, released, closed or rejected do not.
COUNTED_STATUSES = (
    DepositStatus.ACTIVE,
    DepositStatus.MATURITY_APPROACHING,
    DepositStatus.VERIFIED,
    DepositStatus.MATURED_ACTION_REQUIRED,
    DepositStatus.MATURED,
    DepositStatus.RENEWAL_REQUESTED,
    DepositStatus.RELEASE_REQUESTED,
)

_TWO_PLACES = Decimal("0.01")


def compute_contract_metrics(contract: Contract) -> dict:
    """Total counted deposits, sufficiency and shortfall for one contract (exact Decimal maths)."""
    linked = [d for d in contract.deposits if d.status in COUNTED_STATUSES]
    total = sum((Decimal(d.amount) for d in linked), Decimal("0"))
    required = Decimal(contract.required_deposit_amount or 0)
    shortfall = max(Decimal("0"), required - total)
    return {
        "total_deposited_amount": float(total.quantize(_TWO_PLACES)),
        "is_deposit_sufficient": total >= required,
        "deposit_shortfall": float(shortfall.quantize(_TWO_PLACES)),
        "linked_deposits_count": len(linked),
        "required_deposit_amount": float(required.quantize(_TWO_PLACES)),
    }
