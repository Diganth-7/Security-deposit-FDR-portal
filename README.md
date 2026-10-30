# AICTE Security Deposit and FDR Management Portal
### Smart India Hackathon 2026 — Problem Statement ID: SIH26265
**Phase 1: Architecture, Core Models, RBAC & Authentication Implementation**

---

## 1. Project Overview
The **AICTE Security Deposit and FDR Management Portal** is a unified digital platform developed for the **All India Council for Technical Education (AICTE)**, Ministry of Education, Government of India. 

Under AICTE statutory approval process regulations, technical institutions and colleges must deposit mandatory security amounts in the form of **Fixed Deposit Receipts (FDR)** drawn under a joint lien between the Institution and the AICTE Regional Officer. This portal replaces manual, error-prone paper tracking with an automated, role-governed lifecycle management system.

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite 8, Tailwind CSS v4, Lucide React, Motion |
| **Backend API** | Python 3.10, FastAPI, Pydantic v2, PyJWT, Passlib / Bcrypt |
| **ORM & Database** | SQLAlchemy 2.0, PostgreSQL (psycopg2-binary), SQLite fallback |
| **Testing** | Pytest 9.2, FastAPI TestClient, HTTPX |
| **Server / Proxy** | Express Node.js server with Vite middlewares and API proxying |

---

## 3. Project Directory Structure

```text
aicte-fdr-portal/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py              # Environment configuration, DB & JWT settings
│   │   ├── database.py            # SQLAlchemy engine, session maker, DB dependency
│   │   ├── models/                # SQLAlchemy database entities
│   │   │   ├── __init__.py
│   │   │   ├── user.py            # User model & UserRole enum (ADMIN, INSTITUTION, OFFICER)
│   │   │   ├── institution.py     # Institution model (name, AICTE ID, state, contact)
│   │   │   └── deposit.py         # Deposit / FDR model (amount, FDR #, bank, dates, status)
│   │   ├── schemas/               # Pydantic validation schemas
│   │   │   ├── __init__.py
│   │   │   ├── user.py            # UserCreate, UserLogin, UserResponse, Token
│   │   │   ├── institution.py     # InstitutionCreate, InstitutionResponse
│   │   │   └── deposit.py         # DepositCreate, DepositStatusUpdate, DepositResponse
│   │   ├── auth/                  # Security & authentication layer
│   │   │   ├── __init__.py
│   │   │   ├── security.py        # Bcrypt password hashing & JWT encode/decode
│   │   │   └── dependencies.py    # Role-based access control (RBAC) dependency guards
│   │   ├── routers/               # Modular REST endpoints
│   │   │   ├── __init__.py
│   │   │   ├── auth.py            # /api/auth/register, /api/auth/login, /api/auth/me
│   │   │   ├── institutions.py    # /api/institutions (list, filter by state, create)
│   │   │   ├── deposits.py        # /api/deposits (submit FDR, scrutiny & verification)
│   │   │   ├── stats.py           # /api/stats/dashboard (summary metrics)
│   │   │   └── tests_runner.py    # /api/tests/run (browser test execution)
│   │   ├── main.py                # FastAPI app initialization, CORS & router mounting
│   │   └── seed.py                # Database seeder with sample colleges and FDRs
│   ├── tests/                     # 14 Pytest test cases
│   │   ├── conftest.py            # Test database fixture & test tokens
│   │   ├── test_auth.py           # User registration, login & JWT tests
│   │   ├── test_institutions.py   # Institution management & RBAC tests
│   │   └── test_deposits.py       # FDR submission, validation & officer scrutiny tests
│   ├── run_tests.py               # Standalone test runner
│   └── requirements.txt           # Python package requirements
├── src/                           # React frontend application
│   ├── components/
│   │   ├── Navbar.tsx             # AICTE branding, status & user profile
│   │   ├── StatusBadge.tsx        # Styled badges for FDR lifecycle
│   │   ├── MetricCard.tsx         # Dashboard KPI cards
│   │   ├── DepositModal.tsx       # Submit new FDR deposit modal
│   │   ├── DepositDetailsModal.tsx# FDR scrutiny and status update modal
│   │   ├── TestRunnerModal.tsx    # Live Pytest runner in browser
│   │   └── ApiDocsModal.tsx       # Architecture & schema modal viewer
│   ├── pages/
│   │   ├── LoginPage.tsx          # Login & registration with 1-click test role switcher
│   │   └── DashboardPage.tsx      # Role-tailored dashboard & FDR table
│   ├── context/
│   │   └── AuthContext.tsx        # JWT session provider
│   ├── api/
│   │   └── client.ts              # Typed API client
│   ├── types/
│   │   └── index.ts               # TypeScript interfaces
│   ├── App.tsx                    # Main layout & route gating
│   ├── index.css                  # Tailwind CSS
│   └── main.tsx
├── server.ts                      # Full-stack server (Node Express + Vite + FastAPI proxy)
├── package.json
├── tsconfig.json
├── .env.example                   # Environment configuration template
└── README.md                      # Complete documentation
```

