import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import engine, Base, db_backend_type, SessionLocal
from backend.app.routers import auth, institutions, deposits, stats, tests_runner, notifications, reminders, contracts, documents, approval_requests
from backend.app.seed import seed_database
from backend.app.services.reminder_service import process_maturity_reminders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aicte_fdr.main")

async def daily_reminder_scheduler():
    """
    Background scheduler loop that runs once a day to check maturities and generate reminders.
    Ensures idempotency without creating duplicate notifications.
    """
    while True:
        try:
            logger.info("Executing scheduled daily FDR maturity check...")
            db = SessionLocal()
            try:
                process_maturity_reminders(db)
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error during daily reminder task: {e}")
        # Sleep for 24 hours (86400 seconds)
        await asyncio.sleep(86400)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and seed default demonstration data
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    try:
        seed_database()
    except Exception as e:
        logger.warning(f"Seed skipped or already populated: {e}")

    # Run initial startup reminder scan
    try:
        startup_db = SessionLocal()
        try:
            process_maturity_reminders(startup_db)
        finally:
            startup_db.close()
    except Exception as e:
        logger.warning(f"Startup reminder scan skipped: {e}")

    # Start background daily reminder scheduler
    scheduler_task = asyncio.create_task(daily_reminder_scheduler())
    yield
    # Shutdown logic
    logger.info("Application shutting down.")
    scheduler_task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Smart India Hackathon 2026 (SIH26265) - Backend REST API for AICTE Security Deposit & FDR Portal",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Enable CORS for local Vite development and frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers with /api prefix
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(institutions.router, prefix=settings.API_PREFIX)
app.include_router(deposits.router, prefix=settings.API_PREFIX)
app.include_router(contracts.router, prefix=settings.API_PREFIX)
app.include_router(documents.router, prefix=settings.API_PREFIX)
app.include_router(approval_requests.router, prefix=settings.API_PREFIX)
app.include_router(notifications.router, prefix=settings.API_PREFIX)
app.include_router(reminders.router, prefix=settings.API_PREFIX)
app.include_router(stats.router, prefix=settings.API_PREFIX)
app.include_router(tests_runner.router, prefix=settings.API_PREFIX)

@app.get("/api/health")
def health_check():
    """System health check and database connection diagnostic."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "problem_statement": settings.PROJECT_CODE,
        "database_backend": db_backend_type,
        "version": settings.VERSION,
        "phase": "Phase 2 - FDR Maturity Tracking & Automated Reminders"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
