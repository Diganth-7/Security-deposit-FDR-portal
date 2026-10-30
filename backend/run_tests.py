import sys
import subprocess
import json

def run_all_tests():
    """Runs pytest on backend/tests and returns formatted test results."""
    cmd = [sys.executable, "-m", "pytest", "backend/tests", "-v", "--tb=short"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "exit_code": result.returncode,
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

if __name__ == "__main__":
    res = run_all_tests()
    print(res["stdout"])
    if res["stderr"]:
        print(res["stderr"], file=sys.stderr)
    sys.exit(res["exit_code"])