---

## 4. Database Models & Schema Design

### 4.1. User Model (`users`)
- `id` (Integer, Primary Key)
- `email` (String 255, Unique, Indexed)
- `full_name` (String 255)
- `hashed_password` (String 255)
- `role` (Enum: `ADMIN`, `INSTITUTION`, `OFFICER`)
- `institution_id` (Integer, Foreign Key to `institutions.id`, Nullable)
- `is_active` (Boolean, Default: True)
- `created_at` (DateTime)

### 4.2. Institution Model (`institutions`)
- `id` (Integer, Primary Key)
- `aicte_id` (String 50, Unique, Indexed)
- `name` (String 255, Indexed)
- `state` (String 100)
- `city` (String 100)
- `institute_type` (String 100)
- `contact_email` (String 255)
- `contact_phone` (String 50, Nullable)

### 4.3. Deposit Model (`deposits`)
- `id` (Integer, Primary Key)
- `fdr_number` (String 100, Unique, Indexed)
- `amount` (Float, Strictly > 0)
- `bank_name` (String 255)
- `branch_name` (String 255, Nullable)
- `ifsc_code` (String 50, Nullable)
- `issue_date` (Date)
- `maturity_date` (Date, Validated: `maturity_date > issue_date`)
- `status` (Enum: `PENDING_VERIFICATION`, `VERIFIED`, `ACTIVE`, `MATURED`, `RELEASED`, `REJECTED`)
- `institution_id` (Integer, Foreign Key to `institutions.id`)
- `submitted_by_id` (Integer, Foreign Key to `users.id`)
- `verified_by_id` (Integer, Foreign Key to `users.id`, Nullable)
- `verification_remarks` (Text, Nullable)
- `verified_at` (DateTime, Nullable)

---

## 5. Role-Based Access Control (RBAC) Matrix

| Capability | ADMIN | OFFICER | INSTITUTION |
|---|:---:|:---:|:---:|
| **Submit FDR Deposit** | Yes (Any college) | No (403) | Yes (Own college) |
| **View FDR Records** | Pan-India | Pan-India | Own college only |
| **Verify / Scrutinize FDR** | Yes | Yes | No (403) |
| **Reject / Flag FDR** | Yes | Yes | No (403) |
| **Create Approved Institution** | Yes | No (403) | No (403) |
| **Access Dashboard KPIs** | Pan-India | Pan-India | College Scoped |

---

