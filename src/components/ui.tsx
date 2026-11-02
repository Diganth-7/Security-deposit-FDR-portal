import React, { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from 'react';
import { AlertCircle, RefreshCw, X, Inbox } from 'lucide-react';
import { errMsg } from '../lib/format';

export const btnPrimary =
  'inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs';
export const btnSecondary =
  'inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors';
export const btnDanger =
  'inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs';
export const btnSuccess =
  'inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-xs';
export const inputCls =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50';
export const cardCls = 'bg-white rounded-2xl border border-slate-200 shadow-xs';

export const ErrorBanner: React.FC<{ message?: string | null; onRetry?: () => void }> = ({ message, onRetry }) =>
  message ? (
    <div role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-start gap-2">
      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
      <span className="flex-1 break-words">{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-semibold underline">
          Retry
        </button>
      )}
    </div>
  ) : null;

export const Loading: React.FC<{ label?: string }> = ({ label = 'Loading...' }) => (
  <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2 text-sm" role="status">
    <RefreshCw className="w-4 h-4 animate-spin text-blue-600" />
    <span>{label}</span>
  </div>
);

export const Empty: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className="p-10 text-center text-slate-500 space-y-1">
    <Inbox className="w-7 h-7 mx-auto text-slate-300" />
    <p className="font-semibold text-sm">{title}</p>
    {hint && <p className="text-xs text-slate-400">{hint}</p>}
  </div>
);

export const Field: React.FC<{
  label: string;
  required?: boolean;
  hint?: string;
  children: (id: string) => React.ReactNode;
}> = ({ label, required, hint, children }) => {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">
        {label} {required && <span className="text-rose-500" aria-hidden="true">*</span>}
      </label>
      {children(id)}
      {hint && <p className="mt-1 text-[11px] text-slate-500">{hint}</p>}
    </div>
  );
};

export const Modal: React.FC<{
  title: string;
  subtitle?: string;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
}> = ({ title, subtitle, onClose, wide, children }) => {
  const titleId = useId();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 p-4 flex items-start sm:items-center justify-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`bg-white rounded-2xl w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} border border-slate-200 shadow-xl my-6`}
      >
        <div className="px-6 py-4 border-b border-slate-100 flex items-start justify-between bg-slate-50 rounded-t-2xl">
          <div>
            <h3 id={titleId} className="text-base font-bold text-slate-900">{title}</h3>
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
          <button type="button" aria-label="Close dialog" onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
};

/** Loads data and exposes loading/error state plus a reload function. */
export function useLoad<T>(fn: () => Promise<T>, deps: React.DependencyList, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const r = await fnRef.current();
      if (id === seq.current) setData(r);
    } catch (e) {
      if (id === seq.current) setError(errMsg(e));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) void reload();
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);

  return { data, error, loading, reload, setData };
}

interface AppCtx {
  openDeposit: (id: number) => void;
  dataVersion: number;
  bump: () => void;
}
export const AppContext = createContext<AppCtx>({ openDeposit: () => {}, dataVersion: 0, bump: () => {} });
export const useApp = () => useContext(AppContext);

export const SummaryCard: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-4">
    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
    <div className="mt-1 text-lg font-bold text-slate-900 break-words">{value}</div>
  </div>
);
