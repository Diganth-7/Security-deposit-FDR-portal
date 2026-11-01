import sys
import subprocess
from fastapi import APIRouter, Depends
from backend.app.auth.dependencies import require_admin

router = APIRouter(prefix="/tests", tags=["Test Runner"])

@router.post("/run", dependencies=[Depends(require_admin)])
def trigger_tests():
    """
    ADMIN only, and only mounted when ENABLE_TEST_RUNNER is on (development by default).
    Runs the backend pytest suite and returns the report for demonstrations.
    """
    cmd = [sys.executable, "-m", "pytest", "backend/tests", "-q", "--tb=short", "-p", "no:cacheprovider"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return {
        "status": "success" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-5000:],
    }
