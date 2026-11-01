import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.config import settings
from backend.app.database import engine, db_backend_type, SessionLocal
from backend.app.migrations import run_migrations
from backend.app.routers import (
    auth, institutions, deposits, stats, tests_runner, notifications, reminders,
    contracts, documents, approval_requests,
)
from backend.app.seed import seed_database
from backend.app.services.reminder_service import process_maturity_reminders
from backend.app.utils.clock import today
from backend.app.utils.context import get_request_id, new_request_id, set_request_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aicte_fdr.main")


def _seconds_until_next_run() -> float:
    """Seconds until REMINDER_RUN_TIME (HH:MM, local to the server clock)."""
    try:
        hh, mm = (int(x) for x in settings.REMINDER_RUN_TIME.split(":"))
    except ValueError:
        hh, mm = 0, 10
    now = datetime.now()
    nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def _run_reminders_once(label: str) -> None:
    db = SessionLocal()
    try:
        summary = process_maturity_reminders(db)
        logger.info("%s reminder scan done: %s", label, summary)
    except Exception:
        logger.exception("%s reminder scan failed", label)
        db.rollback()
    finally:
        db.close()


async def daily_reminder_scheduler():
    """Runs the maturity scan once a day. Safe to repeat: reminders are de-duplicated."""
    while True:
        await asyncio.sleep(_seconds_until_next_run())
        await asyncio.to_thread(_run_reminders_once, "Scheduled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_task = None
    if settings.APP_ENV != "test":
        applied = run_migrations(engine)  # a database error here stops startup on purpose
        logger.info("Database ready (%s). Migrations applied: %s", db_backend_type, applied or "none")
        if settings.SEED_DEMO_DATA:
            try:
                seed_database()
            except Exception:
                logger.exception("Demo data seeding failed")
        _run_reminders_once("Startup")
    if settings.ENABLE_REMINDER_SCHEDULER:
        scheduler_task = asyncio.create_task(daily_reminder_scheduler())
    yield
    logger.info("Application shutting down.")
    if scheduler_task:
        scheduler_task.cancel()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Smart India Hackathon 2026 (SIH26265) - REST API for the AICTE Security Deposit & FDR Portal. "
                "Prototype: no real bank integration.",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context_and_security_headers(request: Request, call_next):
    """Attach a correlation ID to every request/response and add basic security headers."""
    rid = new_request_id(request.headers.get("x-request-id"))
    set_request_id(rid)
    try:
        response = await call_next(request)
    finally:
        set_request_id(None)
    response.headers["X-Request-ID"] = rid
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith(settings.API_PREFIX):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---- Consistent error bodies: {"detail": ..., "code": ..., "request_id": ...} ----
def _error(status_code: int, detail, code: str, request: Request, headers=None) -> JSONResponse:
    rid = request.headers.get("x-request-id") or ""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code, "request_id": get_request_id() or rid},
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, exc.detail, f"HTTP_{exc.status_code}", request, getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Only field location and message are returned: never the submitted values.
    problems = [{"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "Invalid value")}
                for e in exc.errors()]
    return _error(422, problems, "VALIDATION_ERROR", request)


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return _error(403, str(exc), "FORBIDDEN", request)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error(500, "An internal error occurred. Quote the request ID when reporting it.", "INTERNAL_ERROR", request)


# ---- Routers ----
for _router in (auth.router, institutions.router, deposits.router, contracts.router, documents.router,
                approval_requests.router, notifications.router, reminders.router, stats.router):
    app.include_router(_router, prefix=settings.API_PREFIX)
if settings.ENABLE_TEST_RUNNER:
    app.include_router(tests_runner.router, prefix=settings.API_PREFIX)


@app.get("/api/health", tags=["Health"])
def health_check():
    """Liveness plus a real database check. Reports 503 if the database cannot be queried."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database query failed")
        db_ok = False
    body = {
        "status": "healthy" if db_ok else "unhealthy",
        "service": settings.PROJECT_NAME,
        "problem_statement": settings.PROJECT_CODE,
        "database_backend": db_backend_type,
        "database_ok": db_ok,
        "environment": settings.APP_ENV,
        "date": today().isoformat(),
        "version": settings.VERSION,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
