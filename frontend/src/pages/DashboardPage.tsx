/**
 * Dashboard — role-aware.
 * admin/hr: GET /dashboard/summary (KPIs + charts). employee/manager: GET /dashboard/me (personal + team).
 */
import {
  ArrowRight,
  Award,
  Bot,
  Building2,
  CalendarCheck,
  CalendarDays,
  CalendarX,
  Clock,
  Info,
  Palmtree,
  RefreshCw,
  Sparkles,
  TimerReset,
  TrendingUp,
  UserCheck,
  UserPlus,
  Users,
  UserX,
  Wallet,
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Avatar } from "@/components/Avatar";
import { ATTENDANCE_SERIES, AXIS_TICK, BarList, GRID_STROKE, Legend, TOOLTIP_STYLE } from "@/components/charts";
import { DataTable } from "@/components/DataTable";
import { LeaveBalanceGrid } from "@/components/LeaveBalanceGrid";
import { PageHeader, Panel } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { TodayAttendanceCard } from "@/components/TodayAttendanceCard";
import { Button } from "@/components/ui/button";
import { displayName, useAuth } from "@/lib/auth";
import { formatDate, formatINR, formatMinutes, formatNumber, humanize, monthLabel } from "@/lib/format";
import { Link, navigate } from "@/lib/router";
import type { DashboardMe, DashboardSummary, Role } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

function greeting(role: Role | null, name: string) {
  switch (role) {
    case "admin":
      return { title: "Welcome, Admin!", subtitle: "Full system overview." };
    case "hr":
      return { title: "Welcome, HR!", subtitle: "Employee & attendance overview." };
    case "manager":
      return { title: "Welcome, Manager!", subtitle: "Team overview." };
    default:
      return { title: `Welcome back, ${name.split(" ")[0] || "there"}!`, subtitle: "Here's your overview." };
  }
}

export function DashboardPage() {
  const { role, user } = useAuth();
  const isHR = role === "admin" || role === "hr";
  const g = greeting(role, displayName(user));
  return isHR ? <HRDashboard title={g.title} subtitle={g.subtitle} /> : <PersonalDashboard title={g.title} subtitle={g.subtitle} />;
}

// ─────────────────────────────────────────────────────────────────────────────
// HR / Admin
// ─────────────────────────────────────────────────────────────────────────────

function HRDashboard({ title, subtitle }: { title: string; subtitle: string }) {
  const { data, loading, error, reload } = useFetch<DashboardSummary>("/dashboard/summary");

  return (
    <>
      <PageHeader
        title={title}
        subtitle={
          <>
            {subtitle}
            {data?.month && <span className="text-ink-muted"> · Period: {data.month}</span>}
          </>
        }
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading} className="bg-white">
            <RefreshCw className={loading ? "size-3.5 animate-spin" : "size-3.5"} /> Refresh
          </Button>
        }
      />
      <AsyncContent loading={loading && !data} error={error} onRetry={reload} loadingLabel="Loading HR analytics...">
        {data && <HRDashboardBody data={data} />}
      </AsyncContent>
    </>
  );
}

