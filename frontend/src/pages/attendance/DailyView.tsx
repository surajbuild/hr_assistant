/** Daily view (admin / hr / manager-team): GET /attendance/daily?date — status chips with counts, search, table/cards. */
import { useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight, Info, Users } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { SearchInput } from "@/components/Field";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { qs } from "@/lib/api";
import { formatDate, formatMinutes, formatTime, parseDate, toISODate } from "@/lib/format";
import type { DailyAttendance, DailyAttendanceRow } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";
import { weekdayName } from "./shared";

const COUNT_KEYS: { key: keyof DailyAttendance["counts"]; label: string; dot?: string }[] = [
  { key: "total", label: "All" },
  { key: "present", label: "Present", dot: "bg-status-present" },
  { key: "late", label: "Late", dot: "bg-status-late" },
  { key: "half_day", label: "Half day", dot: "bg-status-half" },
  { key: "leave", label: "Leave", dot: "bg-status-leave" },
  { key: "absent", label: "Absent", dot: "bg-status-absent" },
  { key: "holiday", label: "Holiday", dot: "bg-status-neutral" },
  { key: "weekend", label: "Weekend", dot: "bg-status-neutral" },
  { key: "not_marked", label: "Not marked", dot: "bg-status-neutral" },
];

const rowStatus = (r: DailyAttendanceRow) => (r.status === "present" && (r.late_minutes ?? 0) > 0 ? "late" : r.status);
const dash = <span className="text-muted-foreground">—</span>;

export function DailyView({ role }: { role: string | null }) {
  const [date, setDate] = useState("");
  const [status, setStatus] = useState<string>("total");
  const [search, setSearch] = useState("");
  const { data, loading, error, reload } = useFetch<DailyAttendance>(`/attendance/daily${qs({ date })}`);
  const today = toISODate(new Date());
  const shownDate = date || data?.date || "";

  function shift(delta: number) {
    const d = parseDate(shownDate) ?? new Date();
    d.setDate(d.getDate() + delta);
    setDate(toISODate(d));
  }

  const q = search.trim().toLowerCase();
  const rows = (data?.rows ?? []).filter((r) => {
    if (status === "late" ? !(r.late_minutes && r.late_minutes > 0) : status !== "total" && r.status !== status) return false;
    return !q || r.name.toLowerCase().includes(q) || r.employee_code.toLowerCase().includes(q) || (r.department ?? "").toLowerCase().includes(q);
  });
  const filtered = status !== "total" || !!q;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 md:flex-row md:items-center">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => shift(-1)} aria-label="Previous day" disabled={!shownDate}>
            <ChevronLeft />
          </Button>
          <label htmlFor="daily-date" className="sr-only">
            Date
          </label>
          <Input id="daily-date" type="date" max={today} value={shownDate} onChange={(e) => setDate(e.target.value)} className="w-40" />
          <Button variant="outline" size="icon" onClick={() => shift(1)} aria-label="Next day" disabled={!shownDate || shownDate >= today}>
            <ChevronRight />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDate(today)} disabled={shownDate === today}>
            Today
          </Button>
        </div>
        <SearchInput value={search} onChange={setSearch} placeholder="Search name, code or department..." className="md:ml-auto md:w-72" />
      </div>

      {data?.is_fallback_date && (
        <Notice tone="info" icon={<Info />}>
          No attendance for the requested day yet — showing <strong>{formatDate(data.date)}</strong>, the latest date with data.
        </Notice>
      )}

      <div className="scrollbar-none -mx-1 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Filter by status">
        {COUNT_KEYS.map((c) => {
          const active = status === c.key;
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => setStatus(c.key)}
              aria-pressed={active}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150",
                active ? "border-brand bg-brand text-brand-foreground" : "border-border bg-surface text-muted-foreground hover:border-border-strong hover:text-foreground",
              )}
            >
              {c.dot && <span className={cn("size-1.5 rounded-full", c.dot)} aria-hidden="true" />}
              {c.label}
              <span className="tabular-nums">{data ? (data.counts?.[c.key] ?? 0) : "–"}</span>
            </button>
          );
        })}
      </div>

      <Panel
        title={shownDate ? formatDate(shownDate) : "Attendance"}
        subtitle={shownDate ? `${weekdayName(shownDate)} · ${role === "manager" ? "your team" : "all active employees"}` : undefined}
        icon={<CalendarClock />}
        bodyClassName="p-0"
      >
        <AsyncContent loading={loading && !data} error={error} onRetry={reload} loadingLabel="Loading daily attendance...">
          <DataTable
            rows={rows}
            rowKey={(r) => r.employee_id}
            dense
            empty={
              <EmptyState
                icon={<Users />}
                title={filtered ? "No employees match" : "No employees"}
                description={filtered ? "Try another status or search." : "There is nobody in scope for this day."}
                action={
                  filtered ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setStatus("total");
                        setSearch("");
                      }}
                    >
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            }
            mobileCard={(r) => (
              <div className="flex items-center gap-3 px-4 py-3">
                <Avatar name={r.name} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{r.name}</p>
                  <p className="truncate text-xs text-muted-foreground tabular-nums">
                    {r.in_time ? `${formatTime(r.in_time)} – ${formatTime(r.out_time)}` : (r.department ?? r.employee_code)}
                    {r.working_minutes ? ` · ${formatMinutes(r.working_minutes)}` : ""}
                  </p>
                </div>
                <StatusBadge status={rowStatus(r)} />
              </div>
            )}
            columns={[
              {
                key: "emp",
                header: "Employee",
                sortValue: (r) => r.name,
                render: (r) => (
                  <div className="flex items-center gap-2.5">
                    <Avatar name={r.name} size="sm" />
                    <div>
                      <p className="font-medium">{r.name}</p>
                      <p className="text-xs text-muted-foreground">{r.employee_code}</p>
                    </div>
                  </div>
                ),
              },
              { key: "dept", header: "Department", sortValue: (r) => r.department, render: (r) => r.department ?? "—" },
              { key: "status", header: "Status", sortValue: (r) => rowStatus(r), render: (r) => <StatusBadge status={rowStatus(r)} /> },
              { key: "in", header: "In", sortValue: (r) => r.in_time, render: (r) => <span className="tabular-nums">{formatTime(r.in_time)}</span> },
              { key: "out", header: "Out", render: (r) => <span className="tabular-nums">{formatTime(r.out_time)}</span> },
              { key: "work", header: "Worked", sortValue: (r) => r.working_minutes, render: (r) => (r.working_minutes ? <span className="tabular-nums">{formatMinutes(r.working_minutes)}</span> : dash) },
              {
                key: "late",
                header: "Late",
                sortValue: (r) => r.late_minutes,
                render: (r) => (r.late_minutes && r.late_minutes > 0 ? <span className="font-medium text-status-late-fg tabular-nums">{formatMinutes(r.late_minutes)}</span> : dash),
              },
              {
                key: "ot",
                header: "Overtime",
                sortValue: (r) => r.overtime_minutes,
                render: (r) =>
                  r.overtime_minutes && r.overtime_minutes > 0 ? <span className="font-medium text-brand-subtle-foreground tabular-nums">{formatMinutes(r.overtime_minutes)}</span> : dash,
              },
            ]}
          />
        </AsyncContent>
      </Panel>
    </div>
  );
}
