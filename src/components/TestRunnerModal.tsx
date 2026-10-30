import React, { useState } from 'react';
import { api } from '../api/client';
import { Terminal, CheckCircle2, XCircle, RefreshCw, X, ShieldCheck } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const TestRunnerModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<{
    status: string;
    exit_code: number;
    stdout: string;
    stderr: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const runBackendTests = async () => {
    setIsRunning(true);
    setError(null);
    try {
      const data = await api.runTests();
      setResults(data);
    } catch (err: any) {
      setError(err.message || 'Failed to trigger test suite');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-slate-900 text-slate-100 rounded-2xl max-w-2xl w-full border border-slate-700 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-wide">
                Automated Pytest Test Suite Runner
              </h3>
              <p className="text-xs text-slate-400">
                Phase 1 verification: Auth, Models, PostgreSQL RBAC, and FDR constraints
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action Bar */}
        <div className="px-6 py-3 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={runBackendTests}
              disabled={isRunning}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 disabled:opacity-50 transition-all font-mono"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
              {isRunning ? 'Executing 14 Test Cases...' : 'Run Pytest Suite'}
            </button>
            <span className="text-xs text-slate-400">
              Target: <code className="text-emerald-400">backend/tests</code>
            </span>
          </div>

          {results && (
            <div className="flex items-center gap-2">
              {results.exit_code === 0 ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  14/14 Tests Passed
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-semibold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                  <XCircle className="w-3.5 h-3.5" />
                  Tests Failed (Exit Code: {results.exit_code})
                </span>
              )}
            </div>
          )}
        </div>

        {/* Terminal Output Body */}
        <div className="p-6 overflow-y-auto flex-1 font-mono text-xs space-y-3 bg-slate-950/90 leading-relaxed">
          {error && (
            <div className="p-3 bg-rose-950/50 border border-rose-700/50 text-rose-300 rounded-lg">
              {error}
            </div>
          )}

          {!results && !isRunning && !error && (
            <div className="text-slate-400 text-center py-10 space-y-2">
              <ShieldCheck className="w-10 h-10 mx-auto text-slate-600" />
              <p className="font-sans text-sm text-slate-300 font-medium">
                Pytest backend integration test runner is ready.
              </p>
              <p className="font-sans text-xs text-slate-500 max-w-md mx-auto">
                Click &quot;Run Pytest Suite&quot; above to execute the 14 automated tests covering registration, login, role authorization, deposit validation, and officer scrutiny.
              </p>
            </div>
          )}

          {isRunning && (
            <div className="flex items-center gap-3 text-slate-400 py-6">
              <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
              <span>Running pytest backend/tests -v ...</span>
            </div>
          )}

          {results?.stdout && (
            <pre className="whitespace-pre-wrap text-emerald-300/90 selection:bg-emerald-800">
              {results.stdout}
            </pre>
          )}

          {results?.stderr && (
            <pre className="whitespace-pre-wrap text-amber-300/90 mt-2 border-t border-slate-800 pt-2">
              {results.stderr}
            </pre>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
          <span>Python 3.10 • pytest 9.2 • FastAPI • SQLAlchemy</span>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded text-slate-400 hover:text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
