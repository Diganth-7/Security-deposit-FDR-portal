import React, { useState } from 'react';
import { Deposit, User } from '../types';
import { api } from '../api/client';
import { StatusBadge } from './StatusBadge';
import {
  X,
  Building2,
  Calendar,
  Landmark,
  FileCheck2,
  CheckCircle,
  XCircle,
  AlertCircle,
  UserCheck,
  Clock,
  ShieldAlert
} from 'lucide-react';

interface Props {
  deposit: Deposit | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
  currentUser: User;
}

export const DepositDetailsModal: React.FC<Props> = ({
  deposit,
  isOpen,
  onClose,
  onUpdated,
  currentUser,
}) => {
  const [remarks, setRemarks] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !deposit) return null;

  const canVerify = currentUser.role === 'ADMIN' || currentUser.role === 'OFFICER';

  const handleStatusChange = async (newStatus: string) => {
    setIsUpdating(true);
    setError(null);
    try {
      await api.updateDepositStatus(deposit.id, {
        status: newStatus,
        verification_remarks: remarks.trim() || undefined,
      });
      onUpdated();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update status.');
    } finally {
      setIsUpdating(false);
    }
  };

  const formatCurrency = (amt: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amt);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-xl w-full border border-slate-200 shadow-xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 border border-blue-200 flex items-center justify-center">
              <Landmark className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-900">
                  {deposit.fdr_number}
                </h3>
                <StatusBadge status={deposit.status} />
              </div>
              <p className="text-xs text-slate-500">
                {deposit.bank_name} {deposit.branch_name ? `• ${deposit.branch_name}` : ''}
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

        {/* Content */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Amount Spotlight */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-blue-700 uppercase tracking-wider">
                Deposit Lien Value
              </span>
              <div className="text-2xl font-black text-slate-900 mt-0.5">
                {formatCurrency(deposit.amount)}
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">FDR Lifecycle</span>
              <span className="text-xs font-semibold text-slate-700">
                {deposit.issue_date} to {deposit.maturity_date}
              </span>
            </div>
          </div>

          {/* Grid details */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="border border-slate-100 bg-slate-50/50 rounded-lg p-3">
              <span className="text-slate-500 block font-medium">Bank & IFSC</span>
              <span className="font-semibold text-slate-800 text-sm mt-0.5 block">
                {deposit.bank_name}
              </span>
              <span className="text-slate-600 font-mono text-[11px]">
                {deposit.ifsc_code || 'IFSC: Not specified'}
              </span>
            </div>

            <div className="border border-slate-100 bg-slate-50/50 rounded-lg p-3">
              <span className="text-slate-500 block font-medium">Affiliated Institution</span>
              <span className="font-semibold text-slate-800 text-sm mt-0.5 block truncate">
                {deposit.institution?.name || `Institution #${deposit.institution_id}`}
              </span>
              <span className="text-slate-600 font-mono text-[11px]">
                AICTE ID: {deposit.institution?.aicte_id || 'N/A'}
              </span>
            </div>
          </div>

          {/* Verification Audit Details */}
          <div className="border-t border-slate-100 pt-4 space-y-2 text-xs">
            <h4 className="font-semibold text-slate-800 flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-blue-600" />
              Scrutiny & Verification Audit
            </h4>
            
            {deposit.verified_by ? (
              <div className="bg-emerald-50/60 border border-emerald-200 rounded-lg p-3 text-emerald-900 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    Verified By: {deposit.verified_by.full_name}
                  </span>
                  <span className="text-[11px] text-emerald-700">
                    {deposit.verified_at ? new Date(deposit.verified_at).toLocaleDateString() : ''}
                  </span>
                </div>
                {deposit.verification_remarks && (
                  <p className="text-[11px] text-emerald-800 bg-white/70 p-2 rounded mt-1 border border-emerald-100">
                    "{deposit.verification_remarks}"
                  </p>
                )}
              </div>
            ) : (
              <div className="bg-amber-50/60 border border-amber-200 rounded-lg p-3 text-amber-900 flex items-center gap-2">
                <Clock className="w-4 h-4 shrink-0 text-amber-600" />
                <span>Awaiting officer scrutiny and bank confirmation.</span>
              </div>
            )}
          </div>

          {/* Role-Based Actions for Officer or Admin */}
          {canVerify && (
            <div className="border-t border-slate-100 pt-4 space-y-3">
              <label className="block text-xs font-semibold text-slate-800">
                Officer Scrutiny Remarks / Audit Note:
              </label>
              <textarea
                rows={2}
                placeholder="Enter verification findings, bank letter details, or deficiency notes..."
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                className="w-full text-xs rounded-lg border border-slate-300 p-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={isUpdating}
                  onClick={() => handleStatusChange('VERIFIED')}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-600 text-white hover:bg-sky-700 transition-colors shadow-xs"
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  Mark Verified
                </button>

                <button
                  type="button"
                  disabled={isUpdating}
                  onClick={() => handleStatusChange('ACTIVE')}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-xs"
                >
                  <FileCheck2 className="w-3.5 h-3.5" />
                  Activate Joint Lien
                </button>

                <button
                  type="button"
                  disabled={isUpdating}
                  onClick={() => handleStatusChange('REJECTED')}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors shadow-xs"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Reject Deposit
                </button>

                {deposit.status === 'ACTIVE' && (
                  <button
                    type="button"
                    disabled={isUpdating}
                    onClick={() => handleStatusChange('RELEASED')}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-700 text-white hover:bg-slate-800 transition-colors"
                  >
                    Release FDR
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-800 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
