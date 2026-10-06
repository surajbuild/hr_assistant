/**
 * Attendance records table + client-side month helpers shared by the Attendance and Employee pages.
 * Original props (`records`, `showEmployee`) are unchanged; everything else is optional:
 *  - actions     → trailing per-row actions column (e.g. "Request correction", "Edit")
 *  - mobileCards → card list below 768px instead of a horizontally scrolling table
 *  - holidays    → ISO date → holiday name, shown under the date
 *  - empty       → custom empty state
 *  - presorted   → keep the given order (server-sorted pages) instead of sorting newest first
 */
import type { ReactNode } from "react";
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

/** Late days are stored as status "present" with late minutes — show them as "Late" (same colour everywhere). */
function displayStatus(r: AttendanceRecord): string {
  return r.status === "present" && r.late_minutes > 0 ? "late" : r.status;
}

const dash = <span className="text-muted-foreground">—</span>;

export function AttendanceTable({
  records,
  showEmployee,
  actions,
  mobileCards,
  holidays,
  empty,
  presorted,
}: {
  records: AttendanceRecord[];
  showEmployee?: boolean;
  actions?: (r: AttendanceRecord) => ReactNode;
  mobileCards?: boolean;
  holidays?: Map<string, string>;
  empty?: ReactNode;
  presorted?: boolean;
}) {
  const sorted = presorted ? records : [...records].sort((a, b) => b.attendance_date.localeCompare(a.attendance_date));
  const weekday = (iso: string) => parseDate(iso)?.toLocaleDateString("en-GB", { weekday: "long" });
  return (
    <DataTable
      rows={sorted}
      rowKey={(r) => r.id}
      dense
      empty={empty ?? <EmptyState icon={<CalendarCheck className="size-6" />} title="No attendance records" description="No records for the selected period." />}
      mobileCard={
        mobileCards
          ? (r) => (
              <div className="flex items-start gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-foreground">{formatDate(r.attendance_date)}</p>
                    <StatusBadge status={displayStatus(r)} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {showEmployee && r.employee_name ? `${r.employee_name} · ` : ""}
                    {holidays?.get(r.attendance_date) ?? weekday(r.attendance_date)}
                  </p>
                  {(r.in_time || r.out_time) && (
                    <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                      {formatTime(r.in_time)} – {formatTime(r.out_time)}
                      {r.working_minutes ? ` · ${formatMinutes(r.working_minutes)}` : ""}
                      {r.late_minutes > 0 ? ` · ${formatMinutes(r.late_minutes)} late` : ""}
                      {r.overtime_minutes > 0 ? ` · ${formatMinutes(r.overtime_minutes)} OT` : ""}
                    </p>
                  )}
                </div>
                {actions && <div className="shrink-0">{actions(r)}</div>}
              </div>
            )
          : undefined
      }
      columns={[
        {
          key: "date",
          header: "Date",
          render: (r) => (
            <div>
              <p className="font-medium tabular-nums">{formatDate(r.attendance_date)}</p>
              <p className="text-xs text-muted-foreground">{holidays?.get(r.attendance_date) ?? weekday(r.attendance_date)}</p>
            </div>
          ),
        },
        ...(showEmployee
          ? [
              {
                key: "emp",
                header: "Employee",
                render: (r: AttendanceRecord) => (
                  <div>
                    <p className="font-medium">{r.employee_name ?? `#${r.employee_id}`}</p>
                    {r.department && <p className="text-xs text-muted-foreground">{r.department}</p>}
                  </div>
                ),
              },
            ]
          : []),
        { key: "status", header: "Status", render: (r) => <StatusBadge status={displayStatus(r)} /> },
        { key: "in", header: "In", render: (r) => <span className="tabular-nums">{formatTime(r.in_time)}</span> },
        { key: "out", header: "Out", render: (r) => <span className="tabular-nums">{formatTime(r.out_time)}</span> },
        { key: "work", header: "Worked", render: (r) => (r.working_minutes ? <span className="tabular-nums">{formatMinutes(r.working_minutes)}</span> : dash) },
        {
          key: "late",
          header: "Late",
          render: (r) => (r.late_minutes > 0 ? <span className="font-medium text-status-late-fg tabular-nums">{formatMinutes(r.late_minutes)}</span> : dash),
        },
        {
          key: "ot",
          header: "Overtime",
          render: (r) => (r.overtime_minutes > 0 ? <span className="font-medium text-brand-subtle-foreground tabular-nums">{formatMinutes(r.overtime_minutes)}</span> : dash),
        },
        ...(actions
          ? [
              {
                key: "actions",
                header: <span className="sr-only">Actions</span>,
                align: "right" as const,
                render: (r: AttendanceRecord) => <div className="flex justify-end">{actions(r)}</div>,
              },
            ]
          : []),
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
