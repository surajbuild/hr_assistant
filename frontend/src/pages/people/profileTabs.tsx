/**
 * Employee profile tabs: Overview · Attendance · Leave · Payroll.
 * Data is fetched once by EmployeeDetailPage and passed in (switching tabs never refetches).
 * Payroll data is only fetched/rendered for self or HR/Admin (D-021); the leave balance only exists for self
 * (GET /leaves/balance/me) — other people's balances have no endpoint, so they are not shown.
 */
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CalendarCheck, CalendarDays, ChevronRight, FileText, Palmtree, Plus, Users, Wallet } from "lucide-react";
import { AttendanceHeatmap } from "@/components/AttendanceHeatmap";
import { AttendanceTable, MonthKeySelect, monthsInRecords, summarize } from "@/components/AttendanceTable";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { LeaveBalanceGrid, leaveTypeColor } from "@/components/LeaveBalanceGrid";
import { Panel } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, CardSkeletons, EmptyState, LoadingState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatINR, formatMinutes, formatNumber, humanize, monthLabel, monthShortLabel } from "@/lib/format";
import { Link, navigate } from "@/lib/router";
import type { AttendanceRecord, Employee, Leave, LeaveBalance, SalaryRecord } from "@/lib/types";
import type { FetchState } from "@/lib/useFetch";
import { MiniStat } from "./profile";

export type ProfileTab = "overview" | "attendance" | "leave" | "payroll";

/** /leaves/me rows have no `days`; /leaves?employee_id= rows carry server-computed working days. */
export type LeaveRow = Leave & { days?: number; applied_at?: string | null };

export interface ProfileData {
  attendance: FetchState<AttendanceRecord[]>;
  leaves: FetchState<LeaveRow[]>;
  /** null when not viewing yourself (no endpoint for other people's balance). */
  balance: FetchState<LeaveBalance[]> | null;
  /** null when the viewer may not see this person's salary. */
  salary: FetchState<SalaryRecord[]> | null;
  /** In-scope employees reporting to this person (staff viewers only). */
  reports: Employee[];
}

const STATUS_COLOR = {
  present: "var(--status-present)",
  late: "var(--status-late)",
  half: "var(--status-half)",
  leave: "var(--status-leave)",
  absent: "var(--status-absent)",
  brand: "var(--brand)",
};

function monthKeyLabel(key: string): string {
  const [y, m] = key.split("-");
  return monthLabel(Number(m), Number(y));
}

function dateRange(from: string, to: string): string {
  return from === to ? formatDate(from) : `${formatDate(from)} – ${formatDate(to)}`;
}

function sortLeaves(rows: LeaveRow[]): LeaveRow[] {
  return [...rows].sort((a, b) => b.from_date.localeCompare(a.from_date));
}

function sortSlips(rows: SalaryRecord[]): SalaryRecord[] {
  return [...rows].sort((a, b) => b.year - a.year || b.month - a.month);
}

function LeaveTypeLabel({ type }: { type: string }) {
  return (
    <span className="inline-flex items-center gap-2 font-medium text-foreground">
      <span className="size-2 shrink-0 rounded-full" style={{ background: leaveTypeColor(type) }} aria-hidden="true" />
      {humanize(type)}
    </span>
  );
}