## 6. REST API Endpoints

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | Public | Register new user with selected role |
| `POST` | `/api/auth/login` | Public | Authenticate with email/password, returns JWT |
| `GET` | `/api/auth/me` | Bearer JWT | Fetch current authenticated user profile |
| `GET` | `/api/institutions` | Public / Auth | List colleges with `?state=` and `?search=` filters |
| `POST` | `/api/institutions` | ADMIN | Add new affiliated institution |
| `GET` | `/api/deposits` | Scoped JWT | List FDRs (Institutions see own, Officers/Admins see all) |
| `POST` | `/api/deposits` | INSTITUTION / ADMIN | Submit new FDR for verification |
| `GET` | `/api/deposits/{id}` | Scoped JWT | Get FDR certificate details |
| `PATCH` | `/api/deposits/{id}/status` | OFFICER / ADMIN | Audit, verify, approve, or reject deposit |
| `GET` | `/api/stats/dashboard` | Bearer JWT | Summary metrics (FDR value, pending queue, active) |
| `POST` | `/api/tests/run` | Public | Execute 14 automated pytest integration test cases |
| `GET` | `/api/health` | Public | Backend health & DB diagnostic |

---

## 7. Setup & Run Instructions

### 7.1. Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ (or automatic SQLite fallback for rapid testing)

### 7.2. Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update your database configuration in `.env`:
```ini
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aicte_fdr_db"
SECRET_KEY="aicte_sih26265_super_secure_jwt_secret_key_2026"
```

### 7.3. Backend Setup & Run
```bash
# 1. Install backend dependencies
pip install -r backend/requirements.txt

# 2. Seed default data (institutions, users, sample FDRs)
python3 -m backend.app.seed

# 3. Run FastAPI backend directly on port 8000
python3 -m uvicorn backend.app.main:app --port 8000 --reload
```
Interactive Swagger API documentation is available at: `http://localhost:8000/docs`

### 7.4. Frontend & Full-Stack Run
```bash
# 1. Install frontend dependencies
npm install

# 2. Start full-stack portal (spawns FastAPI and serves React on port 3000)
npm run dev
```
Open `http://localhost:3000` in your web browser.

---

## 8. Automated Testing
Run the automated test suite covering all Phase 1 requirements:
```bash
python3 -m pytest backend/tests -v
```
All **14 test cases pass**, validating:
- Registration & duplicate email prevention
- Login, password hashing & JWT token validation
- Negative deposit amount rejection (422)
- Maturity date < Issue date validation error (422)
- Scrutiny Officer verification flow (200)
- Scrutiny Officer forbidden from submitting FDR (403)
- Institution forbidden from approving their own FDR (403)
- Institution directory & role-gated creation

*(You can also click the **&quot;Run Tests&quot;** button in the top navbar inside the portal to execute the tests directly in the browser!)*

---

## 9. Evaluation Demo Credentials

The database comes pre-seeded with accounts for all three roles:

| Role | Name | Email | Password |
|---|---|---|---|
| **ADMIN** | Dr. Alok Verma | `admin@aicte.gov.in` | `Admin@AICTE2026` |
| **OFFICER** | Rajesh Sharma | `officer.sharma@aicte.gov.in` | `Officer@AICTE2026` |
| **INSTITUTION (DTU)** | Prof. S. K. Garg | `registrar@dtu.ac.in` | `Dtu@2026Pass` |
| **INSTITUTION (COEP)** | Dr. V. N. Pande | `finance@coep.ac.in` | `Coep@2026Pass` |

*(Convenient 1-click login buttons are also provided on the Login page for instant role switching during evaluation).*

---

## 10. Phase 1 Checklist & Phase 2 Roadmap
- [x] 1. Project directory structure
- [x] 2. PostgreSQL connection and configuration
- [x] 3. User model with Admin, Institution and Officer roles
- [x] 4. Institution model
- [x] 5. Deposit model with amount, FDR number, bank name, issue date, maturity date and status
- [x] 6. Registration and login endpoints
- [x] 7. Role-based authorization
- [x] 8. React login page and dashboard layout
- [x] 9. Environment variables
- [x] 10. README setup instructions

**Phase 2 Ready to Begin Upon User Approval.**
