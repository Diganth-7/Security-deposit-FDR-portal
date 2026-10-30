import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, FileText, CheckCircle2, Terminal, BookOpen, LogOut, Building, UserCheck } from 'lucide-react';

interface NavbarProps {
  onOpenTestRunner: () => void;
  onOpenApiDocs: () => void;
  backendHealthy: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  onOpenTestRunner,
  onOpenApiDocs,
  backendHealthy,
}) => {
  const { user, logout } = useAuth();

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'ADMIN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
            <Shield className="w-3 h-3" />
            AICTE Administrator
          </span>
        );
      case 'OFFICER':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300">
            <UserCheck className="w-3 h-3" />
            Scrutiny Officer
          </span>
        );
      case 'INSTITUTION':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <Building className="w-3 h-3" />
            Institution User
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      {/* Tricolor Government Ribbon */}
      <div className="h-1 w-full flex">
        <div className="h-full w-1/3 bg-[#FF9933]"></div>
        <div className="h-full w-1/3 bg-white"></div>
        <div className="h-full w-1/3 bg-[#138808]"></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Portal Branding */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-600 via-amber-600 to-blue-800 flex items-center justify-center text-white shadow-sm ring-1 ring-slate-900/10">
              <Shield className="w-6 h-6 stroke-[2.2]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900 text-base tracking-tight leading-none">
                  AICTE FDR Portal
                </span>
                <span className="text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                  SIH26265
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Security Deposit & Fixed Deposit Receipt Management
              </p>
            </div>
          </div>

          {/* Center/Right Actions & User Profile */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Backend Health Diagnostic */}
            <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-50 border border-slate-200 text-slate-600">
              <div
                className={`w-2 h-2 rounded-full ${
                  backendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
                }`}
              />
              <span>FastAPI {backendHealthy ? 'Connected' : 'Offline'}</span>
            </div>

            {/* Test Suite Runner Button */}
            <button
              onClick={onOpenTestRunner}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-xs"
              title="Run automated pytest backend tests in real-time"
            >
              <Terminal className="w-3.5 h-3.5 text-emerald-400" />
              <span>Run Tests</span>
            </button>

            {/* Architecture / API Specs Button */}
            <button
              onClick={onOpenApiDocs}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5 text-blue-600" />
              <span>API Specs</span>
            </button>

            {/* User Info & Role Badge */}
            {user && (
              <div className="flex items-center gap-3 pl-2 border-l border-slate-200">
                <div className="text-right hidden sm:block">
                  <div className="text-xs font-semibold text-slate-900 line-clamp-1">
                    {user.full_name}
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono">
                    {user.email}
                  </div>
                </div>
                {getRoleBadge(user.role)}
                <button
                  onClick={logout}
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                  title="Sign Out"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
