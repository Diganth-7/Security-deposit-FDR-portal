import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AICTE Security Deposit and FDR Management Portal"
    PROJECT_CODE: str = "SIH26265"
    VERSION: str = "1.0.0-phase1"
    API_PREFIX: str = "/api"
    
    # Database configuration
    # Supports PostgreSQL as primary, with SQLite fallback for local testing
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "aicte_fdr_db")
    
    # DATABASE_URL can be explicitly supplied or computed
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # Fallback SQLite DB path when PostgreSQL is unavailable
    SQLITE_FALLBACK_URL: str = "sqlite:///./aicte_fdr.db"
    USE_SQLITE_FALLBACK_ON_ERROR: bool = True
    
    # Security & JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aicte_sih26265_super_secure_jwt_secret_key_2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    model_config = {
        "env_file": ".env",
        "extra": "allow"
    }

settings = Settings()
