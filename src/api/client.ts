import type {
  User, Institution, Deposit, DepositMaturityItem, DashboardStats, HealthStatus, Contract,
  DocumentRecord, ApprovalRequest, NotificationItem, AuditPage, ReportResult, ReportFilters,
  ReportName, DocumentType, ContractStatus, RequestStatus, RequestType,
} from '../types';

const API_BASE = '/api';
const TOKEN_KEY = 'aicte_auth_token';

export function getAuthToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setAuthToken(token: string): void {
  try { localStorage.setItem(TOKEN_KEY, token); } catch { /* storage unavailable */ }
}
export function removeAuthToken(): void {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  status: number;
  code?: string;
  requestId?: string;
  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

let unauthorizedHandler: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

function buildMessage(body: any, status: number, statusText: string): string {
  const detail = body?.detail ?? body?.error ?? body?.message;
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d: any) => {
        if (typeof d === 'string') return d;
        const field = d.field ?? (Array.isArray(d.loc) ? d.loc.filter((x: any) => x !== 'body').join('.') : '');
        const msg = d.message ?? d.msg ?? 'invalid value';
        return field ? `${field}: ${msg}` : msg;
      })
      .join('; ');
  }
  if (status === 502 || status === 503) return 'The server is unavailable or still starting. Please retry shortly.';
  return statusText || `Request failed (HTTP ${status})`;
}

