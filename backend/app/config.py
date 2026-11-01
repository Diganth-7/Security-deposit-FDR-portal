"""Application settings, read from environment variables or a local .env file.

Secure by default:
* There is no built-in JWT secret. In production a strong SECRET_KEY is required;
  in development a random one is generated per process (tokens stop working on
  restart, which is fine for local work).
* There are no built-in database credentials. DATABASE_URL defaults to a local
  SQLite file for development only.
* A failing PostgreSQL connection is an error, not a silent switch to SQLite,
  unless ALLOW_SQLITE_FALLBACK=true is set explicitly (never in production).
"""
import logging
import secrets
from typing import Optional, Set

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("aicte_fdr.config")

# The SECRET_KEY that used to be committed in this repository. Anything equal to
# it is treated as compromised.
_LEAKED_DEFAULT_SECRETS = {"aicte_sih26265_super_secure_jwt_secret_key_2026"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "AICTE Security Deposit and FDR Management Portal"
    PROJECT_CODE: str = "SIH26265"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"

    # development | test | production
    APP_ENV: str = "development"
    # IANA zone for maturity dates, e.g. "Asia/Kolkata". Empty = server local date.
    APP_TIMEZONE: str = ""

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./aicte_fdr.db"
    ALLOW_SQLITE_FALLBACK: bool = False
    SQLITE_FALLBACK_URL: str = "sqlite:///./aicte_fdr.db"

    # --- Security -----------------------------------------------------------
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    ALLOW_PRIVILEGED_SELF_REGISTRATION: bool = False
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # --- Documents ----------------------------------------------------------
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024
    UPLOAD_STORAGE_DIR: str = "storage/documents"

    # --- Reminders ----------------------------------------------------------
    ENABLE_REMINDER_SCHEDULER: bool = True
    REMINDER_RUN_TIME: str = "00:10"  # HH:MM in the app timezone
    ALLOW_REMINDER_DATE_OVERRIDE: bool = False

    # --- Demo / diagnostics (None = derive from APP_ENV) --------------------
    SEED_DEMO_DATA: Optional[bool] = None
    ENABLE_TEST_RUNNER: Optional[bool] = None

    # --- Approval workflow permissions (comma separated roles) --------------
    # Who may SUBMIT each kind of request ...
    APPROVAL_SUBMIT_ROLES_RENEWAL: str = "INSTITUTION,ADMIN"
    APPROVAL_SUBMIT_ROLES_RELEASE: str = "INSTITUTION,ADMIN"
    APPROVAL_SUBMIT_ROLES_FORFEITURE: str = "OFFICER,ADMIN"
    # ... and who may DECIDE (approve/reject) each kind. The requester can never
    # decide their own request, whatever is configured here.
    APPROVAL_DECIDE_ROLES_RENEWAL: str = "OFFICER,ADMIN"
    APPROVAL_DECIDE_ROLES_RELEASE: str = "OFFICER,ADMIN"
    APPROVAL_DECIDE_ROLES_FORFEITURE: str = "OFFICER,ADMIN"
    # At least one VERIFIED document on the FDR is needed before approving.
    APPROVAL_REQUIRE_VERIFIED_DOCUMENT: bool = True
    # Forfeiture approval needs the FDR linked to an ACTIVE/TERMINATED/EXPIRED contract.
    FORFEITURE_REQUIRES_CONTRACT: bool = True

    @model_validator(mode="after")
    def _apply_environment_rules(self):
        env = self.APP_ENV.lower()
        self.APP_ENV = env
        is_prod = env == "production"

        key = self.SECRET_KEY
        weak = (not key) or len(key) < 32 or key in _LEAKED_DEFAULT_SECRETS or "CHANGE_ME" in key.upper()
        if weak:
            if is_prod:
                raise ValueError(
                    "SECRET_KEY must be set to a random value of at least 32 characters in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
            if key:
                logger.warning("SECRET_KEY is weak or a known default; replacing it with a random per-process key.")
            self.SECRET_KEY = secrets.token_urlsafe(48)
            logger.warning("No strong SECRET_KEY configured: using an ephemeral key (tokens reset on restart).")

        if is_prod and self.ALLOW_SQLITE_FALLBACK:
            raise ValueError("ALLOW_SQLITE_FALLBACK must not be enabled in production.")

        if self.SEED_DEMO_DATA is None:
            self.SEED_DEMO_DATA = env == "development"
        if self.ENABLE_TEST_RUNNER is None:
            self.ENABLE_TEST_RUNNER = env == "development"
        if env == "test":
            self.ENABLE_REMINDER_SCHEDULER = False
        if "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed.")
        return self

    @property
    def cors_origin_list(self) -> list:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @staticmethod
    def parse_roles(value: str) -> Set[str]:
        return {r.strip().upper() for r in value.split(",") if r.strip()}


settings = Settings()