function daysLabel(n: number | undefined): string | null {
  return n ? `${n} working day${n === 1 ? "" : "s"}` : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Overview
// ─────────────────────────────────────────────────────────────────────────────

export function OverviewTab({
  data,
  viewingSelf,
  onTab,
  onOpenSlip,
}: {
  data: ProfileData;
  viewingSelf: boolean;
  onTab: (t: ProfileTab) => void;
  onOpenSlip: (s: SalaryRecord) => void;
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="flex min-w-0 flex-col gap-5 lg:col-span-2">
        <AttendanceSnapshot state={data.attendance} onMore={() => onTab("attendance")} />
        <RecentLeaves state={data.leaves} onMore={() => onTab("leave")} />
      </div>
      <div className="flex min-w-0 flex-col gap-5">
        {data.balance ? <BalanceSnapshot state={data.balance} onMore={() => onTab("leave")} /> : <LeaveSummary state={data.leaves} />}
        {data.salary && <PayslipSnapshot state={data.salary} viewingSelf={viewingSelf} onOpen={onOpenSlip} onMore={() => onTab("payroll")} />}
        {data.reports.length > 0 && <ReportsPanel reports={data.reports} />}
      </div>
    </div>
  );
}

function AttendanceSnapshot({ state, onMore }: { state: FetchState<AttendanceRecord[]>; onMore: () => void }) {
  const records = state.data ?? [];
  const latest = monthsInRecords(records)[0];
  const inMonth = latest ? records.filter((r) => r.attendance_date.startsWith(latest)) : [];
  const s = summarize(inMonth);
  const [y, m] = (latest ?? "").split("-").map(Number);
  return (
    <Panel
      title="Attendance"
      subtitle={latest ? `Latest month with records · ${monthKeyLabel(latest)}` : undefined}
      icon={<CalendarCheck />}
      actions={
        records.length > 0 && (
          <Button variant="ghost" size="sm" onClick={onMore}>
            All records <ArrowRight />
          </Button>
        )
      }
    >
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} skeleton={<Skeleton className="h-56 w-full" />}>
        {!latest ? (
          <EmptyState icon={<CalendarCheck />} title="No attendance recorded yet" description="Days appear here once check-ins are recorded." className="py-8" />
        ) : (
          <div className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,240px)]">
            <div className="grid grid-cols-2 content-start gap-2.5 min-[480px]:grid-cols-3">
              <MiniStat label="Present" value={s.present} color={STATUS_COLOR.present} />
              <MiniStat label="Late" value={s.late} color={STATUS_COLOR.late} />
              <MiniStat label="Half day" value={s.half} color={STATUS_COLOR.half} />
              <MiniStat label="Leave" value={s.leave} color={STATUS_COLOR.leave} />
              <MiniStat label="Absent" value={s.absent} color={STATUS_COLOR.absent} />
              <MiniStat label="Overtime" value={formatMinutes(s.ot)} color={STATUS_COLOR.brand} />
            </div>
            {y && m ? <AttendanceHeatmap records={inMonth} year={y} month={m} /> : null}
          </div>
        )}
      </AsyncContent>
    </Panel>
  );
}

