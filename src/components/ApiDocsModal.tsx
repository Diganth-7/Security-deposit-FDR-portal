import React, { useState } from 'react';
import { X, Layers, Database, KeyRound, Server, FileCode, CheckCircle2 } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const ApiDocsModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'architecture' | 'endpoints' | 'models' | 'roles'>('architecture');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-3xl w-full border border-slate-200 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-100 text-blue-700">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">
                AICTE FDR Portal Architecture & API Documentation
              </h3>
              <p className="text-xs text-slate-500">
                SIH 2026 (SIH26265) Phase 1 Architecture, Database Models & Endpoints
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 px-6 bg-white gap-2">
          {[
            { id: 'architecture', label: '1. Architecture & Tree', icon: Layers },
            { id: 'models', label: '2. Database Models', icon: Database },
            { id: 'endpoints', label: '3. REST Endpoints', icon: Server },
            { id: 'roles', label: '4. RBAC Matrix', icon: KeyRound },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`py-3 px-3 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
                  isActive
                    ? 'border-blue-600 text-blue-700 bg-blue-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-800'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1 text-xs space-y-4 leading-relaxed">
          {activeTab === 'architecture' && (
            <div className="space-y-4">
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl">
                <h4 className="font-bold text-slate-800 text-sm mb-1">
                  High-Level Architecture (Full-Stack Decoupled)
                </h4>
                <p className="text-slate-600 mb-3">
                  The AICTE FDR Portal is designed around a secure, scalable 3-tier architecture:
                </p>
                <ul className="list-disc pl-5 space-y-1 text-slate-700">
                  <li><strong>Frontend:</strong> React 19 SPA built with Vite and Tailwind CSS. Provides separate customized views for Institutions, Regional Scrutiny Officers, and Central Administrators.</li>
                  <li><strong>Reverse Proxy & Dev Server:</strong> Node.js Express server on port 3000 mounting Vite and proxying <code className="text-blue-600 font-mono">/api/*</code> and <code className="text-blue-600 font-mono">/docs</code> to FastAPI on port 8000.</li>
                  <li><strong>Backend API:</strong> Python 3.10 FastAPI application serving high-performance asynchronous endpoints with Pydantic validation and JWT authentication.</li>
                  <li><strong>Database Layer:</strong> PostgreSQL configured via SQLAlchemy ORM with connection pooling, migrations, and automatic schema reflection.</li>
                </ul>
              </div>

              <div>
                <h4 className="font-bold text-slate-800 text-sm mb-2">Project Directory Structure</h4>
                <pre className="bg-slate-900 text-slate-200 p-4 rounded-xl font-mono text-[11px] overflow-x-auto">
{`aicte-fdr-portal/
├── backend/
│   ├── app/
│   │   ├── config.py              # Environment settings, Postgres credentials, JWT secret
│   │   ├── database.py            # SQLAlchemy engine, session factory, PostgreSQL connection
│   │   ├── models/                # Database entities
│   │   │   ├── user.py            # User model (ADMIN, INSTITUTION, OFFICER)
│   │   │   ├── institution.py     # Institution model (name, code, state, type)
│   │   │   └── deposit.py         # Deposit/FDR model (amount, FDR #, bank, issue/maturity)
│   │   ├── schemas/               # Pydantic v2 validation models
│   │   ├── auth/                  # Bcrypt hashing & PyJWT token generator & RBAC guards
│   │   ├── routers/               # Modular REST endpoints
│   │   │   ├── auth.py            # /api/auth/register, /api/auth/login, /api/auth/me
│   │   │   ├── institutions.py    # /api/institutions (CRUD & state filtering)
│   │   │   ├── deposits.py        # /api/deposits (FDR submission, review & scrutiny)
│   │   │   ├── stats.py           # /api/stats/dashboard (summary metrics)
│   │   │   └── tests_runner.py    # /api/tests/run (live automated test execution)
│   │   ├── main.py                # FastAPI app, CORS, table initialization & router setup
│   │   └── seed.py                # Database seeder with sample AICTE colleges and FDRs
│   ├── tests/                     # 14 Pytest integration test cases
│   └── requirements.txt           # Python backend dependencies
├── src/                           # React frontend (Vite + Tailwind CSS)
│   ├── components/                # Modular UI components
│   ├── context/                   # AuthContext with persistent JWT storage
│   ├── api/                       # Typed API client with Bearer token injection
│   └── types/                     # TypeScript domain models
├── server.ts                      # Express server mounting Vite + proxying FastAPI
├── .env.example                   # Environment configuration template
└── README.md                      # Comprehensive setup & architecture documentation`}
                </pre>
              </div>
            </div>
          )}

          {activeTab === 'models' && (
            <div className="space-y-4">
              <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
                <span className="font-mono text-blue-700 font-bold block text-sm mb-1">
                  Table: users
                </span>
                <p className="text-slate-600 mb-2">Stores portal users and their role memberships.</p>
                <div className="font-mono text-[11px] bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div>id: Integer [PRIMARY KEY, AUTOINCREMENT]</div>
                  <div>email: String(255) [UNIQUE, INDEX, NOT NULL]</div>
                  <div>full_name: String(255) [NOT NULL]</div>
                  <div>hashed_password: String(255) [NOT NULL]</div>
                  <div>role: Enum(&apos;ADMIN&apos;, &apos;INSTITUTION&apos;, &apos;OFFICER&apos;) [NOT NULL]</div>
                  <div>institution_id: Integer [FOREIGN KEY -&gt; institutions.id, NULLABLE]</div>
                  <div>is_active: Boolean [DEFAULT True]</div>
                  <div>created_at: DateTime [DEFAULT CURRENT_TIMESTAMP]</div>
                </div>
              </div>

              <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
                <span className="font-mono text-emerald-700 font-bold block text-sm mb-1">
                  Table: institutions
                </span>
                <p className="text-slate-600 mb-2">AICTE affiliated engineering colleges and polytechnic institutes.</p>
                <div className="font-mono text-[11px] bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div>id: Integer [PRIMARY KEY, AUTOINCREMENT]</div>
                  <div>aicte_id: String(50) [UNIQUE, INDEX, NOT NULL]</div>
                  <div>name: String(255) [INDEX, NOT NULL]</div>
                  <div>state: String(100) [NOT NULL]</div>
                  <div>city: String(100) [NOT NULL]</div>
                  <div>institute_type: String(100) [DEFAULT &apos;Technical Institute&apos;]</div>
                  <div>contact_email: String(255) [NOT NULL]</div>
                  <div>contact_phone: String(50) [NULLABLE]</div>
                </div>
              </div>

              <div className="border border-slate-200 rounded-xl p-4 bg-slate-50">
                <span className="font-mono text-amber-700 font-bold block text-sm mb-1">
                  Table: deposits (FDR)
                </span>
                <p className="text-slate-600 mb-2">Statutory Security Deposits submitted as Fixed Deposit Receipts.</p>
                <div className="font-mono text-[11px] bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div>id: Integer [PRIMARY KEY, AUTOINCREMENT]</div>
                  <div>fdr_number: String(100) [UNIQUE, INDEX, NOT NULL]</div>
                  <div>amount: Float [NOT NULL, &gt; 0]</div>
                  <div>bank_name: String(255) [NOT NULL]</div>
                  <div>branch_name: String(255) [NULLABLE]</div>
                  <div>ifsc_code: String(50) [NULLABLE]</div>
                  <div>issue_date: Date [NOT NULL]</div>
                  <div>maturity_date: Date [NOT NULL, &gt; issue_date]</div>
                  <div>status: Enum(&apos;PENDING_VERIFICATION&apos;, &apos;VERIFIED&apos;, &apos;ACTIVE&apos;, &apos;MATURED&apos;, &apos;RELEASED&apos;, &apos;REJECTED&apos;)</div>
                  <div>institution_id: Integer [FOREIGN KEY -&gt; institutions.id, CASCADE]</div>
                  <div>submitted_by_id: Integer [FOREIGN KEY -&gt; users.id]</div>
                  <div>verified_by_id: Integer [FOREIGN KEY -&gt; users.id, NULLABLE]</div>
                  <div>verification_remarks: Text [NULLABLE]</div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'endpoints' && (
            <div className="space-y-3">
              {[
                { method: 'POST', path: '/api/auth/register', auth: 'Public', desc: 'Register a new user account with role selection' },
                { method: 'POST', path: '/api/auth/login', auth: 'Public', desc: 'Authenticate credentials and obtain signed JWT token' },
                { method: 'GET', path: '/api/auth/me', auth: 'Bearer JWT', desc: 'Retrieve authenticated profile and role details' },
                { method: 'GET', path: '/api/institutions', auth: 'Bearer JWT', desc: 'List affiliated institutions (supports ?state= & ?search=)' },
                { method: 'POST', path: '/api/institutions', auth: 'ADMIN Only', desc: 'Register a new approved AICTE institution' },
                { method: 'GET', path: '/api/deposits', auth: 'Role-Scoped', desc: 'Institutions see own FDRs; Admins/Officers see pan-India FDRs' },
                { method: 'POST', path: '/api/deposits', auth: 'INSTITUTION / ADMIN', desc: 'Submit new FDR with bank details and validity dates' },
                { method: 'PATCH', path: '/api/deposits/{id}/status', auth: 'OFFICER / ADMIN', desc: 'Audit, verify, approve or reject an FDR submission' },
                { method: 'GET', path: '/api/stats/dashboard', auth: 'Bearer JWT', desc: 'Aggregate metrics (FDR value, pending queue, active liens)' },
                { method: 'POST', path: '/api/tests/run', auth: 'Public', desc: 'Trigger pytest test suite and return execution status' },
              ].map((ep, i) => (
                <div key={i} className="flex items-start justify-between p-3 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${
                      ep.method === 'POST' ? 'bg-emerald-100 text-emerald-800' :
                      ep.method === 'GET' ? 'bg-blue-100 text-blue-800' :
                      'bg-amber-100 text-amber-800'
                    }`}>
                      {ep.method}
                    </span>
                    <span className="font-mono font-medium text-slate-800">{ep.path}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                      {ep.auth}
                    </span>
                    <p className="text-slate-500 text-[11px] mt-0.5">{ep.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'roles' && (
            <div className="space-y-4">
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <table className="min-w-full divide-y divide-slate-200 text-left">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-slate-700 font-bold">Action / Feature</th>
                      <th className="px-3 py-2 text-rose-700 font-bold">ADMIN</th>
                      <th className="px-3 py-2 text-indigo-700 font-bold">OFFICER</th>
                      <th className="px-3 py-2 text-emerald-700 font-bold">INSTITUTION</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white">
                    <tr>
                      <td className="px-4 py-2 font-medium">Submit New Security FDR</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">Yes (Any)</td>
                      <td className="px-3 py-2 text-rose-500 font-bold">No</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">Yes (Own)</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium">View Submitted FDRs</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">All India</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">All India</td>
                      <td className="px-3 py-2 text-slate-700 font-medium">Only Own College</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium">Audit &amp; Verify FDR (Status)</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">Yes</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">Yes</td>
                      <td className="px-3 py-2 text-rose-500 font-bold">Forbidden (403)</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium">Add Approved Institution</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">Yes</td>
                      <td className="px-3 py-2 text-rose-500 font-bold">No</td>
                      <td className="px-3 py-2 text-rose-500 font-bold">No</td>
                    </tr>
                    <tr>
                      <td className="px-4 py-2 font-medium">View Aggregate Portal Stats</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">National</td>
                      <td className="px-3 py-2 text-emerald-600 font-bold">National</td>
                      <td className="px-3 py-2 text-slate-700 font-medium">College Level</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
          <span>Smart India Hackathon 2026 • Problem ID SIH26265</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
