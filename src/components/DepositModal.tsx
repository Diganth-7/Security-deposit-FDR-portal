import React, { useState } from 'react';
import { api } from '../api/client';
import { Institution, User } from '../types';
import { X, ShieldAlert, Check, Calendar, Landmark, CreditCard, AlertCircle } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentUser: User;
  institutions: Institution[];
}

const COMMON_BANKS = [
  'State Bank of India',
  'Punjab National Bank',
  'Bank of Baroda',
  'Canara Bank',
  'Union Bank of India',
  'HDFC Bank',
  'ICICI Bank',
  'Axis Bank',
  'Kotak Mahindra Bank',
  'Bank of India'
];

export const DepositModal: React.FC<Props> = ({
  isOpen,
  onClose,
  onSuccess,
  currentUser,
  institutions,
}) => {
  const [fdrNumber, setFdrNumber] = useState('');
  const [amount, setAmount] = useState('');
  const [bankName, setBankName] = useState(COMMON_BANKS[0]);
  const [customBank, setCustomBank] = useState('');
  const [branchName, setBranchName] = useState('');
  const [ifscCode, setIfscCode] = useState('');
  const [issueDate, setIssueDate] = useState(new Date().toISOString().split('T')[0]);
  const [maturityDate, setMaturityDate] = useState(
    new Date(Date.now() + 365 * 3 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  );
  const [selectedInstId, setSelectedInstId] = useState<number | undefined>(
    currentUser.institution_id || (institutions.length > 0 ? institutions[0].id : undefined)
  );

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Deposit amount must be a positive number.');
      return;
    }

    if (!fdrNumber.trim()) {
      setError('FDR Certificate number is mandatory.');
      return;
    }

    if (new Date(maturityDate) <= new Date(issueDate)) {
      setError('Maturity date must be strictly after the issue date.');
      return;
    }

    const finalBank = bankName === 'OTHER' ? customBank.trim() : bankName;
    if (!finalBank) {
      setError('Please specify the issuing bank name.');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.createDeposit({
        fdr_number: fdrNumber.trim().toUpperCase(),
        amount: parsedAmount,
        bank_name: finalBank,
        branch_name: branchName.trim() || undefined,
        ifsc_code: ifscCode.trim().toUpperCase() || undefined,
        issue_date: issueDate,
        maturity_date: maturityDate,
        institution_id: currentUser.role === 'ADMIN' ? selectedInstId : undefined,
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to submit FDR deposit.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-base font-bold text-slate-900">
              Submit Fixed Deposit Receipt (FDR)
            </h3>
            <p className="text-xs text-slate-500">
              Mandatory AICTE security deposit verification submission
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Admin institution selector */}
          {currentUser.role === 'ADMIN' && institutions.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Target Affiliated Institution <span className="text-rose-500">*</span>
              </label>
              <select
                value={selectedInstId}
                onChange={(e) => setSelectedInstId(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {institutions.map((inst) => (
                  <option key={inst.id} value={inst.id}>
                    {inst.name} ({inst.aicte_id}) - {inst.state}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* FDR Number & Amount */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                FDR Certificate No. <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. FDR-SBI-2026-9812"
                value={fdrNumber}
                onChange={(e) => setFdrNumber(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase font-mono tracking-wide focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Deposit Amount (INR ₹) <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                placeholder="e.g. 2500000"
                min="1000"
                step="1000"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
              />
            </div>
          </div>

          {/* Bank Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Issuing Scheduled Bank <span className="text-rose-500">*</span>
            </label>
            <select
              value={bankName}
              onChange={(e) => setBankName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {COMMON_BANKS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
              <option value="OTHER">Other Scheduled Bank...</option>
            </select>
            {bankName === 'OTHER' && (
              <input
                type="text"
                placeholder="Enter Bank Name"
                value={customBank}
                onChange={(e) => setCustomBank(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            )}
          </div>

          {/* Branch & IFSC */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Branch Name
              </label>
              <input
                type="text"
                placeholder="e.g. Connaught Place"
                value={branchName}
                onChange={(e) => setBranchName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Bank IFSC Code
              </label>
              <input
                type="text"
                placeholder="e.g. SBIN0001067"
                value={ifscCode}
                onChange={(e) => setIfscCode(e.target.value)}
                maxLength={11}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Issue & Maturity Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Issue Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Maturity Date <span className="text-rose-500">*</span>
              </label>
              <input
                type="date"
                value={maturityDate}
                onChange={(e) => setMaturityDate(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* AICTE Lien Notice */}
          <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl text-amber-800 text-[11px] leading-relaxed">
            <strong>Statutory Compliance:</strong> Under AICTE Approval Process Handbook guidelines, all security FDRs must be drawn in the joint name of the Institute and AICTE Regional Officer, lien marked without maturity premature encashment.
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-xs"
            >
              {isSubmitting ? 'Registering...' : 'Submit for Scrutiny'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