function RecentLeaves({ state, onMore }: { state: FetchState<LeaveRow[]>; onMore: () => void }) {
  const rows = sortLeaves(state.data ?? []).slice(0, 4);
  return (
    <Panel
      title="Recent leave requests"
      icon={<Palmtree />}
      bodyClassName="p-0"
      actions={
        (state.data?.length ?? 0) > 0 && (
          <Button variant="ghost" size="sm" onClick={onMore}>
            View all <ArrowRight />
          </Button>
        )
      }
    >
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} skeleton={<LoadingState rows={3} label="Loading leave requests" />}>
        {rows.length === 0 ? (
          <EmptyState icon={<CalendarDays />} title="No leave requests" description="Leave applications will be listed here." className="py-8" />
        ) : (
          <ul className="divide-y divide-border">
            {rows.map((l) => (
              <li key={l.id} className="flex items-center gap-3 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <LeaveTypeLabel type={l.leave_type} />
                  <p className="truncate text-xs text-muted-foreground tabular-nums">
                    {dateRange(l.from_date, l.to_date)}
                    {daysLabel(l.days) ? ` · ${daysLabel(l.days)}` : ""}
                  </p>
                </div>
                <StatusBadge status={l.status} />
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

function BalanceSnapshot({ state, onMore }: { state: FetchState<LeaveBalance[]>; onMore: () => void }) {
  const list = state.data ?? [];
  const year = list[0]?.year ?? new Date().getFullYear();
  return (
    <Panel
      title="Leave balance"
      subtitle={String(year)}
      icon={<Palmtree />}
      actions={
        <Button variant="ghost" size="sm" onClick={onMore}>
          Details <ArrowRight />
        </Button>
      }
    >
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} skeleton={<LoadingState rows={3} label="Loading leave balance" />}>
        {list.length === 0 ? (
          <EmptyState title="No leave balance" description="No leave types are configured for this year." className="py-6" />
        ) : (
          <ul className="flex flex-col gap-3.5">
            {list.map((b) => {
              const pct = b.entitled > 0 ? Math.min(100, ((b.used + b.pending) / b.entitled) * 100) : 0;
              return (
                <li key={b.leave_type}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                    <LeaveTypeLabel type={b.leave_type} />
                    <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                      <strong className="text-sm font-semibold text-foreground">{formatNumber(b.remaining, 1)}</strong> of {formatNumber(b.entitled, 1)} left
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: leaveTypeColor(b.leave_type) }} />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

function LeaveSummary({ state }: { state: FetchState<LeaveRow[]> }) {
  const rows = state.data ?? [];
  const count = (s: string) => rows.filter((l) => l.status === s).length;
  const approvedDays = rows.filter((l) => l.status === "approved").reduce((sum, l) => sum + (l.days ?? 0), 0);
  return (
    <Panel title="Leave summary" subtitle="All requests on record" icon={<Palmtree />}>
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} skeleton={<LoadingState rows={2} label="Loading leave summary" />}>
        <div className="grid grid-cols-2 gap-2.5">
          <MiniStat label="Pending" value={count("pending")} color={STATUS_COLOR.late} />
          <MiniStat label="Approved" value={count("approved")} color={STATUS_COLOR.present} hint={approvedDays ? `${approvedDays} working day${approvedDays === 1 ? "" : "s"}` : undefined} />
          <MiniStat label="Rejected" value={count("rejected")} color={STATUS_COLOR.absent} />
          <MiniStat label="Cancelled" value={count("cancelled")} color="var(--status-neutral)" />
        </div>
      </AsyncContent>
    </Panel>
  );
}

function PayslipSnapshot({
  state,
  viewingSelf,
  onOpen,
  onMore,
}: {
  state: FetchState<SalaryRecord[]>;
  viewingSelf: boolean;
  onOpen: (s: SalaryRecord) => void;
  onMore: () => void;
}) {
  const latest = sortSlips(state.data ?? [])[0];
  return (
    <Panel
      title="Latest payslip"
      subtitle={latest ? monthLabel(latest.month, latest.year) : undefined}
      icon={<Wallet />}
      actions={
        latest && (
          <Button variant="ghost" size="sm" onClick={onMore}>
            All payslips <ArrowRight />
          </Button>
        )
      }
    >
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} skeleton={<LoadingState rows={2} label="Loading payslips" />}>
        {!latest ? (
          <EmptyState
            icon={<Wallet />}
            title="No payslips yet"
            description={viewingSelf ? "Your payslips appear here once payroll is processed." : "Payslips appear once payroll is generated for this employee."}
            className="py-6"
          />
        ) : (
          <div>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-muted-foreground">Net pay</p>
                <p className="mt-0.5 text-[28px] leading-9 font-semibold tracking-tight text-foreground tabular-nums">{formatINR(latest.net_salary)}</p>
              </div>
              <StatusBadge status={latest.paid_at ? "paid" : "unpaid"} />
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-muted-foreground">Gross</dt>
              <dd className="text-right tabular-nums">{formatINR(latest.gross_salary)}</dd>
              <dt className="text-muted-foreground">Overtime</dt>
              <dd className="text-right tabular-nums">{formatINR(latest.overtime_amount)}</dd>
              <dt className="text-muted-foreground">PF + deductions</dt>
              <dd className="text-right tabular-nums">−{formatINR(Number(latest.pf) + Number(latest.deductions))}</dd>
            </dl>
            <Button variant="outline" size="sm" className="mt-4 w-full" onClick={() => onOpen(latest)}>
              <FileText /> View payslip
            </Button>
          </div>
        )}
      </AsyncContent>
    </Panel>
  );
}

function ReportsPanel({ reports }: { reports: Employee[] }) {
  return (
    <Panel title="Direct reports" subtitle={`${reports.length} ${reports.length === 1 ? "person" : "people"}`} icon={<Users />} bodyClassName="px-3 pb-3 pt-1">
      <ul className="flex flex-col">
        {reports.map((r) => (
          <li key={r.id}>
            <Link to={`/employees/${r.id}`} className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent">
              <Avatar name={r.name} size="sm" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">{r.name}</span>
                <span className="block truncate text-xs text-muted-foreground">{r.designation ?? r.employee_code}</span>
              </span>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Attendance
// ─────────────────────────────────────────────────────────────────────────────

export function AttendanceTab({ state }: { state: FetchState<AttendanceRecord[]> }) {
  const records = state.data ?? [];
  const months = useMemo(() => monthsInRecords(records), [records]);
  const [month, setMonth] = useState<string | null>(null);
  useEffect(() => {
    if (month === null && months.length > 0) setMonth(months[0]!);
  }, [months, month]);
  const filtered = month ? records.filter((r) => r.attendance_date.startsWith(month)) : records;
  const s = summarize(filtered);
  const [y, m] = (month ?? "").split("-").map(Number);

  if (state.loading) {
    return (
      <div className="flex flex-col gap-5">
        <Skeleton className="h-52 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  return (
    <AsyncContent loading={false} error={state.error} onRetry={state.reload}>
      {records.length === 0 ? (
        <Panel>
          <EmptyState icon={<CalendarCheck />} title="No attendance recorded yet" description="Daily records appear here once check-ins are recorded." />
        </Panel>
      ) : (
        <div className="flex flex-col gap-5">
          <Panel
            title="Summary"
            subtitle={month ? monthKeyLabel(month) : `All months · ${filtered.length} records`}
            icon={<CalendarCheck />}
            actions={<MonthKeySelect months={months} value={month ?? ""} onChange={(v) => setMonth(v)} />}
          >
            <div className={month ? "grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,280px)]" : undefined}>
              <div className="grid grid-cols-2 content-start gap-2.5 min-[480px]:grid-cols-3 xl:grid-cols-4">
                <MiniStat label="Present" value={s.present} color={STATUS_COLOR.present} />
                <MiniStat label="Late" value={s.late} color={STATUS_COLOR.late} />
                <MiniStat label="Half day" value={s.half} color={STATUS_COLOR.half} />
                <MiniStat label="Leave" value={s.leave} color={STATUS_COLOR.leave} />
                <MiniStat label="Absent" value={s.absent} color={STATUS_COLOR.absent} />
                <MiniStat label="Worked" value={formatMinutes(s.work)} />
                <MiniStat label="Overtime" value={formatMinutes(s.ot)} color={STATUS_COLOR.brand} />
                <MiniStat label="Days recorded" value={filtered.length} />
              </div>
              {month && y && m ? <AttendanceHeatmap records={filtered} year={y} month={m} /> : null}
            </div>
          </Panel>
          <Panel title="Daily records" subtitle={`${filtered.length} day${filtered.length === 1 ? "" : "s"}`} bodyClassName="p-0">
            <AttendanceTable records={filtered} />
          </Panel>
        </div>
      )}
    </AsyncContent>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Leave
// ─────────────────────────────────────────────────────────────────────────────

const LEAVE_FILTERS = ["all", "pending", "approved", "rejected", "cancelled"] as const;
type LeaveFilter = (typeof LEAVE_FILTERS)[number];

export function LeaveTab({ data, viewingSelf }: { data: ProfileData; viewingSelf: boolean }) {
  const [filter, setFilter] = useState<LeaveFilter>("all");
  const all = sortLeaves(data.leaves.data ?? []);
  const rows = filter === "all" ? all : all.filter((l) => l.status === filter);
  const hasDays = all.some((l) => l.days !== undefined);
  const balance = data.balance;

  return (
    <div className="flex flex-col gap-5">
      {balance && (
        <Panel
          title="Leave balance"
          subtitle={String(balance.data?.[0]?.year ?? new Date().getFullYear())}
          icon={<Palmtree />}
          actions={
            <Button size="sm" onClick={() => navigate("/leave")}>
              <Plus /> Apply for leave
            </Button>
          }
        >
          <AsyncContent
            loading={balance.loading}
            error={balance.error}
            onRetry={balance.reload}
            skeleton={<CardSkeletons count={3} className="grid-cols-1 sm:grid-cols-3" itemClassName="h-20" />}
          >
            {(balance.data ?? []).length === 0 ? (
              <EmptyState title="No leave balance" description="No leave types are configured for this year." className="py-6" />
            ) : (
              <LeaveBalanceGrid balances={balance.data ?? []} />
            )}
          </AsyncContent>
        </Panel>
      )}

      <Panel title="Leave requests" subtitle={data.leaves.loading ? undefined : `${all.length} on record`} icon={<CalendarDays />} bodyClassName="p-0">
        <AsyncContent loading={data.leaves.loading} error={data.leaves.error} onRetry={data.leaves.reload} skeleton={<LoadingState rows={4} label="Loading leave requests" />}>
          {all.length > 0 && (
            <div className="border-b border-border px-5 pb-3">
              <Segmented<LeaveFilter>
                label="Filter by status"
                value={filter}
                onChange={setFilter}
                options={LEAVE_FILTERS.map((f) => {
                  const n = f === "all" ? all.length : all.filter((l) => l.status === f).length;
                  return {
                    value: f,
                    label: (
                      <>
                        {f === "all" ? "All" : humanize(f)}
                        <span className="text-muted-foreground tabular-nums">{n}</span>
                      </>
                    ),
                  };
                })}
              />
            </div>
          )}
          <DataTable
            rows={rows}
            rowKey={(l) => l.id}
            pageSize={10}
            empty={
              all.length === 0 ? (
                <EmptyState
                  icon={<CalendarDays />}
                  title="No leave requests"
                  description={viewingSelf ? "You haven't applied for leave yet." : "This employee has no leave requests on record."}
                  action={
                    viewingSelf ? (
                      <Button size="sm" onClick={() => navigate("/leave")}>
                        <Plus /> Apply for leave
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <EmptyState
                  icon={<CalendarDays />}
                  title={`No ${filter} requests`}
                  action={
                    <Button variant="outline" size="sm" onClick={() => setFilter("all")}>
                      Show all
                    </Button>
                  }
                />
              )
            }
            mobileCard={(l) => (
              <div className="flex items-start gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <LeaveTypeLabel type={l.leave_type} />
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {dateRange(l.from_date, l.to_date)}
                    {daysLabel(l.days) ? ` · ${daysLabel(l.days)}` : ""}
                  </p>
                  {l.reason && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{l.reason}</p>}
                </div>
                <StatusBadge status={l.status} />
              </div>
            )}
            columns={[
              { key: "type", header: "Type", sortValue: (l) => l.leave_type, render: (l) => <LeaveTypeLabel type={l.leave_type} /> },
              { key: "dates", header: "Dates", sortValue: (l) => l.from_date, render: (l) => <span className="tabular-nums">{dateRange(l.from_date, l.to_date)}</span> },
              ...(hasDays
                ? [{ key: "days", header: "Working days", align: "right" as const, sortValue: (l: LeaveRow) => l.days ?? 0, render: (l: LeaveRow) => <span className="tabular-nums">{l.days ?? "—"}</span> }]
                : []),
              { key: "reason", header: "Reason", render: (l) => <span className="block max-w-[320px] truncate text-muted-foreground" title={l.reason ?? undefined}>{l.reason || "—"}</span> },
              { key: "status", header: "Status", sortValue: (l) => l.status, render: (l) => <StatusBadge status={l.status} /> },
            ]}
          />
        </AsyncContent>
      </Panel>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Payroll (self or HR/Admin only — the caller never renders this tab otherwise)
// ─────────────────────────────────────────────────────────────────────────────

export function PayrollTab({
  state,
  emp,
  viewingSelf,
  onOpenSlip,
}: {
  state: FetchState<SalaryRecord[]>;
  emp: Employee;
  viewingSelf: boolean;
  onOpenSlip: (s: SalaryRecord) => void;
}) {
  const rows = sortSlips(state.data ?? []);
  const latest = rows[0];
  const chronological = [...rows].reverse().map((r) => Number(r.net_salary));
  const paid = rows.filter((r) => r.paid_at).length;

  if (state.loading) return <CardSkeletons count={3} className="grid-cols-1 sm:grid-cols-3" />;

  return (
    <AsyncContent loading={false} error={state.error} onRetry={state.reload}>
      {rows.length === 0 ? (
        <Panel>
          <EmptyState
            icon={<Wallet />}
            title="No payslips yet"
            description={viewingSelf ? "Your payslips appear here once payroll is processed." : "Generate payroll for a month to create this employee's payslip."}
            action={
              !viewingSelf ? (
                <Button size="sm" variant="outline" onClick={() => navigate("/payroll")}>
                  Open payroll <ArrowRight />
                </Button>
              ) : undefined
            }
          />
        </Panel>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard
              label={`Net pay · ${latest ? monthShortLabel(latest.month, latest.year) : ""}`}
              numeric={Number(latest?.net_salary ?? 0)}
              format={(n) => formatINR(n)}
              spark={chronological}
              icon={<Wallet />}
              tone="brand"
            />
            {emp.monthly_gross_salary != null ? (
              <StatCard label="Monthly gross (structure)" numeric={Number(emp.monthly_gross_salary)} format={(n) => formatINR(n)} hint="Used by Generate payroll" tone="neutral" />
            ) : (
              <StatCard label="Gross · latest" numeric={Number(latest?.gross_salary ?? 0)} format={(n) => formatINR(n)} tone="neutral" />
            )}
            <StatCard label="Payslips" numeric={rows.length} hint={`${paid} paid · ${rows.length - paid} unpaid`} icon={<FileText />} tone="present" />
          </div>

          <Panel title="Payslips" subtitle="Select a month to open the payslip" icon={<FileText />} bodyClassName="p-0">
            <DataTable
              rows={rows}
              rowKey={(r) => r.id}
              onRowClick={onOpenSlip}
              pageSize={12}
              mobileCard={(r) => (
                <button type="button" onClick={() => onOpenSlip(r)} className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-accent focus-visible:bg-accent">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-foreground">{monthLabel(r.month, r.year)}</span>
                    <span className="block text-xs text-muted-foreground tabular-nums">Net {formatINR(r.net_salary)}</span>
                  </span>
                  <StatusBadge status={r.paid_at ? "paid" : "unpaid"} />
                  <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                </button>
              )}
              columns={[
                { key: "month", header: "Month", sortValue: (r) => r.year * 100 + r.month, render: (r) => <span className="font-medium">{monthLabel(r.month, r.year)}</span> },
                { key: "gross", header: "Gross", align: "right", render: (r) => <span className="tabular-nums">{formatINR(r.gross_salary)}</span> },
                { key: "ot", header: "Overtime", align: "right", render: (r) => <span className="tabular-nums">{formatINR(r.overtime_amount)}</span> },
                { key: "pf", header: "PF", align: "right", render: (r) => <span className="tabular-nums">−{formatINR(r.pf)}</span> },
                { key: "ded", header: "Deductions", align: "right", render: (r) => <span className="tabular-nums">−{formatINR(r.deductions)}</span> },
                { key: "net", header: "Net pay", align: "right", sortValue: (r) => Number(r.net_salary), render: (r) => <span className="font-semibold tabular-nums">{formatINR(r.net_salary)}</span> },
                {
                  key: "status",
                  header: "Status",
                  render: (r) =>
                    r.paid_at ? (
                      <span title={`Paid on ${formatDate(r.paid_at)}`}>
                        <StatusBadge status="paid" />
                      </span>
                    ) : (
                      <StatusBadge status="unpaid" />
                    ),
                },
                {
                  key: "view",
                  header: <span className="sr-only">Payslip</span>,
                  align: "right",
                  render: (r) => (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`View payslip for ${monthLabel(r.month, r.year)}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenSlip(r);
                      }}
                    >
                      <FileText /> View
                    </Button>
                  ),
                },
              ]}
            />
          </Panel>
          {!viewingSelf && (
            <p className="text-xs text-muted-foreground">
              <Badge tone="neutral" className="mr-1.5">
                Confidential
              </Badge>
              Salary data is visible only to HR, Admin and the employee.
            </p>
          )}
        </div>
      )}
    </AsyncContent>
  );
}