function HRDashboardBody({ data }: { data: DashboardSummary }) {
  const { kpis } = data;
  const monthly = data.monthly_attendance ?? [];
  const leaveTotal = data.leave_breakdown.reduce((s, l) => s + l.count, 0);

  return (
    <div className="flex flex-col gap-5">
      {data.is_fallback_date && (
        <Notice tone="info" icon={<Info />}>
          Showing data for <strong>{formatDate(data.reference_date)}</strong> — latest available.
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 sm:gap-4">
        <StatCard label="Total Employees" value={formatNumber(kpis.total_employees)} hint="Active staff" icon={<Users />} tone="navy" />
        <StatCard label="Present" value={formatNumber(kpis.present_today)} hint={formatDate(data.reference_date)} icon={<UserCheck />} tone="green" />
        <StatCard label="Absent" value={formatNumber(kpis.absent_today)} hint="Unplanned" icon={<UserX />} tone="red" />
        <StatCard label="On Leave" value={formatNumber(kpis.on_leave_today)} hint="Approved leave" icon={<Palmtree />} tone="violet" />
        <StatCard label="Late" value={formatNumber(kpis.late_today)} hint="After 09:15" icon={<Clock />} tone="amber" />
        <StatCard label="Overtime" value={`${formatNumber(kpis.total_overtime_hours, 1)}h`} hint={`${data.month}`} icon={<TrendingUp />} tone="blue" />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Attendance by Department"
          subtitle={`Present vs headcount · ${formatDate(data.reference_date)}`}
          icon={<Building2 />}
        >
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

        <Panel title="Leave Usage" subtitle={`${leaveTotal} request${leaveTotal === 1 ? "" : "s"} by type`} icon={<Palmtree />}>
          {data.leave_breakdown.length === 0 ? (
            <EmptyState title="No leave requests" description="No leave applications recorded for this period." />
          ) : (
            <BarList
              color="#7c3aed"
              items={data.leave_breakdown.map((l) => ({ key: l.type, label: humanize(l.type), value: l.count }))}
              formatValue={(v) => `${v}`}
            />
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Monthly Attendance"
          subtitle="Attendance days by status per month"
          icon={<CalendarCheck />}
          actions={<Legend items={ATTENDANCE_SERIES.map((s) => ({ label: s.label, color: s.color }))} />}
        >
          {monthly.length === 0 ? (
            <EmptyState title="No monthly trend yet" description="Monthly attendance data is not available." />
          ) : (
            <div className="h-[260px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthly} margin={{ top: 8, right: 8, left: -16, bottom: 0 }} barCategoryGap="28%">
                  <CartesianGrid vertical={false} stroke={GRID_STROKE} />
                  <XAxis dataKey="label" tick={AXIS_TICK} axisLine={false} tickLine={false} />
                  <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip {...TOOLTIP_STYLE} />
                  {ATTENDANCE_SERIES.map((s, i) => (
                    <Bar
                      key={s.key}
                      dataKey={s.key}
                      name={s.label}
                      stackId="a"
                      fill={s.color}
                      stroke="#ffffff"
                      strokeWidth={1}
                      maxBarSize={44}
                      radius={i === ATTENDANCE_SERIES.length - 1 ? [4, 4, 0, 0] : 0}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {monthly.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {monthly.map((m) => (
                <span key={m.month} className="rounded-md bg-slate-50 px-2 py-1 text-xs text-ink-muted">
                  {m.label}: <strong className="text-ink">{formatNumber(m.attendance_rate, 1)}%</strong> attendance
                </span>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Quick Actions" icon={<Sparkles />}>
          <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-1 xl:grid-cols-2">
            {[
              { label: "Add Employee", to: "/employees/add", icon: UserPlus, tone: "bg-blue-50 text-blue-600" },
              { label: "View Attendance", to: "/attendance", icon: CalendarCheck, tone: "bg-emerald-50 text-emerald-600" },
              { label: "Leave Requests", to: "/leave", icon: CalendarDays, tone: "bg-violet-50 text-violet-600" },
              { label: "Ask AI", to: "/assistant", icon: Bot, tone: "bg-amber-50 text-amber-600" },
            ].map(({ label, to, icon: Icon, tone }) => (
              <Link
                key={to}
                to={to}
                className="flex flex-col items-start gap-2 rounded-lg border border-border p-3 text-sm font-medium text-ink transition-colors hover:border-brand/40 hover:bg-brand-light/50"
              >
                <span className={`flex size-8 items-center justify-center rounded-md ${tone}`}>
                  <Icon className="size-4" />
                </span>
                {label}
              </Link>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="Overtime Leaders" subtitle={data.month} icon={<Award />}>
          {data.overtime_leaders.length === 0 ? (
            <EmptyState title="No overtime recorded" />
          ) : (
            <BarList
              color="#2563eb"
              items={data.overtime_leaders.map((o) => ({
                key: o.name,
                label: o.name,
                sublabel: o.department,
                value: o.overtime_hours,
              }))}
              formatValue={(v) => `${formatNumber(v, 1)} h`}
            />
          )}
        </Panel>
        <Panel title="Late Coming" subtitle={data.month} icon={<TimerReset />}>
          {data.late_leaders.length === 0 ? (
            <EmptyState title="No late arrivals" />
          ) : (
            <BarList
              color="#d97706"
              items={data.late_leaders.map((l) => ({
                key: l.name,
                label: l.name,
                sublabel: `${l.department} · ${formatMinutes(l.total_late_minutes)} total`,
                value: l.late_count,
              }))}
              formatValue={(v) => `${v}×`}
            />
          )}
        </Panel>
      </div>

      <Panel
        title="Recent Leave Requests"
        icon={<CalendarX />}
        bodyClassName="p-0"
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate("/leave")} className="text-brand">
            View all <ArrowRight className="size-3.5" />
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
                    <p className="text-xs text-ink-muted">{r.department}</p>
                  </div>
                </div>
              ),
            },
            { key: "type", header: "Type", render: (r) => humanize(r.leave_type) },
            { key: "dates", header: "Dates", render: (r) => `${formatDate(r.from_date)} – ${formatDate(r.to_date)}` },
            { key: "reason", header: "Reason", render: (r) => <span className="block max-w-[260px] truncate text-ink-muted">{r.reason || "—"}</span> },
            { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
          ]}
        />
      </Panel>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Employee / Manager
// ─────────────────────────────────────────────────────────────────────────────

function PersonalDashboard({ title, subtitle }: { title: string; subtitle: string }) {
  const { data, loading, error, reload } = useFetch<DashboardMe>("/dashboard/me");
  return (
    <>
      <PageHeader
        title={title}
        subtitle={
          <>
            {subtitle}
            {data?.month_label && <span> · {data.month_label}</span>}
          </>
        }
        actions={
          <Button variant="outline" size="sm" onClick={reload} disabled={loading} className="bg-white">
            <RefreshCw className={loading ? "size-3.5 animate-spin" : "size-3.5"} /> Refresh
          </Button>
        }
      />
      <AsyncContent loading={loading && !data} error={error} onRetry={reload} loadingLabel="Loading your overview...">
        {data && <PersonalBody data={data} onAttendanceChange={reload} />}
      </AsyncContent>
    </>
  );
}

function PersonalBody({ data, onAttendanceChange }: { data: DashboardMe; onAttendanceChange: () => void }) {
  const a = data.attendance;
  return (
    <div className="flex flex-col gap-5">
      {!data.employee && (
        <Notice tone="warning" icon={<Info />}>
          Your login is not linked to an employee profile yet. Some sections may be empty — contact HR.
        </Notice>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <TodayAttendanceCard onChange={onAttendanceChange} />
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:col-span-2">
          <StatCard label="Attendance" value={`${formatNumber(a.attendance_percentage, 1)}%`} hint={data.month_label} icon={<TrendingUp />} tone="blue" />
          <StatCard label="Present days" value={a.present_days} hint={`${a.half_day_days} half day${a.half_day_days === 1 ? "" : "s"}`} icon={<UserCheck />} tone="green" />
          <StatCard label="Absent / Leave" value={`${a.absent_days} / ${a.leave_days}`} hint={data.month_label} icon={<UserX />} tone="red" />
          <StatCard label="Late days" value={a.late_days} hint={`Overtime ${formatMinutes(a.total_overtime_minutes)}`} icon={<Clock />} tone="amber" />
        </div>
      </div>

      <Panel
        title="Leave Balance"
        subtitle={data.leave_balance[0]?.year ? `Calendar year ${data.leave_balance[0].year}` : "Current calendar year"}
        icon={<Palmtree />}
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate("/leave")} className="text-brand">
            Apply leave <ArrowRight className="size-3.5" />
          </Button>
        }
      >
        {data.leave_balance.length === 0 ? (
          <EmptyState title="No leave balance available" />
        ) : (
          <LeaveBalanceGrid balances={data.leave_balance} />
        )}
      </Panel>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel
          title="Latest Payslip"
          icon={<Wallet />}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/payroll")} className="text-brand">
              All payslips <ArrowRight className="size-3.5" />
            </Button>
          }
        >
          {data.latest_salary ? (
            <div>
              <p className="text-xs text-ink-muted">{monthLabel(data.latest_salary.month, data.latest_salary.year)}</p>
              <p className="mt-1 text-3xl font-bold tabular-nums text-navy">{formatINR(data.latest_salary.net_salary)}</p>
              <p className="text-xs text-ink-muted">Net pay</p>
              <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <dt className="text-ink-muted">Gross</dt>
                <dd className="text-right tabular-nums">{formatINR(data.latest_salary.gross_salary)}</dd>
                <dt className="text-ink-muted">Overtime</dt>
                <dd className="text-right tabular-nums">{formatINR(data.latest_salary.overtime_amount)}</dd>
                <dt className="text-ink-muted">PF</dt>
                <dd className="text-right tabular-nums">−{formatINR(data.latest_salary.pf)}</dd>
                <dt className="text-ink-muted">Deductions</dt>
                <dd className="text-right tabular-nums">−{formatINR(data.latest_salary.deductions)}</dd>
              </dl>
            </div>
          ) : (
            <EmptyState title="No payslips yet" />
          )}
        </Panel>

        <section className="hr-card flex flex-col justify-between gap-4 bg-gradient-to-br from-navy to-navy-dark p-6 text-white">
          <div>
            <span className="flex size-10 items-center justify-center rounded-lg bg-white/10">
              <Bot className="size-5" />
            </span>
            <h2 className="mt-4 text-lg font-semibold">Ask the AI assistant</h2>
            <p className="mt-1 text-sm text-blue-100">
              Get instant answers about your attendance, leave balance, salary and company policies.
            </p>
            <ul className="mt-3 space-y-1 text-sm text-blue-100">
              <li>“What is my leave balance?”</li>
              <li>“How many days was I late this month?”</li>
            </ul>
          </div>
          <Button onClick={() => navigate("/assistant")} className="w-fit bg-white text-navy hover:bg-blue-50">
            Open AI Assistant <ArrowRight className="size-4" />
          </Button>
        </section>
      </div>

      {data.team && (
        <Panel
          title="My Team"
          subtitle={`${data.team.size} direct report${data.team.size === 1 ? "" : "s"}`}
          icon={<Users />}
          actions={
            <Button variant="ghost" size="sm" onClick={() => navigate("/leave")} className="text-brand">
              Pending approvals ({data.team.pending_leaves}) <ArrowRight className="size-3.5" />
            </Button>
          }
        >
          <div className="mb-4 grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-ink">{data.team.present_today}</p>
              <p className="text-xs text-ink-muted">Present today</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-ink">{data.team.on_leave_today}</p>
              <p className="text-xs text-ink-muted">On leave</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3 text-center">
              <p className="text-xl font-bold text-ink">{data.team.pending_leaves}</p>
              <p className="text-xs text-ink-muted">Pending leaves</p>
            </div>
          </div>
          {data.team.members.length === 0 ? (
            <EmptyState title="No team members" />
          ) : (
            <ul className="divide-y divide-border">
              {data.team.members.map((m) => (
                <li key={m.id}>
                  <Link to={`/employees/${m.id}`} className="flex items-center justify-between gap-3 rounded-md px-1 py-2.5 hover:bg-slate-50">
                    <span className="flex min-w-0 items-center gap-3">
                      <Avatar name={m.name} size="sm" />
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-ink">{m.name}</span>
                        <span className="block truncate text-xs text-ink-muted">{m.designation ?? "—"}</span>
                      </span>
                    </span>
                    <StatusBadge status={m.today_status ?? "not_marked"} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </div>
  );
}
