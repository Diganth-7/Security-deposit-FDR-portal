/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { TestRunnerModal } from './components/TestRunnerModal';
import { ApiDocsModal } from './components/ApiDocsModal';
import { api } from './api/client';
import { Shield, RefreshCw } from 'lucide-react';

function MainApp() {
  const { user, isLoading } = useAuth();
  const [backendHealthy, setBackendHealthy] = useState<boolean>(true);
  const [isTestRunnerOpen, setIsTestRunnerOpen] = useState<boolean>(false);
  const [isApiDocsOpen, setIsApiDocsOpen] = useState<boolean>(false);

  useEffect(() => {
    // Health check diagnostic
    const checkHealth = () => {
      api
        .getHealth()
        .then(() => setBackendHealthy(true))
        .catch(() => setBackendHealthy(false));
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center text-white">
        <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30 mb-4 animate-bounce">
          <Shield className="w-7 h-7" />
        </div>
        <div className="flex items-center gap-2 text-slate-300 font-mono text-xs">
          <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />
          <span>Initializing AICTE FDR Portal session...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen bg-slate-50/50 text-slate-900 flex flex-col">
      <Navbar
        onOpenTestRunner={() => setIsTestRunnerOpen(true)}
        onOpenApiDocs={() => setIsApiDocsOpen(true)}
        backendHealthy={backendHealthy}
      />

      <main className="flex-1">
        <DashboardPage />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-1">
          <p className="font-semibold text-slate-700">
            AICTE Security Deposit and Fixed Deposit Receipt (FDR) Management Portal
          </p>
          <p>
            Smart India Hackathon 2026 • Problem Statement: SIH26265 • All India Council for Technical Education (AICTE)
          </p>
          <p className="text-[11px] text-slate-400">
            Phase 1 Core Architecture: FastAPI + PostgreSQL + SQLAlchemy + Pydantic + React 19 + Tailwind CSS
          </p>
        </div>
      </footer>

      <TestRunnerModal
        isOpen={isTestRunnerOpen}
        onClose={() => setIsTestRunnerOpen(false)}
      />

      <ApiDocsModal
        isOpen={isApiDocsOpen}
        onClose={() => setIsApiDocsOpen(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}
