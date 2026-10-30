export type UserRole = 'ADMIN' | 'INSTITUTION' | 'OFFICER';

export type DepositStatus =
  | 'PENDING_VERIFICATION'
  | 'VERIFIED'
  | 'ACTIVE'
  | 'MATURED'
  | 'RELEASED'
  | 'REJECTED';

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
  address?: string;
  institute_type: string;
  contact_email: string;
  contact_phone?: string;
  created_at: string;
}

export interface Deposit {
  id: number;
  fdr_number: string;
  amount: number;
  bank_name: string;
  branch_name?: string;
  ifsc_code?: string;
  issue_date: string;
  maturity_date: string;
  status: DepositStatus;
  institution_id: number;
  submitted_by_id: number;
  verified_by_id?: number | null;
  verification_remarks?: string | null;
  verified_at?: string | null;
  created_at: string;
  updated_at: string;
  institution?: Institution;
  submitted_by?: User;
  verified_by?: User;
}

export interface DashboardStats {
  total_count: number;
  total_amount: number;
  pending_count: number;
  verified_count: number;
  active_count: number;
  matured_count: number;
  rejected_count: number;
  institutions_count: number;
  role: UserRole;
  user_name: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  problem_statement: string;
  database_backend: string;
  version: string;
  phase: string;
}
