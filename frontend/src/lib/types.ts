/**
 * TypeScript types for backend API responses (see DEVELOPMENT_PLAN.md "API contract").
 * Dates are ISO strings ("2024-09-30"), times are "HH:MM:SS" strings.
 */

export type Role = "employee" | "manager" | "hr" | "admin";

export type EmployeeStatus = "active" | "inactive" | "on_notice" | "terminated" | string;

export interface Employee {
  id: number;
  employee_code: string;
  name: string;
  department: string | null;
  designation: string | null;
  joining_date: string | null;
  status: EmployeeStatus;
  manager_id: number | null;
  manager_name?: string | null;
  email?: string | null;
  role?: Role | string | null;
  /** Only returned to HR/Admin or the employee themself (null otherwise). */
  monthly_gross_salary?: number | null;
}

export interface CurrentUser {
  user_id: number;
  email: string;
  role: Role;
  status: string;
  employee: Employee | null;
}

export interface LoginResponse {
  access_token: string;
  token_type?: string;
}

// ── Departments ─────────────────────────────────────────────────────────────

export interface Department {
  name: string;
  employee_count: number;
  active_count: number;
  designations: string[];
  managers: string[];
}

// ── Attendance ──────────────────────────────────────────────────────────────

export type AttendanceStatus = "present" | "absent" | "half_day" | "leave" | "holiday" | "weekend" | string;

export interface AttendanceRecord {
  id: number;
  employee_id: number;
  employee_name?: string;
  department?: string | null;
  attendance_date: string;
  in_time: string | null;
  out_time: string | null;
  working_minutes: number | null;
  status: AttendanceStatus;
  late_minutes: number;
  overtime_minutes: number;
}

export interface AttendanceSummary {
  total_days: number;
  present_days: number;
  absent_days: number;
  half_day_days: number;
  leave_days: number;
  holiday_days: number;
  weekend_days: number;
  late_days: number;
  overtime_days: number;
  total_working_minutes: number;
  total_overtime_minutes: number;
}

export interface DailyAttendanceRow {
  employee_id: number;
  employee_code: string;
  name: string;
  department: string | null;
  designation: string | null;
  status: AttendanceStatus;
  in_time: string | null;
  out_time: string | null;
  working_minutes: number | null;
  late_minutes: number | null;
  overtime_minutes: number | null;
}

export interface DailyAttendance {
  date: string;
  is_fallback_date: boolean;
  counts: {
    present: number;
    absent: number;
    late: number;
    half_day: number;
    leave: number;
    holiday: number;
    weekend: number;
    not_marked: number;
    total: number;
  };
  rows: DailyAttendanceRow[];
}

/** GET/POST /attendance/corrections… — a request to set one day's in/out time (D-033). */
export type CorrectionStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface AttendanceCorrection {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_code: string;
  department: string;
  attendance_date: string;
  requested_in_time: string;
  requested_out_time: string;
  reason: string;
  status: CorrectionStatus | string;
  requested_at: string;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  /** The record of that day as it is now (null = no record). */
  current_status: AttendanceStatus | null;
  current_in_time: string | null;
  current_out_time: string | null;
}

/** GET /attendance/records row (staff search, paginated — total in `X-Total-Count`). */
export interface AttendanceRecordRow extends AttendanceRecord {
  employee_code: string;
  employee_name: string;
  department: string;
}

// ── Holidays (D-034) ────────────────────────────────────────────────────────

export interface Holiday {
  /** null for national holidays (defined in code, cannot be removed). */
  id: number | null;
  date: string;
  name: string;
  kind: "national" | "company" | string;
  weekday: string;
}

export interface HolidayList {
  year: number;
  items: Holiday[];
}

// ── Leaves ──────────────────────────────────────────────────────────────────

export type LeaveType = "casual" | "sick" | "earned" | "unpaid" | "maternity" | "paternity";

export interface Leave {
  id: number;
  employee_id: number;
  leave_type: string;
  from_date: string;
  to_date: string;
  status: string;
  reason: string | null;
}

export interface LeaveListItem extends Leave {
  employee_name: string;
  employee_code?: string;
  department?: string | null;
  days?: number;
  applied_at?: string | null;
}

export interface LeaveBalance {
  leave_type: string;
  year?: number;
  entitled: number;
  used: number;
  pending: number;
  remaining: number;
}

// ── Salary ──────────────────────────────────────────────────────────────────

export interface SalaryRecord {
  id: number;
  employee_id: number;
  month: number;
  year: number;
  gross_salary: number;
  pf: number;
  deductions: number;
  overtime_amount: number;
  net_salary: number;
  paid_at: string | null;
  employee_name?: string;
  employee_code?: string;
  department?: string | null;
}

