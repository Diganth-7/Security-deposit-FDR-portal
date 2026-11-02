"""The demo seed must produce a consistent, varied data set and must not run in production."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import settings
from backend.app.database import Base
from backend.app.models.approval_request import ApprovalRequest, RequestStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.contract import Contract
from backend.app.models.deposit import Deposit
from backend.app.models.document import Document
from backend.app.models.notification import Notification
from backend.app.models.user import User
from backend.app.auth.security import verify_password
from backend.app.seed import seed_database
from backend.app.services.contract_service import compute_contract_metrics
from backend.app.services.storage_service import storage_service


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "DemoPass#2026x")
    monkeypatch.setattr(storage_service, "base_dir", tmp_path)
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    assert seed_database(factory) is True
    db = factory()
    yield db, tmp_path, factory
    db.close()


def test_seed_creates_varied_consistent_data(seeded):
    db, files, factory = seeded
    assert db.query(User).count() == 6
    assert db.query(Deposit).count() == 11 and db.query(Contract).count() == 5
    statuses = {r.status for r in db.query(ApprovalRequest)}
    assert {RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW, RequestStatus.APPROVED, RequestStatus.REJECTED} <= statuses
    assert db.query(Notification).count() > 0 and db.query(AuditLog).count() > 20
    assert len(list(files.glob("demo_doc_*.pdf"))) == db.query(Document).count()
    # at least one contract is under-covered (for the insufficient-deposit demo)
    assert any(not compute_contract_metrics(c)["is_deposit_sufficient"] for c in db.query(Contract))
    # accounts use the configured password, stored only as a hash
    admin = db.query(User).filter(User.email == "admin@aicte.gov.in").one()
    assert verify_password("DemoPass#2026x", admin.hashed_password) and admin.hashed_password != "DemoPass#2026x"


def test_seed_is_idempotent(seeded):
    db, _, factory = seeded
    assert seed_database(factory) is False
    assert db.query(User).count() == 6


def test_seed_refuses_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError):
        seed_database()
