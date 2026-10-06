/**
 * Dashboard data helpers. Every number shown on the dashboard comes from an existing endpoint:
 *  - daily attendance trend ← GET /attendance/records?from_date&to_date (aggregated here, client-side)
 *  - pending approvals      ← GET /leaves?status=pending (own requests excluded — nobody approves their own leave)
 *  - payroll snapshot       ← GET /salary (latest month; totals summed here)
 * No new API, no mock data.
 */
import { useMemo } from "react";
import { monthRange } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import type { AttendanceRecord, LeaveListItem, SalaryList } from "@/lib/types";
import { qs } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

export interface DayCounts {
  date: string;
  day: string;
  present: number;
  late: number;
  half_day: number;
  leave: number;
  absent: number;
  /** Everyone physically counted as attending (present + late + half day). */
  attending: number;
}

/** Group a month of attendance records by day. Weekend/holiday-only days are skipped. */
export function aggregateDaily(records: AttendanceRecord[]): DayCounts[] {
  const map = new Map<string, DayCounts>();
  for (const r of records) {
    if (r.status === "weekend" || r.status === "holiday") continue;
    let d = map.get(r.attendance_date);
    if (!d) {
      d = { date: r.attendance_date, day: String(Number(r.attendance_date.slice(8, 10))), present: 0, late: 0, half_day: 0, leave: 0, absent: 0, attending: 0 };
      map.set(r.attendance_date, d);
    }
    if (r.status === "present") {
      if (r.late_minutes > 0) d.late++;
      else d.present++;
    } else if (r.status === "half_day") d.half_day++;
    else if (r.status === "leave") d.leave++;
    else if (r.status === "absent") d.absent++;
  }
  const out = [...map.values()].sort((a, b) => a.date.localeCompare(b.date));
  for (const d of out) d.attending = d.present + d.late + d.half_day;
  return out;
}

/** Month of `referenceDate` ("YYYY-MM-DD") → daily attendance for the whole company (hr/admin). */
export function useDailyTrend(referenceDate: string | undefined) {
  const range = useMemo(() => {
    if (!referenceDate) return null;
    const [y, m] = referenceDate.split("-").map(Number);
    return y && m ? { ...monthRange(m, y), year: y, month: m } : null;
  }, [referenceDate]);
  const state = useFetch<AttendanceRecord[]>(range ? `/attendance/records${qs({ from_date: range.from, to_date: range.to })}` : null);
  const days = useMemo(() => aggregateDaily(state.data ?? []), [state.data]);
  return { ...state, days, range };
}

function asList(data: LeaveListItem[] | { items: LeaveListItem[] } | null): LeaveListItem[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.items ?? []);
}

/** Pending leave requests this user may decide (own excluded). */
export function usePendingApprovals(enabled = true) {
  const { user } = useAuth();
  const state = useFetch<LeaveListItem[] | { items: LeaveListItem[] }>(enabled ? "/leaves?status=pending" : null);
  const myId = user?.employee?.id;
  const items = useMemo(() => asList(state.data).filter((l) => l.employee_id !== myId), [state.data, myId]);
  return { ...state, items };
}

export interface PayrollSnapshotData {
  month: number;
  year: number;
  employees: number;
  gross: number;
  net: number;
  overtime: number;
  paid: number;
  unpaid: number;
}

/** Latest payroll month, totalled from GET /salary (hr/admin). */
export function useLatestPayroll() {
  const state = useFetch<SalaryList>("/salary");
  const snapshot = useMemo<PayrollSnapshotData | null>(() => {
    const d = state.data;
    if (!d || d.items.length === 0) return null;
    const sum = (f: (r: SalaryList["items"][number]) => number) => d.items.reduce((s, r) => s + Number(f(r) || 0), 0);
    const paid = d.items.filter((r) => !!r.paid_at).length;
    return {
      month: d.month,
      year: d.year,
      employees: d.items.length,
      gross: sum((r) => r.gross_salary),
      net: sum((r) => r.net_salary),
      overtime: sum((r) => r.overtime_amount),
      paid,
      unpaid: d.items.length - paid,
    };
  }, [state.data]);
  return { ...state, snapshot };
}
