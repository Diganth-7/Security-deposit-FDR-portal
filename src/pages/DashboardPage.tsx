import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { Deposit, Institution, DashboardStats, DepositStatus } from '../types';
import { MetricCard } from '../components/MetricCard';
import { StatusBadge } from '../components/StatusBadge';
import { DepositModal } from '../components/DepositModal';
import { DepositDetailsModal } from '../components/DepositDetailsModal';
import {
  Shield,
  Plus,
  Landmark,
  Building,
  CheckCircle2,
  Clock,
  Search,
  Filter,
  RefreshCw,
  Calendar,
  AlertTriangle,
  FileText,
  Eye,
  SlidersHorizontal,
  ChevronRight,
  ExternalLink
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [deposits, setDeposits] = useState<Deposit[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [activeTab, setActiveTab] = useState<'deposits' | 'institutions'>('deposits');

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [isDepositModalOpen, setIsDepositModalOpen] = useState(false);
  const [selectedDeposit, setSelectedDeposit] = useState<Deposit | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  // New Institution Modal for Admin
  const [isAddInstOpen, setIsAddInstOpen] = useState(false);
  const [newInstAicteId, setNewInstAicteId] = useState('');
  const [newInstName, setNewInstName] = useState('');
  const [newInstState, setNewInstState] = useState('');
  const [newInstCity, setNewInstCity] = useState('');
  const [newInstEmail, setNewInstEmail] = useState('');
  const [instError, setInstError] = useState<string | null>(null);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [statsData, depositsData, institutionsData] = await Promise.all([
        api.getDashboardStats().catch(() => null),
        api.getDeposits(),
        api.getInstitutions(),
      ]);

      if (statsData) setStats(statsData);
      setDeposits(depositsData);
      setInstitutions(institutionsData);
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateInstitution = async (e: React.FormEvent) => {
    e.preventDefault();
    setInstError(null);
    try {
      await api.createInstitution({
        aicte_id: newInstAicteId.trim(),
        name: newInstName.trim(),
        state: newInstState.trim(),
        city: newInstCity.trim(),
        contact_email: newInstEmail.trim(),
      });
      setIsAddInstOpen(false);
      setNewInstAicteId('');
      setNewInstName('');
      setNewInstState('');
      setNewInstCity('');
      setNewInstEmail('');
      fetchData();
    } catch (err: any) {
      setInstError(err.message || 'Failed to create institution');
    }
  };

  const formatCurrency = (amt?: number) => {
    if (!amt && amt !== 0) return '₹ 0';
    if (amt >= 10000000) {
      return `₹ ${(amt / 10000000).toFixed(2)} Cr`;
    }
    if (amt >= 100000) {
      return `₹ ${(amt / 100000).toFixed(2)} L`;
    }
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(amt);
  };

  // Filtered deposits
  const filteredDeposits = deposits.filter((d) => {
    const matchesStatus = statusFilter === 'ALL' || d.status === statusFilter;
    const matchesSearch =
      d.fdr_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.bank_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (d.institution?.name && d.institution.name.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Role Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 text-white rounded-2xl p-6 shadow-md border border-slate-800">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded text-[11px] font-bold tracking-wider uppercase bg-blue-500/20 text-blue-300 border border-blue-400/30">
                {user?.role} PORTAL WORKSPACE
              </span>
              <span className="text-xs text-slate-400">SIH 2026 AICTE Architecture</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight">
              Welcome, {user?.full_name}
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl leading-relaxed">
              {user?.role === 'ADMIN' &&
                'Directorate Access: Pan-India monitoring of statutory fixed deposit receipts, approved colleges, scrutiny workflows, and lien management.'}
              {user?.role === 'OFFICER' &&
                'Regional Scrutiny Queue: Inspect FDR certificates, verify bank confirmation documents, and validate mandatory joint lien conditions.'}
              {user?.role === 'INSTITUTION' &&
                'Institutional Compliance: Submit mandatory Fixed Deposit Receipts for course intake approval, track review status, and maintain statutory security deposits.'}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {user?.role !== 'OFFICER' && (
              <button
                onClick={() => setIsDepositModalOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-xl bg-blue-500 hover:bg-blue-400 text-white transition-all shadow-md shadow-blue-500/20"
              >
                <Plus className="w-4 h-4" />
                <span>Submit New FDR</span>
              </button>
            )}
            <button
              onClick={fetchData}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              title="Refresh Data"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Security Deposits"
          value={formatCurrency(stats?.total_amount)}
          subtitle={`${stats?.total_count || 0} Total Registered FDRs`}
          icon={<Landmark className="w-5 h-5" />}
          badgeColor="bg-blue-50 text-blue-700 border-blue-200"
        />

        <MetricCard
          title="Pending Verification"
          value={stats?.pending_count || 0}
          subtitle="Awaiting officer scrutiny"
          icon={<Clock className="w-5 h-5" />}
          badgeColor="bg-amber-50 text-amber-700 border-amber-200"
        />

        <MetricCard
          title="Verified & Active Liens"
          value={(stats?.verified_count || 0) + (stats?.active_count || 0)}
          subtitle="Statutory compliance active"
          icon={<CheckCircle2 className="w-5 h-5" />}
          badgeColor="bg-emerald-50 text-emerald-700 border-emerald-200"
        />

        <MetricCard
          title="Affiliated Institutions"
          value={institutions.length}
          subtitle="AICTE Approved technical colleges"
          icon={<Building className="w-5 h-5" />}
          badgeColor="bg-indigo-50 text-indigo-700 border-indigo-200"
        />
      </div>

      {/* Main Tab Controller & Search */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        {/* Tab Headers */}
        <div className="p-4 sm:px-6 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-50/50">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('deposits')}
              className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === 'deposits'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              <FileText className="w-4 h-4" />
              <span>Fixed Deposit Receipts ({filteredDeposits.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('institutions')}
              className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === 'institutions'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
              }`}
            >
              <Building className="w-4 h-4" />
              <span>Approved Institutions ({institutions.length})</span>
            </button>
          </div>

          {/* Search & Status Filters (Deposits Tab) */}
          {activeTab === 'deposits' && (
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search FDR #, bank, college..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white w-48 sm:w-56"
                />
              </div>

              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white font-medium text-slate-700"
              >
                <option value="ALL">All Statuses</option>
                <option value="PENDING_VERIFICATION">Pending Verification</option>
                <option value="VERIFIED">Verified</option>
                <option value="ACTIVE">Active Lien</option>
                <option value="MATURED">Matured</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </div>
          )}

          {activeTab === 'institutions' && user?.role === 'ADMIN' && (
            <button
              onClick={() => setIsAddInstOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Affiliated Institution</span>
            </button>
          )}
        </div>

        {/* Tab 1: Deposits Table */}
        {activeTab === 'deposits' && (
          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="p-12 text-center text-slate-400 flex items-center justify-center gap-2 text-sm">
                <RefreshCw className="w-4 h-4 animate-spin text-blue-600" />
                <span>Loading FDR deposit records from backend...</span>
              </div>
            ) : filteredDeposits.length === 0 ? (
              <div className="p-12 text-center text-slate-500 space-y-2">
                <FileText className="w-8 h-8 mx-auto text-slate-300" />
                <p className="font-semibold text-sm">No Fixed Deposit Receipts Found</p>
                <p className="text-xs text-slate-400">
                  {searchQuery || statusFilter !== 'ALL'
                    ? 'Try adjusting your search criteria or status filter.'
                    : 'Submit a new FDR deposit to begin the scrutiny workflow.'}
                </p>
              </div>
            ) : (
              <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                <thead className="bg-slate-50 text-slate-600 font-bold uppercase tracking-wider">
                  <tr>
                    <th className="px-6 py-3">FDR Certificate</th>
                    <th className="px-6 py-3">Issuing Bank & Branch</th>
                    <th className="px-6 py-3">Lien Amount</th>
                    <th className="px-6 py-3">Validity Window</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {filteredDeposits.map((dep) => (
                    <tr key={dep.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-mono font-bold text-slate-900 text-sm">
                          {dep.fdr_number}
                        </div>
                        <div className="text-[11px] text-slate-500 font-sans mt-0.5">
                          {dep.institution?.name || `Institution #${dep.institution_id}`}
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <div className="font-semibold text-slate-800">
                          {dep.bank_name}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {dep.branch_name || 'Main Branch'}{' '}
                          {dep.ifsc_code && `(${dep.ifsc_code})`}
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <div className="font-bold text-slate-900 text-sm">
                          {formatCurrency(dep.amount)}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          INR (Indian Rupees)
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <div className="text-slate-800 font-medium">
                          Issue: {dep.issue_date}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Matures: {dep.maturity_date}
                        </div>
                      </td>

                      <td className="px-6 py-4">
                        <StatusBadge status={dep.status} />
                      </td>

                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => {
                            setSelectedDeposit(dep);
                            setIsDetailsModalOpen(true);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>
                            {user?.role === 'OFFICER' || user?.role === 'ADMIN'
                              ? 'Scrutinize'
                              : 'Details'}
                          </span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Tab 2: Institutions Directory */}
        {activeTab === 'institutions' && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-slate-600 font-bold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3">AICTE ID</th>
                  <th className="px-6 py-3">Institution Name</th>
                  <th className="px-6 py-3">Location</th>
                  <th className="px-6 py-3">Category</th>
                  <th className="px-6 py-3">Official Email</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {institutions.map((inst) => (
                  <tr key={inst.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-6 py-4 font-mono font-bold text-blue-700">
                      {inst.aicte_id}
                    </td>
                    <td className="px-6 py-4 font-semibold text-slate-900 text-sm">
                      {inst.name}
                    </td>
                    <td className="px-6 py-4 text-slate-700">
                      {inst.city}, <span className="font-semibold">{inst.state}</span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                        {inst.institute_type}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-slate-600">
                      {inst.contact_email}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      {user && (
        <DepositModal
          isOpen={isDepositModalOpen}
          onClose={() => setIsDepositModalOpen(false)}
          onSuccess={fetchData}
          currentUser={user}
          institutions={institutions}
        />
      )}

      {user && (
        <DepositDetailsModal
          deposit={selectedDeposit}
          isOpen={isDetailsModalOpen}
          onClose={() => setIsDetailsModalOpen(false)}
          onUpdated={fetchData}
          currentUser={user}
        />
      )}

      {/* Admin Add Institution Modal */}
      {isAddInstOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full border border-slate-200 shadow-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <h3 className="text-sm font-bold text-slate-900">
                Register Affiliated Institution
              </h3>
              <button
                onClick={() => setIsAddInstOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                &times;
              </button>
            </div>
            <form onSubmit={handleCreateInstitution} className="p-6 space-y-3 text-xs">
              {instError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-rose-700">
                  {instError}
                </div>
              )}
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  AICTE Permanent ID *
                </label>
                <input
                  type="text"
                  placeholder="e.g. 1-88492019"
                  value={newInstAicteId}
                  onChange={(e) => setNewInstAicteId(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-300 p-2 font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Institution Full Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. National Institute of Technology"
                  value={newInstName}
                  onChange={(e) => setNewInstName(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-300 p-2"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">State *</label>
                  <input
                    type="text"
                    placeholder="e.g. Delhi"
                    value={newInstState}
                    onChange={(e) => setNewInstState(e.target.value)}
                    required
                    className="w-full rounded-lg border border-slate-300 p-2"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">City *</label>
                  <input
                    type="text"
                    placeholder="e.g. New Delhi"
                    value={newInstCity}
                    onChange={(e) => setNewInstCity(e.target.value)}
                    required
                    className="w-full rounded-lg border border-slate-300 p-2"
                  />
                </div>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Registrar / Principal Email *
                </label>
                <input
                  type="email"
                  placeholder="e.g. principal@nit.ac.in"
                  value={newInstEmail}
                  onChange={(e) => setNewInstEmail(e.target.value)}
                  required
                  className="w-full rounded-lg border border-slate-300 p-2"
                />
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setIsAddInstOpen(false)}
                  className="px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700"
                >
                  Save Institution
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
