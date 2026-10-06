/**
 * Dashboard widgets. Each takes REAL data (from existing endpoints) and renders its own empty state.
 * Role dashboards compose these differently (see HRDashboard / PersonalDashboard).
 */
import type { ReactNode } from "react";
import { ArrowRight, Bot, CalendarCheck, CalendarDays, CalendarX, Clock, Palmtree, ShieldCheck, TimerReset, UserPlus, Users, Wallet, Award, Building2, ScrollText } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Avatar } from "@/components/Avatar";
import { ATTENDANCE_SERIES, AXIS_TICK, BarList, Donut, GRID_STROKE, Legend, RingProgress, TOOLTIP_STYLE } from "@/components/charts";
import { DataTable } from "@/components/DataTable";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, LoadingState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDateTime, formatINR, formatMinutes, formatNumber, humanize, monthLabel } from "@/lib/format";
import { Link, navigate } from "@/lib/router";
import type { AppUser, ChatLog, DashboardMe, DashboardSummary, LeaveListItem } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import type { DayCounts, PayrollSnapshotData } from "./data";

const ChartSkeleton = () => <Skeleton className="h-[240px] w-full" />;

// ── Attendance trend (daily, current reference month) ────────────────────────
export function AttendanceTrendPanel({
  days,
  loading,
  error,
  onRetry,
  monthly,
  monthName,
}: {
  days: DayCounts[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  monthly: NonNullable<DashboardSummary["monthly_attendance"]>;
  monthName: string;
}) {
  const last = monthly[monthly.length - 1];
  const prev = monthly[monthly.length - 2];
  const delta = last && prev ? last.attendance_rate - prev.attendance_rate : null;
  return (
    <Panel
      title="Attendance trend"
      subtitle={`Daily attendance · ${monthName}`}
      icon={<CalendarCheck />}
      actions={<Legend items={ATTENDANCE_SERIES.map((s) => ({ label: s.label, color: s.color }))} />}
    >
      {last && (
        <p className="mb-3 flex flex-wrap items-baseline gap-x-2 text-sm text-muted-foreground">
          <span className="text-2xl font-semibold tracking-tight text-foreground tabular-nums">{formatNumber(last.attendance_rate, 1)}%</span>
          attendance rate in {last.label}
          {delta !== null && prev && (
            <Badge tone={Math.abs(delta) < 0.05 ? "neutral" : delta > 0 ? "present" : "absent"} className="tabular-nums">
              {Math.abs(delta) < 0.05 ? "no change" : `${delta > 0 ? "+" : "−"}${formatNumber(Math.abs(delta), 1)} pts`} vs {prev.label}
            </Badge>
          )}
        </p>
      )}
      <AsyncContent loading={loading} error={error} onRetry={onRetry} skeleton={<ChartSkeleton />}>
        {days.length === 0 ? (
          <EmptyState icon={<CalendarX />} title="No attendance recorded" description="Daily attendance for this month will appear here." className="py-8" />
        ) : (
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={days} margin={{ top: 8, right: 4, left: -20, bottom: 0 }} barCategoryGap="22%">
                <CartesianGrid vertical={false} stroke={GRID_STROKE} />
                <XAxis dataKey="day" tick={AXIS_TICK} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  {...TOOLTIP_STYLE}
                  labelFormatter={(_l, payload) => {
                    const d = (payload?.[0]?.payload as DayCounts | undefined)?.date;
                    return d ? formatDate(d) : "";
                  }}
                />
                {ATTENDANCE_SERIES.map((s, i) => (
                  <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} maxBarSize={20} radius={i === ATTENDANCE_SERIES.length - 1 ? [3, 3, 0, 0] : 0} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </AsyncContent>
      {monthly.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {monthly.map((m) => (
            <span key={m.month} className="rounded-md bg-surface-muted px-2 py-1 text-xs text-muted-foreground">
              {m.label}: <strong className="font-semibold text-foreground tabular-nums">{formatNumber(m.attendance_rate, 1)}%</strong>
            </span>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ── Today (donut from the real KPI counts) ───────────────────────────────────
export function TodayPanel({ data }: { data: DashboardSummary }) {
  const { kpis } = data;
  const late = Math.min(kpis.late_today, kpis.present_today);
  const onTime = Math.max(0, kpis.present_today - late);
  const marked = onTime + late + kpis.absent_today + kpis.on_leave_today;
  const notMarked = Math.max(0, kpis.total_employees - marked);
  const segments = [
    { label: "On time", value: onTime, color: "var(--status-present)" },
    { label: "Late", value: late, color: "var(--status-late)" },
    { label: "On leave", value: kpis.on_leave_today, color: "var(--status-leave)" },
    { label: "Absent", value: kpis.absent_today, color: "var(--status-absent)" },
    { label: "Not marked", value: notMarked, color: "var(--status-neutral)" },
  ];
  return (
    <Panel title="Today" subtitle={formatDate(data.reference_date)} icon={<Clock />}>
      <div className="flex flex-col items-center gap-5 sm:flex-row lg:flex-col xl:flex-row">
        <Donut segments={segments} size={140} stroke={16}>
          <span className="text-3xl leading-none font-semibold tracking-tight text-foreground tabular-nums">{formatNumber(kpis.present_today)}</span>
          <span className="mt-1 text-[11px] text-muted-foreground">of {formatNumber(kpis.total_employees)} present</span>
        </Donut>
        <ul className="grid w-full flex-1 grid-cols-1 gap-2 text-sm">
          {segments.map((s) => (
            <li key={s.label} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className="size-2.5 rounded-full" style={{ background: s.color }} aria-hidden="true" />
                {s.label}
              </span>
              <span className="font-semibold text-foreground tabular-nums">{formatNumber(s.value)}</span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

// ── Pending approvals (queue preview; deciding happens on the Leave page) ────
export function PendingApprovalsPanel({
  items,
  loading,
  error,
  onRetry,
  className,
  title = "Pending approvals",
}: {
  items: LeaveListItem[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  className?: string;
  title?: string;
}) {
  return (
    <Panel
      className={className}
      title={title}
      subtitle={loading ? undefined : `${items.length} waiting for your decision`}
      icon={<CalendarDays />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/leave")}>
          Review <ArrowRight />
        </Button>
      }
      bodyClassName="p-0"
    >
      <AsyncContent loading={loading} error={error} onRetry={onRetry} skeleton={<LoadingState rows={3} label="Loading approvals" />}>
        {items.length === 0 ? (
          <EmptyState icon={<CalendarCheck />} title="All caught up" description="No leave requests are waiting for you." className="py-8" />
        ) : (
          <ul className="divide-y divide-border">
            {items.slice(0, 5).map((l) => (
              <li key={l.id}>
                <Link to="/leave" className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-accent/60">
                  <Avatar name={l.employee_name} size="md" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{l.employee_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {humanize(l.leave_type)} · {formatDate(l.from_date)}
                      {l.to_date !== l.from_date ? ` – ${formatDate(l.to_date)}` : ""}
                      {l.days ? ` · ${l.days} day${l.days === 1 ? "" : "s"}` : ""}
                    </p>
                  </div>
                  <StatusBadge status="pending" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ── Department attendance / leave usage / leaders ────────────────────────────
export function DepartmentPanel({ data, className }: { data: DashboardSummary; className?: string }) {
  return (
    <Panel className={className} title="Departments" subtitle={`Present vs headcount · ${formatDate(data.reference_date)}`} icon={<Building2 />}>
      {data.department_attendance.length === 0 ? (
        <EmptyState title="No department data" />
      ) : (
        <BarList
          max={100}
          items={data.department_attendance.map((d) => ({
            key: d.department,
            label: d.department,
            sublabel: `${d.present}/${d.total_employees} present`,
            value: d.percentage,
            title: `${d.department}: ${d.present} present, ${d.absent} absent of ${d.total_employees}`,
          }))}
          formatValue={(v) => `${formatNumber(v, 1)}%`}
        />
      )}
    </Panel>
  );
}

export function LeaveUsagePanel({ data, className }: { data: DashboardSummary; className?: string }) {
  const total = data.leave_breakdown.reduce((s, l) => s + l.count, 0);
  return (
    <Panel className={className} title="Leave usage" subtitle={`${total} request${total === 1 ? "" : "s"} by type`} icon={<Palmtree />}>
      {data.leave_breakdown.length === 0 ? (
        <EmptyState title="No leave requests" description="No leave applications recorded for this period." />
      ) : (
        <BarList color="var(--status-leave)" items={data.leave_breakdown.map((l) => ({ key: l.type, label: humanize(l.type), value: l.count }))} formatValue={(v) => `${v}`} />
      )}
    </Panel>
  );
}

export function OvertimePanel({ data, className }: { data: DashboardSummary; className?: string }) {
  return (
    <Panel
      className={className}
      title="Overtime"
      subtitle={`${formatNumber(data.kpis.total_overtime_hours, 1)} h total · ${data.month}`}
      icon={<Award />}
    >
      {data.overtime_leaders.length === 0 ? (
        <EmptyState title="No overtime recorded" />
      ) : (
        <BarList
          color="var(--brand)"
          items={data.overtime_leaders.map((o) => ({ key: o.name, label: o.name, sublabel: o.department, value: o.overtime_hours }))}
          formatValue={(v) => `${formatNumber(v, 1)} h`}
        />
      )}
    </Panel>
  );
}

export function LatePanel({ data, className }: { data: DashboardSummary; className?: string }) {
  return (
    <Panel className={className} title="Late coming" subtitle={data.month} icon={<TimerReset />}>
      {data.late_leaders.length === 0 ? (
        <EmptyState title="No late arrivals" />
      ) : (
        <BarList
          color="var(--status-late)"
          items={data.late_leaders.map((l) => ({ key: l.name, label: l.name, sublabel: `${l.department} · ${formatMinutes(l.total_late_minutes)} total`, value: l.late_count }))}
          formatValue={(v) => `${v}×`}
        />
      )}
    </Panel>
  );
}

export function RecentLeavesPanel({ data }: { data: DashboardSummary }) {
  return (
    <Panel
      title="Recent activity"
      subtitle="Latest leave requests"
      icon={<CalendarX />}
      bodyClassName="p-0"
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/leave")}>
          View all <ArrowRight />
        </Button>
      }
    >
      <DataTable
        rows={data.recent_leaves}
        rowKey={(r) => r.id}
        empty={<EmptyState title="No recent leave requests" />}
        columns={[
          {
            key: "emp",
            header: "Employee",
            render: (r) => (
              <div className="flex items-center gap-2.5">
                <Avatar name={r.employee_name} size="sm" />
                <div>
                  <p className="font-medium">{r.employee_name}</p>
                  <p className="text-xs text-muted-foreground">{r.department}</p>
                </div>
              </div>
            ),
          },
          { key: "type", header: "Type", render: (r) => humanize(r.leave_type) },
          { key: "dates", header: "Dates", render: (r) => `${formatDate(r.from_date)} – ${formatDate(r.to_date)}` },
          { key: "reason", header: "Reason", render: (r) => <span className="block max-w-[260px] truncate text-muted-foreground">{r.reason || "—"}</span> },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
        ]}
      />
    </Panel>
  );
}

export function QuickActions({ canAdd, className }: { canAdd: boolean; className?: string }) {
  const actions = [
    ...(canAdd ? [{ label: "Add employee", to: "/employees/add", icon: UserPlus }] : []),
    { label: "Attendance", to: "/attendance", icon: CalendarCheck },
    { label: "Leave requests", to: "/leave", icon: CalendarDays },
    { label: "Ask the assistant", to: "/assistant", icon: Bot },
  ];
  return (
    <Panel className={className} title="Quick actions">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-1 xl:grid-cols-2">
        {actions.map(({ label, to, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-2.5 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-border-strong hover:bg-accent"
          >
            <span className="flex size-7 items-center justify-center rounded-md bg-brand-subtle text-brand-subtle-foreground">
              <Icon className="size-4" />
            </span>
            {label}
          </Link>
        ))}
      </div>
    </Panel>
  );
}

// ── HR: payroll snapshot (GET /salary latest month) ──────────────────────────
export function PayrollSnapshotPanel({ snapshot, loading, error, onRetry, className }: { snapshot: PayrollSnapshotData | null; loading: boolean; error: string | null; onRetry: () => void; className?: string }) {
  return (
    <Panel
      className={className}
      title="Payroll"
      subtitle={snapshot ? monthLabel(snapshot.month, snapshot.year) : undefined}
      icon={<Wallet />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/payroll")}>
          Open <ArrowRight />
        </Button>
      }
    >
      <AsyncContent loading={loading} error={error} onRetry={onRetry} skeleton={<LoadingState rows={2} label="Loading payroll" />}>
        {!snapshot ? (
          <EmptyState icon={<Wallet />} title="No payroll yet" description="Generate payroll from the Payroll page." className="py-8" />
        ) : (
          <div>
            <p className="text-xs font-medium text-muted-foreground">Net payout</p>
            <p className="mt-0.5 text-3xl font-semibold tracking-tight text-foreground tabular-nums">{formatINR(snapshot.net)}</p>
            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-muted-foreground">Gross</dt>
              <dd className="text-right font-medium tabular-nums">{formatINR(snapshot.gross)}</dd>
              <dt className="text-muted-foreground">Overtime</dt>
              <dd className="text-right font-medium tabular-nums">{formatINR(snapshot.overtime)}</dd>
              <dt className="text-muted-foreground">Payslips</dt>
              <dd className="text-right font-medium tabular-nums">{snapshot.employees}</dd>
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge tone="present">{snapshot.paid} paid</Badge>
              <Badge tone="late">{snapshot.unpaid} unpaid</Badge>
            </div>
          </div>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ── Admin: access overview (GET /users) and AI activity (GET /chat/logs) ─────
export function AccessPanel({ className }: { className?: string }) {
  const { data, loading, error, reload } = useFetch<AppUser[]>("/users");
  const users = data ?? [];
  const roles: { key: string; label: string; color: string }[] = [
    { key: "admin", label: "Admins", color: "var(--brand)" },
    { key: "hr", label: "HR", color: "var(--status-leave)" },
    { key: "manager", label: "Managers", color: "var(--status-half)" },
    { key: "employee", label: "Employees", color: "var(--status-present)" },
  ];
  const inactive = users.filter((u) => u.status !== "active").length;
  return (
    <Panel
      className={className}
      title="Access"
      subtitle={loading ? undefined : `${users.length} user account${users.length === 1 ? "" : "s"}`}
      icon={<ShieldCheck />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/settings")}>
          Manage <ArrowRight />
        </Button>
      }
    >
      <AsyncContent loading={loading} error={error} onRetry={reload} skeleton={<LoadingState rows={2} label="Loading users" />}>
        {users.length === 0 ? (
          <EmptyState icon={<Users />} title="No users" className="py-8" />
        ) : (
          <>
            <BarList
              max={Math.max(1, users.length)}
              items={roles.map((r) => ({ key: r.key, label: r.label, value: users.filter((u) => u.role === r.key).length, color: r.color }))}
            />
            <p className="mt-4 flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2 text-sm">
              <span className="text-muted-foreground">Inactive accounts</span>
              <span className="font-semibold text-foreground tabular-nums">{inactive}</span>
            </p>
          </>
        )}
      </AsyncContent>
    </Panel>
  );
}

export function AiActivityPanel({ className }: { className?: string }) {
  const { data, loading, error, reload } = useFetch<ChatLog[]>("/chat/logs?limit=100");
  const logs = data ?? [];
  const failures = logs.filter((l) => !!l.error).length;
  return (
    <Panel
      className={className}
      title="AI assistant activity"
      subtitle={loading ? undefined : `Last ${logs.length} interaction${logs.length === 1 ? "" : "s"}${failures ? ` · ${failures} with errors or blocked` : ""}`}
      icon={<ScrollText />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/settings")}>
          Audit log <ArrowRight />
        </Button>
      }
      bodyClassName="p-0"
    >
      <AsyncContent loading={loading} error={error} onRetry={reload} skeleton={<LoadingState rows={3} label="Loading AI activity" />}>
        {logs.length === 0 ? (
          <EmptyState icon={<Bot />} title="No questions yet" description="Questions asked in the assistant are logged here." className="py-8" />
        ) : (
          <ul className="divide-y divide-border">
            {logs.slice(0, 5).map((l) => (
              <li key={l.id} className="flex items-start gap-3 px-5 py-3">
                <Avatar name={l.user_email ?? "?"} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{l.question}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {l.user_email ?? "unknown"} · {formatDateTime(l.timestamp)}
                  </p>
                </div>
                {l.error ? <Badge tone="absent">Blocked</Badge> : l.detected_intent ? <Badge tone="brand">{humanize(l.detected_intent)}</Badge> : null}
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ── Personal (employee / manager) ────────────────────────────────────────────
export function MyMonthPanel({ data, className }: { data: DashboardMe; className?: string }) {
  const a = data.attendance;
  const rows: [string, ReactNode, string][] = [
    ["Present days", a.present_days, "var(--status-present)"],
    ["Late days", a.late_days, "var(--status-late)"],
    ["Half days", a.half_day_days, "var(--status-half)"],
    ["Leave days", a.leave_days, "var(--status-leave)"],
    ["Absent days", a.absent_days, "var(--status-absent)"],
  ];
  return (
    <Panel className={className} title="My month" subtitle={data.month_label} icon={<CalendarCheck />}>
      <div className="flex items-center gap-5">
        <RingProgress value={a.attendance_percentage} size={104} stroke={10} color="var(--status-present)" label={`Attendance ${formatNumber(a.attendance_percentage, 1)} percent`}>
          <span className="flex flex-col">
            <span className="text-xl leading-none font-semibold tracking-tight text-foreground tabular-nums">{formatNumber(a.attendance_percentage, 1)}%</span>
            <span className="mt-0.5 text-[10px] text-muted-foreground">attendance</span>
          </span>
        </RingProgress>
        <ul className="grid flex-1 gap-1.5 text-sm">
          {rows.map(([label, value, color]) => (
            <li key={label} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className="size-2 rounded-full" style={{ background: color }} aria-hidden="true" />
                {label}
              </span>
              <span className="font-semibold text-foreground tabular-nums">{value}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-4 flex items-center justify-between rounded-lg bg-surface-muted px-3 py-2 text-sm">
        <span className="text-muted-foreground">Overtime this month</span>
        <span className="font-semibold text-foreground tabular-nums">{formatMinutes(a.total_overtime_minutes)}</span>
      </p>
    </Panel>
  );
}

export function LatestPayslipPanel({ data, className }: { data: DashboardMe; className?: string }) {
  const s = data.latest_salary;
  return (
    <Panel
      className={className}
      title="Latest payslip"
      subtitle={s ? monthLabel(s.month, s.year) : undefined}
      icon={<Wallet />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/payroll")}>
          All payslips <ArrowRight />
        </Button>
      }
    >
      {s ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Net pay</p>
          <p className="mt-0.5 text-3xl font-semibold tracking-tight text-foreground tabular-nums">{formatINR(s.net_salary)}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Gross</dt>
            <dd className="text-right tabular-nums">{formatINR(s.gross_salary)}</dd>
            <dt className="text-muted-foreground">Overtime</dt>
            <dd className="text-right tabular-nums">{formatINR(s.overtime_amount)}</dd>
            <dt className="text-muted-foreground">PF</dt>
            <dd className="text-right tabular-nums">−{formatINR(s.pf)}</dd>
            <dt className="text-muted-foreground">Deductions</dt>
            <dd className="text-right tabular-nums">−{formatINR(s.deductions)}</dd>
          </dl>
        </div>
      ) : (
        <EmptyState icon={<Wallet />} title="No payslips yet" description="Your payslips appear here once payroll is processed." className="py-8" />
      )}
    </Panel>
  );
}

export function AskAiPanel({ className, suggestions }: { className?: string; suggestions: string[] }) {
  return (
    <section className={`hr-card flex flex-col justify-between gap-4 bg-brand-subtle p-5 ${className ?? ""}`} style={{ borderColor: "transparent" }}>
      <div>
        <span className="flex size-9 items-center justify-center rounded-lg bg-brand text-brand-foreground">
          <Bot className="size-[18px]" />
        </span>
        <h2 className="mt-3 text-base font-semibold text-foreground">Ask the AI assistant</h2>
        <p className="mt-1 text-sm text-muted-foreground">Instant answers about your attendance, leave, salary and company policies — computed from your data.</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <li key={s} className="rounded-full bg-surface px-2.5 py-1 text-xs text-foreground">
              “{s}”
            </li>
          ))}
        </ul>
      </div>
      <Button onClick={() => navigate("/assistant")} className="w-fit">
        Open assistant <ArrowRight />
      </Button>
    </section>
  );
}

export function TeamPanel({ team, className }: { team: NonNullable<DashboardMe["team"]>; className?: string }) {
  return (
    <Panel
      className={className}
      title="My team"
      subtitle={`${team.size} direct report${team.size === 1 ? "" : "s"}`}
      icon={<Users />}
      actions={
        <Button variant="ghost" size="sm" onClick={() => navigate("/leave")}>
          Approvals ({team.pending_leaves}) <ArrowRight />
        </Button>
      }
    >
      <div className="mb-4 grid grid-cols-3 gap-3">
        {[
          ["Present today", team.present_today, "var(--status-present)"],
          ["On leave", team.on_leave_today, "var(--status-leave)"],
          ["Pending leaves", team.pending_leaves, "var(--status-late)"],
        ].map(([label, value, color]) => (
          <div key={String(label)} className="rounded-lg bg-surface-muted p-3">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="size-2 rounded-full" style={{ background: String(color) }} aria-hidden="true" />
              {label}
            </p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-foreground tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      {team.members.length === 0 ? (
        <EmptyState title="No team members" className="py-8" />
      ) : (
        <ul className="-mx-2 divide-y divide-border">
          {team.members.map((m) => (
            <li key={m.id}>
              <Link to={`/employees/${m.id}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-accent/60">
                <span className="flex min-w-0 items-center gap-3">
                  <Avatar name={m.name} />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-foreground">{m.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">{m.designation ?? "—"}</span>
                  </span>
                </span>
                <StatusBadge status={m.today_status ?? "not_marked"} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
