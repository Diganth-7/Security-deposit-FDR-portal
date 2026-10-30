import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.auth.security import get_password_hash

# In-memory SQLite database for test suite isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture()
def test_institution(db_session):
    inst = Institution(
        aicte_id="1-TEST9999",
        name="Indian Institute of Engineering & Technology",
        state="Maharashtra",
        city="Mumbai",
        address="Powai, Mumbai",
        institute_type="Autonomous",
        contact_email="test.inst@iiet.ac.in",
        contact_phone="+91-22-25767000"
    )
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)
    return inst

@pytest.fixture()
def test_admin_user(db_session):
    admin = User(
        email="test_admin@aicte.gov.in",
        full_name="AICTE Test Administrator",
        hashed_password=get_password_hash("AdminPass123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture()
def test_officer_user(db_session):
    officer = User(
        email="test_officer@aicte.gov.in",
        full_name="Regional Test Officer",
        hashed_password=get_password_hash("OfficerPass123"),
        role=UserRole.OFFICER,
        is_active=True
    )
    db_session.add(officer)
    db_session.commit()
    db_session.refresh(officer)
    return officer

@pytest.fixture()
def test_institution_user(db_session, test_institution):
    user = User(
        email="test_registrar@iiet.ac.in",
        full_name="Registrar IIET",
        hashed_password=get_password_hash("RegistrarPass123"),
        role=UserRole.INSTITUTION,
        institution_id=test_institution.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture()
def admin_token(client, test_admin_user):
    res = client.post("/api/auth/login", json={
        "email": "test_admin@aicte.gov.in",
        "password": "AdminPass123"
    })
    return res.json()["access_token"]

@pytest.fixture()
def officer_token(client, test_officer_user):
    res = client.post("/api/auth/login", json={
        "email": "test_officer@aicte.gov.in",
        "password": "OfficerPass123"
    })
    return res.json()["access_token"]

@pytest.fixture()
def institution_token(client, test_institution_user):
    res = client.post("/api/auth/login", json={
        "email": "test_registrar@iiet.ac.in",
        "password": "RegistrarPass123"
    })
    return res.json()["access_token"]
