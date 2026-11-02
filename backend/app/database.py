import logging
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings

logger = logging.getLogger("aicte_fdr.database")


def _normalize_url(db_url: str) -> str:
    """
    A bare postgresql:// URL means psycopg2 on older SQLAlchemy but psycopg v3 on 2.1+.
    requirements.txt installs psycopg2, so always name it explicitly.
    """
    url = make_url(db_url)
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg2")
    return url.render_as_string(hide_password=False)


def _make_engine(db_url: str):
    db_url = _normalize_url(db_url)
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})
    connect_args = {"connect_timeout": 5} if db_url.startswith("postgresql") else {}
    return create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=20, connect_args=connect_args)


def get_engine():
    """
    Builds the engine for DATABASE_URL.

    A SQLite URL is used as-is. For any other database the connection is verified
    at startup and a failure is raised with a clear message. The app only falls
    back to SQLite when ALLOW_SQLITE_FALLBACK=true is set explicitly (development
    convenience), and it says so loudly and reports it on /api/health.
    """
    db_url = settings.DATABASE_URL
    engine = _make_engine(db_url)
    if db_url.startswith("sqlite"):
        return engine, "sqlite"

    safe_url = engine.url.render_as_string(hide_password=True)
    try:
        with engine.connect():
            pass
        logger.info("Connected to database %s", safe_url)
        return engine, "postgresql" if db_url.startswith("postgresql") else engine.dialect.name
    except Exception as exc:
        if settings.ALLOW_SQLITE_FALLBACK and settings.APP_ENV != "production":
            logger.error(
                "DATABASE UNREACHABLE (%s): %s. ALLOW_SQLITE_FALLBACK is on, so using %s. "
                "Data written now will NOT be in your configured database.",
                safe_url, type(exc).__name__, settings.SQLITE_FALLBACK_URL,
            )
            return _make_engine(settings.SQLITE_FALLBACK_URL), "sqlite-fallback"
        raise RuntimeError(
            f"Cannot connect to the configured database ({safe_url}): {type(exc).__name__}. "
            "Start the database and check DATABASE_URL, or use "
            "DATABASE_URL=sqlite:///./aicte_fdr.db for local development."
        ) from exc


engine, db_backend_type = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding a database session per request.
    Closes the session after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
