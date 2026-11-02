#!/usr/bin/env bash
# One-command demo: installs dependencies, creates a fresh demo database and starts the app.
#   ./scripts/run-demo.sh            # http://127.0.0.1:3000
# Demo password: set DEMO_PASSWORD yourself, otherwise the default below is used (demo only).
set -euo pipefail
cd "$(dirname "$0")/.."

export DEMO_PASSWORD="${DEMO_PASSWORD:-DemoPass#2026x}"
export APP_ENV=development
export DATABASE_URL="${DATABASE_URL:-sqlite:///./aicte_demo.db}"
export SEED_DEMO_DATA=true
export VITE_SHOW_DEMO_LOGINS=true
export VITE_DEMO_PASSWORD="$DEMO_PASSWORD"
export PORT="${PORT:-3000}"

# Linux/macOS keep the venv python in .venv/bin, Windows (Git Bash) in .venv/Scripts.
find_venv_python() {
  if [ -x ".venv/bin/python" ]; then echo ".venv/bin/python"
  elif [ -x ".venv/Scripts/python.exe" ]; then echo ".venv/Scripts/python.exe"
  fi
}
PY="$(find_venv_python || true)"
if [ -z "$PY" ]; then
  echo ">> Creating Python virtualenv (.venv)"
  if command -v python3 >/dev/null 2>&1; then python3 -m venv .venv; else python -m venv .venv; fi
  PY="$(find_venv_python)"
fi
export PYTHON_BIN="$PWD/$PY"
# Node (on Windows) needs a native path such as C:\...\python.exe, not /c/...
if command -v cygpath >/dev/null 2>&1; then export PYTHON_BIN="$(cygpath -w "$PYTHON_BIN")"; fi
echo ">> Installing backend dependencies"
"$PYTHON_BIN" -m pip install -q --disable-pip-version-check -r backend/requirements.txt
echo ">> Installing frontend dependencies"
npm install --no-audit --no-fund --silent

if [ "${FRESH:-1}" = "1" ] && [[ "$DATABASE_URL" == sqlite* ]]; then
  rm -f aicte_demo.db
fi
echo ">> Starting on http://127.0.0.1:$PORT  (Swagger: /docs)"
echo ">> Demo logins: admin@aicte.gov.in | officer.sharma@aicte.gov.in | officer.rao@aicte.gov.in"
echo ">>              registrar@dtu.ac.in | finance@coep.ac.in | accounts@bmsce.ac.in   password: $DEMO_PASSWORD"
exec npx tsx server.ts
