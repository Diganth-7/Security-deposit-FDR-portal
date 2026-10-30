import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import engine, Base, db_backend_type
from backend.app.routers import auth, institutions, deposits, stats, tests_runner
from backend.app.seed import seed_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aicte_fdr.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and seed default demonstration data
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    try:
        seed_database()
    except Exception as e:
        logger.warning(f"Seed skipped or already populated: {e}")
    yield
    # Shutdown logic if any
    logger.info("Application shutting down.")

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
        "phase": "Phase 1 - Architecture & Core Models"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