async function rawFetch(endpoint: string, options: RequestInit = {}, base = API_BASE): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${base}${endpoint}`, { ...options, headers });
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0, 'NETWORK_ERROR');
  }

  if (!response.ok) {
    let body: any = null;
    try {
      body = await response.json();
    } catch { /* non-JSON error body */ }
    const isAuthCall = endpoint.startsWith('/auth/login') || endpoint.startsWith('/auth/register');
    if (response.status === 401 && !isAuthCall && token) {
      removeAuthToken();
      unauthorizedHandler?.();
    }
    throw new ApiError(
      buildMessage(body, response.status, response.statusText),
      response.status,
      body?.code,
      body?.request_id,
    );
  }
  return response;
}

async function request<T>(endpoint: string, options: RequestInit = {}, base = API_BASE): Promise<T> {
  const response = await rawFetch(endpoint, options, base);
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined as T;
  }
}

async function requestBlob(endpoint: string): Promise<Blob> {
  const response = await rawFetch(endpoint);
  return response.blob();
}

function qs(params?: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    }
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export interface DepositCreateInput {
  fdr_number: string;
  amount: number;
  bank_name: string;
  branch_name?: string;
  ifsc_code?: string;
  issue_date: string;
  maturity_date: string;
  institution_id?: number;
  contract_id?: number;
  contract_reference?: string;
}

export interface ContractInput {
  contract_number?: string;
  title: string;
  description?: string;
  contract_type?: string;
  contract_amount: number;
  required_deposit_amount: number;
  start_date: string;
  end_date: string;
  status?: ContractStatus;
  institution_id?: number;
}

export interface RegisterInput {
  email: string;
  full_name: string;
  password: string;
  role: string;
  institution_id?: number | null;
  aicte_id?: string;
}

export const api = {
  getHealth: () => request<HealthStatus>('/health'),

  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; user: User }>('/auth/login', json('POST', data)),
  register: (data: RegisterInput) => request<User>('/auth/register', json('POST', data)),
  getMe: () => request<User>('/auth/me'),

  getInstitutions: (params?: { state?: string; search?: string }) =>
    request<Institution[]>(`/institutions${qs(params)}`),
  createInstitution: (data: Partial<Institution>) => request<Institution>('/institutions', json('POST', data)),

  getDeposits: (params?: { status?: string; bank?: string; search?: string; institution_id?: number }) =>
    request<Deposit[]>(`/deposits${qs(params)}`),
  getDeposit: (id: number) => request<Deposit>(`/deposits/${id}`),
  createDeposit: (data: DepositCreateInput) => request<Deposit>('/deposits', json('POST', data)),
  updateDepositStatus: (id: number, data: { status: string; verification_remarks?: string }) =>
    request<Deposit>(`/deposits/${id}/status`, json('PATCH', data)),
  getUpcomingMaturities: (days = 30) => request<DepositMaturityItem[]>(`/deposits/upcoming-maturities${qs({ days })}`),
  getMaturedDeposits: () => request<DepositMaturityItem[]>('/deposits/matured'),
  getDepositDocuments: (id: number) => request<DocumentRecord[]>(`/deposits/${id}/documents`),

  getContracts: (params?: { status?: string; institution_id?: number; search?: string; insufficient_only?: boolean }) =>
    request<Contract[]>(`/contracts${qs(params as any)}`),
  getContract: (id: number) => request<Contract>(`/contracts/${id}`),
  createContract: (data: ContractInput) => request<Contract>('/contracts', json('POST', data)),
  updateContract: (id: number, data: Partial<ContractInput>) => request<Contract>(`/contracts/${id}`, json('PUT', data)),
  deleteContract: (id: number) => request<void>(`/contracts/${id}`, { method: 'DELETE' }),
  getContractDeposits: (id: number) => request<Deposit[]>(`/contracts/${id}/deposits`),
  linkDeposit: (contractId: number, depositId: number) =>
    request<Contract>(`/contracts/${contractId}/deposits/${depositId}`, { method: 'POST' }),

  uploadDocument: (data: { file: File; deposit_id: number; document_type: DocumentType; contract_id?: number }) => {
    const fd = new FormData();
    fd.append('file', data.file);
    fd.append('deposit_id', String(data.deposit_id));
    fd.append('document_type', data.document_type);
    if (data.contract_id) fd.append('contract_id', String(data.contract_id));
    return request<DocumentRecord>('/documents/upload', { method: 'POST', body: fd });
  },
  getDocuments: (params?: { deposit_id?: number; institution_id?: number; document_type?: string; status?: string }) =>
    request<DocumentRecord[]>(`/documents${qs(params)}`),
  getPendingDocuments: () => request<DocumentRecord[]>('/documents/pending'),
  downloadDocument: (id: number) => requestBlob(`/documents/${id}/download`),
  verifyDocument: (id: number, remarks?: string) =>
    request<DocumentRecord>(`/documents/${id}/verify`, json('PATCH', { remarks: remarks || undefined })),
  rejectDocument: (id: number, rejection_reason: string) =>
    request<DocumentRecord>(`/documents/${id}/reject`, json('PATCH', { rejection_reason })),

  submitRenewal: (data: { deposit_id: number; requested_tenure_months: number; description?: string; supporting_document_ids?: number[] }) =>
    request<ApprovalRequest>('/requests/renewal', json('POST', data)),
  submitRelease: (data: { deposit_id: number; justification: string; compliance_reference?: string; supporting_document_ids?: number[] }) =>
    request<ApprovalRequest>('/requests/release', json('POST', data)),
  submitForfeiture: (data: { deposit_id: number; violation_reason: string; statutory_clause: string; description?: string }) =>
    request<ApprovalRequest>('/requests/forfeiture', json('POST', data)),
  getMyRequests: (params?: { status?: RequestStatus | string; request_type?: RequestType | string }) =>
    request<ApprovalRequest[]>(`/requests/my-requests${qs(params)}`),
  getPendingRequests: () => request<ApprovalRequest[]>('/requests/pending'),
  getRequest: (id: number) => request<ApprovalRequest>(`/requests/${id}`),
  assignRequest: (id: number, officer_id?: number) => request<ApprovalRequest>(`/requests/${id}/assign`, json('PATCH', { officer_id })),
  approveRequest: (id: number, data: { decision_remarks: string; extended_maturity_date?: string }) =>
    request<ApprovalRequest>(`/requests/${id}/approve`, json('PATCH', data)),
  rejectRequest: (id: number, rejection_reason: string) =>
    request<ApprovalRequest>(`/requests/${id}/reject`, json('PATCH', { rejection_reason })),
  cancelRequest: (id: number) => request<ApprovalRequest>(`/requests/${id}/cancel`, { method: 'PATCH' }),

  getNotifications: (params?: { unread_only?: boolean; limit?: number; offset?: number }) =>
    request<NotificationItem[]>(`/notifications${qs(params as any)}`),
  getUnreadCount: () => request<{ unread_count: number }>('/notifications/unread-count'),
  markNotificationRead: (id: number) => request<NotificationItem>(`/notifications/${id}/read`, { method: 'PATCH' }),

  getDashboardStats: () => request<DashboardStats>('/stats/dashboard'),

  getAuditLogs: (params: Record<string, string | number | undefined>) => request<AuditPage>(`/audit-logs${qs(params)}`),
  getEntityAudit: (type: string, id: number, params?: { limit?: number; offset?: number }) =>
    request<AuditPage>(`/audit-logs/${type}/${id}${qs(params)}`),

  getReport: (name: ReportName, filters: ReportFilters) => request<ReportResult>(`/reports/${name}${qs(filters as any)}`),
  exportReportCsv: (name: ReportName, filters: ReportFilters) =>
    requestBlob(`/reports/export/csv${qs({ report: name, ...(filters as any) })}`),

  getOpenApi: () => request<any>('/openapi.json', {}, ''),

  runTests: () =>
    request<{ status: string; exit_code: number; stdout: string; stderr: string }>('/tests/run', { method: 'POST' }),
};
