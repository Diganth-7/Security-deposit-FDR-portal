import sys
import subprocess
from fastapi import APIRouter

router = APIRouter(prefix="/tests", tags=["Test Runner"])

@router.post("/run")
def trigger_tests():
    """Runs the backend pytest test suite and returns execution report for hackathon evaluation."""
    cmd = [sys.executable, "-m", "pytest", "backend/tests", "-v", "--tb=short"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "status": "success" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
