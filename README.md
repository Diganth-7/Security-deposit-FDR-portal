# AICTE Security Deposit and FDR Management Portal (SIH26265)

Prototype for managing institutions' security-deposit FDRs: registration and login, FDR tracking with
maturity reminders, contracts, document upload and officer verification, renewal/release/forfeiture
approvals, audit trail and reports with CSV export.

**Prototype status:** there is **no real bank integration** and no AI/ML. "Verification" means an AICTE officer
checking the submitted document, not confirmation from a bank. This is not production-ready (see *Limitations*).

Stack: FastAPI, SQLAlchemy, Pydantic, JWT, SQLite or PostgreSQL; React 19, Vite, Tailwind.

## Run the demo (one command)

Needs Python 3.11+ and Node 20+.

```bash
./scripts/run-demo.sh        # then open http://127.0.0.1:3000   (API docs: /docs)
```

It creates `.venv`, installs dependencies, builds a **fresh** demo database (SQLite, `aicte_demo.db`), loads
fictional demo data and starts everything. Set `DEMO_PASSWORD=...` to choose the shared demo password
(default `DemoPass#2026x`, demo only). The login page shows one-click buttons for the demo roles.

| Role | Login (email) |
|---|---|
| Administrator | admin@aicte.gov.in |
| Scrutiny officer | officer.sharma@aicte.gov.in, officer.rao@aicte.gov.in |
| Institution | registrar@dtu.ac.in, finance@coep.ac.in, accounts@bmsce.ac.in |

Demo data: 3 institutions, 5 contracts (one under-covered), 11 FDRs maturing in 1, 7, 20 and 30 days plus one
overdue, 11 documents (verified/pending/rejected), and requests in every state, with notifications and audit history.

## Manual setup

```bash
cp .env.example .env                       # edit values; never commit .env
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
npm install
PYTHON_BIN=$PWD/.venv/bin/python npx tsx server.ts      # web + API on :3000
```
Database: default is SQLite. For PostgreSQL set `DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DB`;
tables are created and upgraded automatically at startup (`python -m backend.app.migrations` runs it manually).
If the database is unreachable the app stops with a clear message instead of switching databases.
Real administrator: `python -m backend.app.create_admin --email you@org --name "Your Name"` (password via
`ADMIN_PASSWORD` or prompt). Set `APP_ENV=production`, a 32+ character `SECRET_KEY` and `SEED_DEMO_DATA=false` for real use.

## What the screens cover today

Web UI: login and institution registration, role dashboard (live statistics), FDR list/search, FDR creation,
FDR details and officer verification, institutions directory.

Available through the API and Swagger (`/docs`, click *Authorize* with a token from `/api/auth/login`):
contracts, document upload/verify/download, renewal/release/forfeiture requests and officer decisions,
notifications, audit trail, reports and CSV export. Dedicated screens for these are not built yet.

## Suggested 5-minute demo

1. Log in as an institution (DTU): own FDRs only, statistics from the database.
2. Log in as an officer: all FDRs and institutions; verify the pending FDR.
3. In Swagger as officer: `GET /api/requests/pending`, approve the DTU renewal (remarks required) and the
   release request; `officer.rao` cannot decide a request he submitted himself (forfeiture).
4. `GET /api/reports/contract-coverage` (COEP shows a shortfall), `GET /api/reports/export/csv?report=maturity`.
5. `GET /api/audit-logs` as officer (an institution gets 403).

## Tests

```bash
.venv/bin/python -m pytest backend/tests -q      # 104 tests, in-memory database
npm run lint && npm run build                     # frontend type-check and build
```

## Security notes and limitations

Done: bcrypt passwords with strength rules, login lockout, JWT with a required strong secret in production,
role checks and institution isolation on every endpoint, append-only audit trail, upload validation (type,
content signature, size, safe server-side names, stored outside web roots), exact decimal money, explicit CORS
origins, uniform error responses without stack traces, request IDs.

Limitations: not penetration-tested; no real bank or identity integration; institution self-registration is open
to anyone who knows an institution ID (production needs admin approval); no rate limiting beyond login
lockout; audit entries are append-only at application level only (a database administrator could still alter
them); documents are stored on local disk; the UI for contracts, approvals, reports and audit is not built yet.
