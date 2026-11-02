import React from 'react';
import { Clock, CheckCircle, ShieldCheck, CalendarCheck, XCircle, Unlock, Hourglass, AlertTriangle, RefreshCcw, LogOut, Gavel, Lock } from 'lucide-react';
import type { DepositStatus } from '../types';

const CFG: Record<DepositStatus, { label: string; cls: string; icon: React.ReactNode }> = {
  PENDING_VERIFICATION: { label: 'Pending Verification', cls: 'bg-amber-50 text-amber-700 border-amber-200', icon: <Clock className="w-3.5 h-3.5" /> },
  VERIFIED: { label: 'Verified', cls: 'bg-sky-50 text-sky-700 border-sky-200', icon: <CheckCircle className="w-3.5 h-3.5" /> },
  ACTIVE: { label: 'Active', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: <ShieldCheck className="w-3.5 h-3.5" /> },
  MATURITY_APPROACHING: { label: 'Maturity Approaching', cls: 'bg-orange-50 text-orange-700 border-orange-200', icon: <Hourglass className="w-3.5 h-3.5" /> },
  MATURED: { label: 'Matured', cls: 'bg-purple-50 text-purple-700 border-purple-200', icon: <CalendarCheck className="w-3.5 h-3.5" /> },
  MATURED_ACTION_REQUIRED: { label: 'Matured - Action Required', cls: 'bg-red-50 text-red-700 border-red-300', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  RENEWAL_REQUESTED: { label: 'Renewal Requested', cls: 'bg-indigo-50 text-indigo-700 border-indigo-200', icon: <RefreshCcw className="w-3.5 h-3.5" /> },
  RELEASE_REQUESTED: { label: 'Release Requested', cls: 'bg-cyan-50 text-cyan-700 border-cyan-200', icon: <LogOut className="w-3.5 h-3.5" /> },
  FORFEITURE_REQUESTED: { label: 'Forfeiture Requested', cls: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200', icon: <Gavel className="w-3.5 h-3.5" /> },
  RELEASED: { label: 'Released', cls: 'bg-slate-100 text-slate-700 border-slate-300', icon: <Unlock className="w-3.5 h-3.5" /> },
  REJECTED: { label: 'Rejected', cls: 'bg-rose-50 text-rose-700 border-rose-200', icon: <XCircle className="w-3.5 h-3.5" /> },
  CLOSED: { label: 'Closed', cls: 'bg-zinc-100 text-zinc-700 border-zinc-300', icon: <Lock className="w-3.5 h-3.5" /> },
};

export const depositStatusLabel = (s: string) => CFG[s as DepositStatus]?.label ?? s;

export const Pill: React.FC<{ cls: string; children: React.ReactNode }> = ({ cls, children }) => (
  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border whitespace-nowrap ${cls}`}>{children}</span>
);

export const StatusBadge: React.FC<{ status: DepositStatus }> = ({ status }) => {
  const c = CFG[status];
  if (!c) return <Pill cls="bg-gray-100 text-gray-700 border-gray-200">{status}</Pill>;
  return <Pill cls={c.cls}>{c.icon}{c.label}</Pill>;
};

const GENERIC: Record<string, string> = {
  SUBMITTED: 'bg-amber-50 text-amber-700 border-amber-200',
  UNDER_REVIEW: 'bg-sky-50 text-sky-700 border-sky-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  REJECTED: 'bg-rose-50 text-rose-700 border-rose-200',
  CANCELLED: 'bg-slate-100 text-slate-600 border-slate-300',
  PENDING: 'bg-amber-50 text-amber-700 border-amber-200',
  VERIFIED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  DRAFT: 'bg-slate-100 text-slate-600 border-slate-300',
  ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  COMPLETED: 'bg-blue-50 text-blue-700 border-blue-200',
  EXPIRED: 'bg-orange-50 text-orange-700 border-orange-200',
  TERMINATED: 'bg-rose-50 text-rose-700 border-rose-200',
  RENEWAL: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  RELEASE: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  FORFEITURE: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
};

/** Badge for request status, document verification status, contract status and request type. */
export const TagBadge: React.FC<{ value: string }> = ({ value }) => (
  <Pill cls={GENERIC[value] ?? 'bg-gray-100 text-gray-700 border-gray-200'}>
    {value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, ' ')}
  </Pill>
);
