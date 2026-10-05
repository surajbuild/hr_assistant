/** Attendance records table + client-side month helpers shared by Attendance and Employee pages. */
import { CalendarCheck } from "lucide-react";
import { formatDate, formatMinutes, formatTime, monthShortLabel, parseDate } from "@/lib/format";
import type { AttendanceRecord } from "@/lib/types";
import { DataTable } from "./DataTable";
import { NativeSelect } from "./Field";
import { EmptyState } from "./States";
import { StatusBadge } from "./StatusBadge";

/** Distinct "YYYY-MM" keys present in the records, newest first. */
export function monthsInRecords(records: { attendance_date: string }[]): string[] {
  const set = new Set(records.map((r) => r.attendance_date.slice(0, 7)));
  return [...set].sort().reverse();
}

export function MonthKeySelect({
  months,
  value,
  onChange,
  allowAll = true,
}: {
  months: string[];
  value: string;
  onChange: (v: string) => void;
  allowAll?: boolean;
}) {
  return (
    <NativeSelect value={value} onChange={(e) => onChange(e.target.value)} aria-label="Month">
      {allowAll && <option value="">All months</option>}
      {months.map((m) => {
        const [y, mo] = m.split("-");
        return (
          <option key={m} value={m}>
            {monthShortLabel(Number(mo), Number(y))}
          </option>
        );
      })}
    </NativeSelect>
  );
}

export function AttendanceTable({
  records,
  showEmployee,
}: {
  records: AttendanceRecord[];
  showEmployee?: boolean;
}) {
  const sorted = [...records].sort((a, b) => b.attendance_date.localeCompare(a.attendance_date));
  return (
    <DataTable
      rows={sorted}
      rowKey={(r) => r.id}
      dense
      empty={<EmptyState icon={<CalendarCheck className="size-6" />} title="No attendance records" description="No records for the selected period." />}
      columns={[
        {
          key: "date",
          header: "Date",
          render: (r) => {
            const d = parseDate(r.attendance_date);
            return (
              <div>
                <p className="font-medium">{formatDate(r.attendance_date)}</p>
                <p className="text-xs text-ink-muted">{d?.toLocaleDateString("en-GB", { weekday: "long" })}</p>
              </div>
            );
          },
        },
        ...(showEmployee
          ? [
              {
                key: "emp",
                header: "Employee",
                render: (r: AttendanceRecord) => (
                  <div>
                    <p className="font-medium">{r.employee_name ?? `#${r.employee_id}`}</p>
                    {r.department && <p className="text-xs text-ink-muted">{r.department}</p>}
                  </div>
                ),
              },
            ]
          : []),
        { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
        { key: "in", header: "In", render: (r) => <span className="tabular-nums">{formatTime(r.in_time)}</span> },
        { key: "out", header: "Out", render: (r) => <span className="tabular-nums">{formatTime(r.out_time)}</span> },
        { key: "work", header: "Worked", render: (r) => <span className="tabular-nums">{r.working_minutes ? formatMinutes(r.working_minutes) : "—"}</span> },
        {
          key: "late",
          header: "Late",
          render: (r) => (r.late_minutes > 0 ? <span className="font-medium text-warning tabular-nums">{formatMinutes(r.late_minutes)}</span> : <span className="text-ink-muted">—</span>),
        },
        {
          key: "ot",
          header: "Overtime",
          render: (r) => (r.overtime_minutes > 0 ? <span className="font-medium text-brand tabular-nums">{formatMinutes(r.overtime_minutes)}</span> : <span className="text-ink-muted">—</span>),
        },
      ]}
    />
  );
}

/** Quick client-side summary for a set of records. */
export function summarize(records: AttendanceRecord[]) {
  let present = 0,
    absent = 0,
    half = 0,
    leave = 0,
    late = 0,
    work = 0,
    ot = 0;
  for (const r of records) {
    if (r.status === "present") present++;
    else if (r.status === "absent") absent++;
    else if (r.status === "half_day") half++;
    else if (r.status === "leave") leave++;
    if (r.late_minutes > 0) late++;
    work += r.working_minutes ?? 0;
    ot += r.overtime_minutes ?? 0;
  }
  return { present, absent, half, leave, late, work, ot };
}
