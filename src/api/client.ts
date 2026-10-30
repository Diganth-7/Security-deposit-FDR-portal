import { User, Institution, Deposit, DashboardStats, HealthStatus } from '../types';

const API_BASE = '/api';

export function getAuthToken(): string | null {
  return localStorage.getItem('aicte_auth_token');
}

export function setAuthToken(token: string): void {
  localStorage.setItem('aicte_auth_token', token);
}

export function removeAuthToken(): void {
  localStorage.removeItem('aicte_auth_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorJson.error || errorDetail;
    } catch {
      errorDetail = response.statusText || errorDetail;
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // Health
  getHealth: () => request<HealthStatus>('/health'),

  // Auth
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  register: (data: {
    email: string;
    full_name: string;
    password: string;
    role: string;
    institution_id?: number | null;
  }) =>
    request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMe: () => request<User>('/auth/me'),

  // Institutions
  getInstitutions: (params?: { state?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.state) query.set('state', params.state);
    if (params?.search) query.set('search', params.search);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return request<Institution[]>(`/institutions${qs}`);
  },

  getInstitution: (id: number) => request<Institution>(`/institutions/${id}`),

  createInstitution: (data: Partial<Institution>) =>
    request<Institution>('/institutions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Deposits
  getDeposits: (params?: { status?: string; bank?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.bank) query.set('bank', params.bank);
    if (params?.search) query.set('search', params.search);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return request<Deposit[]>(`/deposits${qs}`);
  },

  getDeposit: (id: number) => request<Deposit>(`/deposits/${id}`),

  createDeposit: (data: {
    fdr_number: string;
    amount: number;
    bank_name: string;
    branch_name?: string;
    ifsc_code?: string;
    issue_date: string;
    maturity_date: string;
    institution_id?: number;
  }) =>
    request<Deposit>('/deposits', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateDepositStatus: (
    id: number,
    data: { status: string; verification_remarks?: string }
  ) =>
    request<Deposit>(`/deposits/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Stats
  getDashboardStats: () => request<DashboardStats>('/stats/dashboard'),

  // Test Runner
  runTests: () =>
    request<{
      status: string;
      exit_code: number;
      stdout: string;
      stderr: string;
    }>('/tests/run', {
      method: 'POST',
    }),
};
