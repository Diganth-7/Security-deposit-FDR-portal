import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

logger = logging.getLogger("aicte_fdr.database")

def get_engine():
    """
    Creates SQLAlchemy Engine with PostgreSQL configuration.
    Falls back gracefully to SQLite if PostgreSQL server is unreachable in local dev/demo.
    """
    db_url = settings.DATABASE_URL
    try:
        if db_url.startswith("sqlite"):
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False}
            )
            return engine, "sqlite"
        else:
            # Test PostgreSQL connection with short timeout
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                connect_args={"connect_timeout": 3} if "postgresql" in db_url else {}
            )
            # Verify connectivity
            with engine.connect() as conn:
                logger.info("Successfully connected to PostgreSQL database.")
            return engine, "postgresql"
    except Exception as e:
        if settings.USE_SQLITE_FALLBACK_ON_ERROR:
            logger.warning(
                f"PostgreSQL connection to {db_url} failed ({e}). "
                f"Falling back to local SQLite engine: {settings.SQLITE_FALLBACK_URL}"
            )
            fallback_engine = create_engine(
                settings.SQLITE_FALLBACK_URL,
                connect_args={"check_same_thread": False}
            )
            return fallback_engine, "sqlite-fallback"
        raise e

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