export interface PayrollLineItem {
  employee_id: number;
  employee_name: string;
  employee_code: string;
  department: string;
  gross_salary: number;
  working_days: number;
  paid_days: number;
  absent_days: number;
  half_days: number;
  unpaid_leave_days: number;
  lop_days: number;
  lop_deduction: number;
  pf: number;
  overtime_minutes: number;
  overtime_amount: number;
  deductions: number;
  net_salary: number;
  action: "created" | "updated";
}

export interface PayrollGenerateResult {
  month: number;
  year: number;
  working_days: number;
  provisional: boolean;
  created: number;
  updated: number;
  skipped: { employee_id: number; employee_name: string; reason: string }[];
  items: PayrollLineItem[];
}

/** POST /salary/mark-paid (D-036) — irreversible; paid rows are locked. */
export interface MarkPaidResult {
  marked: number[];
  already_paid: number[];
  not_found: number[];
  paid_at: string;
}

export interface SalaryList {
  month: number;
  year: number;
  items: SalaryRecord[];
}

export interface SalarySummary {
  month?: number | null;
  year?: number | null;
  total_gross_salary: number;
  total_pf: number;
  total_deductions: number;
  total_overtime_amount: number;
  total_net_salary: number;
  employee_count?: number;
  record_count?: number;
}

// ── Documents ───────────────────────────────────────────────────────────────

export interface HrDocument {
  id: number;
  name: string;
  file_name: string;
  file_type: string;
  version: number | string | null;
  status: string;
  uploaded_by: number | null;
  uploaded_by_name?: string | null;
  upload_date: string | null;
  chunk_count?: number | null;
}

// ── Chat ────────────────────────────────────────────────────────────────────

export interface ChatSource {
  document: string;
  page?: number | null;
  score?: number | null;
}

export interface ChatResponse {
  question: string;
  answer: string;
  intent?: string | null;
  source?: string | null;
  confidence?: number | string | null;
  page?: number | null;
  sources?: ChatSource[];
}

export interface ChatHistoryItem {
  id: number;
  question: string;
  response: string;
  detected_intent?: string | null;
  data_source?: string | null;
  timestamp: string;
}

export interface ChatLog {
  id: number;
  user_id: number | null;
  user_email?: string | null;
  question: string;
  detected_intent?: string | null;
  data_source?: string | null;
  response?: string | null;
  timestamp: string;
  response_time_ms?: number | null;
  error?: string | null;
}

// ── Users (admin) ───────────────────────────────────────────────────────────

export interface AppUser {
  id: number;
  email: string;
  role: Role;
  status: string;
  employee_id: number | null;
  employee_name?: string | null;
  employee_code?: string | null;
  created_at?: string | null;
}

// ── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardSummary {
  reference_date: string;
  is_fallback_date: boolean;
  month: string;
  kpis: {
    total_employees: number;
    present_today: number;
    absent_today: number;
    on_leave_today: number;
    late_today: number;
    total_overtime_hours: number;
  };
  department_attendance: { department: string; total_employees: number; present: number; absent: number; percentage: number }[];
  overtime_leaders: { name: string; department: string; overtime_hours: number }[];
  late_leaders: { name: string; department: string; late_count: number; total_late_minutes: number }[];
  leave_breakdown: { type: string; count: number }[];
  recent_leaves: {
    id: number;
    employee_name: string;
    department: string;
    leave_type: string;
    from_date: string;
    to_date: string;
    status: string;
    reason: string | null;
  }[];
  monthly_attendance?: {
    month: string;
    label: string;
    present: number;
    absent: number;
    late: number;
    half_day: number;
    leave: number;
    attendance_rate: number;
  }[];
}

export interface DashboardMe {
  employee: Employee | null;
  month_label: string;
  today: { status: string; in_time: string | null; out_time: string | null } | null;
  attendance: {
    present_days: number;
    absent_days: number;
    late_days: number;
    half_day_days: number;
    leave_days: number;
    total_working_minutes: number;
    total_overtime_minutes: number;
    attendance_percentage: number;
  };
  leave_balance: LeaveBalance[];
  latest_salary: {
    month: number;
    year: number;
    gross_salary: number;
    net_salary: number;
    pf: number;
    deductions: number;
    overtime_amount: number;
  } | null;
  team: {
    size: number;
    present_today: number;
    on_leave_today: number;
    pending_leaves: number;
    members: { id: number; name: string; designation: string | null; today_status: string | null }[];
  } | null;
}
