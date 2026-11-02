export type UserRole = 'ADMIN' | 'INSTITUTION' | 'OFFICER';

export const DEPOSIT_STATUSES = [
  'PENDING_VERIFICATION',
  'VERIFIED',
  'ACTIVE',
  'MATURITY_APPROACHING',
  'MATURED',
  'MATURED_ACTION_REQUIRED',
  'RENEWAL_REQUESTED',
  'RELEASE_REQUESTED',
  'FORFEITURE_REQUESTED',
  'RELEASED',
  'REJECTED',
  'CLOSED',
] as const;
export type DepositStatus = (typeof DEPOSIT_STATUSES)[number];

export type RequestType = 'RENEWAL' | 'RELEASE' | 'FORFEITURE';
export const REQUEST_STATUSES = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CANCELLED'] as const;
export type RequestStatus = (typeof REQUEST_STATUSES)[number];

export type ContractStatus = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'EXPIRED' | 'TERMINATED';
export const CONTRACT_STATUSES: ContractStatus[] = ['DRAFT', 'ACTIVE', 'COMPLETED', 'EXPIRED', 'TERMINATED'];

export type DocumentType =
  | 'FDR_CERTIFICATE'
  | 'BANK_RECEIPT'
  | 'CONTRACT_DOCUMENT'
  | 'RENEWAL_DOCUMENT'
  | 'RELEASE_DOCUMENT'
  | 'OTHER';
export const DOCUMENT_TYPES: DocumentType[] = [
  'FDR_CERTIFICATE',
  'BANK_RECEIPT',
  'CONTRACT_DOCUMENT',
  'RENEWAL_DOCUMENT',
  'RELEASE_DOCUMENT',
  'OTHER',
];
export type DocumentVerificationStatus = 'PENDING' | 'VERIFIED' | 'REJECTED';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  institution_id?: number | null;
  is_active: boolean;
  created_at: string;
}

export interface Institution {
  id: number;
  aicte_id: string;
  name: string;
  state: string;
  city: string;
  address?: string | null;
  institute_type: string;
  contact_email: string;
  contact_phone?: string | null;
  created_at: string;
}

export interface Deposit {
  id: number;
  fdr_number: string;
  amount: number;
  bank_name: string;
  branch_name?: string | null;
  ifsc_code?: string | null;
  issue_date: string;
  maturity_date: string;
  contract_reference?: string | null;
  contract_id?: number | null;
  status: DepositStatus;
  institution_id: number;
  submitted_by_id: number;
  verified_by_id?: number | null;
  verification_remarks?: string | null;
  verified_at?: string | null;
  created_at: string;
  updated_at: string;
  institution?: Institution | null;
  submitted_by?: User | null;
  verified_by?: User | null;
}

export interface DepositMaturityItem {
  id: number;
  fdr_number: string;
  amount: number;
  bank_name: string;
  issue_date: string;
  maturity_date: string;
  status: DepositStatus;
  contract_reference?: string | null;
  institution_id: number;
  institution_name?: string | null;
  days_remaining: number;
  maturity_status: string;
}

export interface DashboardStats {
  total_count: number;
  total_amount: number;
  pending_count: number;
  verified_count: number;
  active_count: number;
  matured_count: number;
  rejected_count: number;
  total_active_fdrs: number;
  maturing_within_30_days: number;
  maturing_within_7_days: number;
  maturing_within_1_day: number;
  matured_action_required: number;
  renewal_requests_pending: number;
  release_requests_pending: number;
  forfeiture_requests_pending: number;
  institutions_count: number;
  role: UserRole;
  user_name: string;
}

export interface Contract {
  id: number;
  contract_number: string;
  title: string;
  description?: string | null;
  institution_id: number;
  contract_type: string;
  contract_amount: number;
  required_deposit_amount: number;
  start_date: string;
  end_date: string;
  status: ContractStatus;
  created_at: string;
  updated_at: string;
  total_deposited_amount: number;
  is_deposit_sufficient: boolean;
  deposit_shortfall: number;
  linked_deposits_count: number;
  institution?: Institution | null;
}

export interface DocumentRecord {
  id: number;
  deposit_id: number;
  institution_id: number;
  contract_id?: number | null;
  original_filename: string;
  document_type: DocumentType;
  file_size: number;
  mime_type: string;
  upload_timestamp: string;
  uploaded_by_id: number;
  verification_status: DocumentVerificationStatus;
  verified_by_id?: number | null;
  verification_timestamp?: string | null;
  rejection_reason?: string | null;
}

export interface ApprovalRequest {
  id: number;
  deposit_id: number;
  institution_id: number;
  contract_id?: number | null;
  request_type: RequestType;
  status: RequestStatus;
  description?: string | null;
  supporting_document_ids?: string | null;
  requested_tenure_months?: number | null;
  extended_maturity_date?: string | null;
  compliance_reference?: string | null;
  statutory_clause?: string | null;
  violation_reason?: string | null;
  requested_by_id: number;
  assigned_officer_id?: number | null;
  decided_by_id?: number | null;
  submitted_at: string;
  reviewed_at?: string | null;
  decision_reason?: string | null;
  fdr_number?: string | null;
  deposit_amount?: number | null;
  institution_name?: string | null;
  requested_by_name?: string | null;
  assigned_officer_name?: string | null;
  decided_by_name?: string | null;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  reminder_type: string;
  days_remaining?: number | null;
  deposit_id: number;
  institution_id?: number | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_id?: number | null;
  actor_name?: string | null;
  actor_role?: string | null;
  action: string;
  entity_type?: string | null;
  entity_id?: number | null;
  deposit_id?: number | null;
  institution_id?: number | null;
  details?: string | null;
  before?: unknown;
  after?: unknown;
  correlation_id?: string | null;
  timestamp: string;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export type ReportName = 'fdr-summary' | 'maturity' | 'approvals' | 'document-status' | 'contract-coverage';

export interface ReportResult {
  report: string;
  title: string;
  generated_at: string;
  filters: Record<string, unknown>;
  summary: Record<string, unknown>;
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
  truncated: boolean;
}

export interface ReportFilters {
  date_from?: string;
  date_to?: string;
  institution_id?: string;
  contract_id?: string;
  fdr_status?: string;
  request_status?: string;
  days_ahead?: string;
}

export interface HealthStatus {
  status: string;
  database_backend?: string;
  database_ok?: boolean;
  environment?: string;
  date?: string;
  version?: string;
}
