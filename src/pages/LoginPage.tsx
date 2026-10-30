import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Institution } from '../types';
import {
  Shield,
  Lock,
  Mail,
  User,
  Building,
  ArrowRight,
  AlertCircle,
  CheckCircle,
  KeyRound,
  FileCheck2,
  Sparkles
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login, register } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);

  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<'ADMIN' | 'OFFICER' | 'INSTITUTION'>('INSTITUTION');
  const [institutionId, setInstitutionId] = useState<number | undefined>(undefined);

  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    api
      .getInstitutions()
      .then((data) => {
        setInstitutions(data);
        if (data.length > 0) {
          setInstitutionId(data[0].id);
        }
      })
      .catch((err) => console.warn('Could not prefetch institutions:', err));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (isRegistering) {
        if (!fullName.trim()) {
          throw new Error('Full Name is required.');
        }
        await register({
          email: email.trim().toLowerCase(),
          full_name: fullName.trim(),
          password,
          role,
          institution_id: role === 'INSTITUTION' ? institutionId : undefined,
        });
      } else {
        await login(email.trim().toLowerCase(), password);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickLogin = async (demoEmail: string, demoPass: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await login(demoEmail, demoPass);
    } catch (err: any) {
      setError(err.message || 'Quick login failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Tricolor Ribbon on top */}
      <div className="fixed top-0 left-0 right-0 h-1.5 flex z-50">
        <div className="h-full w-1/3 bg-[#FF9933]"></div>
        <div className="h-full w-1/3 bg-white"></div>
        <div className="h-full w-1/3 bg-[#138808]"></div>
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Emblem & Header */}
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-tr from-amber-600 via-orange-600 to-blue-900 flex items-center justify-center text-white shadow-lg shadow-orange-500/20 ring-4 ring-white">
          <Shield className="w-9 h-9 stroke-[2.2]" />
        </div>
        <h2 className="mt-4 text-2xl font-black text-slate-900 tracking-tight">
          AICTE FDR Portal
        </h2>
        <p className="mt-1 text-xs font-semibold text-slate-500 uppercase tracking-widest">
          All India Council for Technical Education • SIH26265
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-xl px-4">
        <div className="bg-white py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-200">
          {/* Fast-Track Demo Selector for Hackathon Reviewers */}
          <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50/70 border border-blue-200/80 rounded-xl">
            <div className="flex items-center gap-1.5 text-xs font-bold text-blue-900 mb-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <span>SIH 2026 Evaluator Quick Role Switcher (1-Click Login):</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleQuickLogin('admin@aicte.gov.in', 'Admin@AICTE2026')}
                className="px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg text-left shadow-2xs font-medium text-slate-800 transition-colors"
              >
                <span className="font-bold text-rose-700 block text-[11px] uppercase">
                  1. Admin Role
                </span>
                <span className="text-[11px] text-slate-500">Dr. Alok Verma</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('officer.sharma@aicte.gov.in', 'Officer@AICTE2026')}
                className="px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg text-left shadow-2xs font-medium text-slate-800 transition-colors"
              >
                <span className="font-bold text-indigo-700 block text-[11px] uppercase">
                  2. Scrutiny Officer
                </span>
                <span className="text-[11px] text-slate-500">Rajesh Sharma</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('registrar@dtu.ac.in', 'Dtu@2026Pass')}
                className="px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg text-left shadow-2xs font-medium text-slate-800 transition-colors"
              >
                <span className="font-bold text-emerald-700 block text-[11px] uppercase">
                  3. Institution (DTU)
                </span>
                <span className="text-[11px] text-slate-500">Prof. S. K. Garg</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('finance@coep.ac.in', 'Coep@2026Pass')}
                className="px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg text-left shadow-2xs font-medium text-slate-800 transition-colors"
              >
                <span className="font-bold text-emerald-700 block text-[11px] uppercase">
                  4. Institution (COEP)
                </span>
                <span className="text-[11px] text-slate-500">Dr. V. N. Pande</span>
              </button>
            </div>
          </div>

          {/* Toggle between Sign In / Register */}
          <div className="flex border-b border-slate-200 mb-6">
            <button
              type="button"
              onClick={() => {
                setIsRegistering(false);
                setError(null);
              }}
              className={`flex-1 pb-3 text-sm font-semibold text-center border-b-2 transition-colors ${
                !isRegistering
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Sign In to Account
            </button>
            <button
              type="button"
              onClick={() => {
                setIsRegistering(true);
                setError(null);
              }}
              className={`flex-1 pb-3 text-sm font-semibold text-center border-b-2 transition-colors ${
                isRegistering
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Register New User
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegistering && (
              <>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Full Name & Designation
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                    <input
                      type="text"
                      placeholder="e.g. Dr. Ramesh Kumar"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                      className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    System Role
                  </label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as any)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    <option value="INSTITUTION">INSTITUTION (College / University Representative)</option>
                    <option value="OFFICER">OFFICER (AICTE Scrutiny Officer)</option>
                    <option value="ADMIN">ADMIN (Central AICTE Directorate)</option>
                  </select>
                </div>

                {role === 'INSTITUTION' && institutions.length > 0 && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Affiliated Institution
                    </label>
                    <div className="relative">
                      <Building className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                      <select
                        value={institutionId}
                        onChange={(e) => setInstitutionId(Number(e.target.value))}
                        className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      >
                        {institutions.map((inst) => (
                          <option key={inst.id} value={inst.id}>
                            {inst.name} ({inst.city}, {inst.state})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}
              </>
            )}

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Official Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="email"
                  placeholder="name@domain.gov.in or .ac.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
                <input
                  type="password"
                  placeholder="Enter secure password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition-colors shadow-md shadow-blue-500/20"
            >
              {isLoading ? (
                'Processing...'
              ) : isRegistering ? (
                <>
                  <span>Create AICTE Account</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>

        <div className="mt-4 text-center text-xs text-slate-500">
          Statutory Portal for Security Deposit & FDR Management • Ministry of Education, Govt. of India
        </div>
      </div>
    </div>
  );
};
