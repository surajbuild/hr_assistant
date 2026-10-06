/** Small helpers shared by the Attendance page parts (time strings, month keys, payroll locks). */
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { MONTHS_LONG, parseDate } from "@/lib/format";
import type { AttendanceCorrection, SalaryRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export const ATTENDANCE_STATUSES = ["present", "absent", "half_day", "leave", "holiday", "weekend"] as const;

/** "09:05:00" → "09:05" (for <input type="time">). */
export function hhmm(t: string | null | undefined): string {
  const m = t ? /^(\d{1,2}):(\d{2})/.exec(t) : null;
  return m ? `${m[1]!.padStart(2, "0")}:${m[2]}` : "";
}

/** "09:05" → minutes since midnight, or null. */
export function toMinutes(t: string | null | undefined): number | null {
  const m = t ? /^(\d{1,2}):(\d{2})/.exec(t) : null;
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** "09:05" → "09:05:00" (backend time format). */
export function withSeconds(t: string): string {
  return /^\d{2}:\d{2}$/.test(t) ? `${t}:00` : t;
}

/** "2024-09-30" → "2024-09". */
export function monthOf(iso: string): string {
  return iso.slice(0, 7);
}

export function monthName(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return `${MONTHS_LONG[(m ?? 1) - 1]} ${y}`;
}

export function shiftMonth(key: string, delta: number): string {
  const [y, m] = key.split("-").map(Number);
  const d = new Date(y!, (m ?? 1) - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function weekdayName(iso: string, style: "long" | "short" = "long"): string {
  return parseDate(iso)?.toLocaleDateString("en-GB", { weekday: style }) ?? "";
}

/** Months ("YYYY-MM") whose salary is already paid for the signed-in employee — attendance there is locked (D-021/D-033). */
export function useMyPaidMonths(enabled: boolean): Set<string> {
  const { data } = useFetch<SalaryRecord[]>(enabled ? "/salary/me" : null);
  return useMemo(() => new Set((data ?? []).filter((s) => s.paid_at).map((s) => `${s.year}-${String(s.month).padStart(2, "0")}`)), [data]);
}

/**
 * HR/Admin: `${employee_id}:${YYYY-MM}` keys of paid salary rows for the given months (GET /salary?month&year).
 * Used to hide the edit action on locked records instead of letting the API refuse it.
 */
export function usePaidKeys(months: string[], enabled: boolean): Set<string> {
  const key = enabled ? [...new Set(months)].sort().join(",") : "";
  const [paid, setPaid] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!key) {
      setPaid(new Set());
      return;
    }
    let alive = true;
    Promise.all(
      key.split(",").map((mk) => {
        const [y, m] = mk.split("-");
        return api.get<{ items: SalaryRecord[] }>(`/salary?month=${Number(m)}&year=${y}`).catch(() => ({ items: [] as SalaryRecord[] }));
      }),
    ).then((lists) => {
      if (!alive) return;
      const s = new Set<string>();
      for (const l of lists) for (const r of l.items ?? []) if (r.paid_at) s.add(`${r.employee_id}:${r.year}-${String(r.month).padStart(2, "0")}`);
      setPaid(s);
    });
    return () => {
      alive = false;
    };
  }, [key]);
  return paid;
}

/** Map of attendance_date → pending correction (own requests). */
export function pendingByDate(items: AttendanceCorrection[] | null | undefined): Map<string, AttendanceCorrection> {
  return new Map((items ?? []).filter((c) => c.status === "pending").map((c) => [c.attendance_date, c]));
}
