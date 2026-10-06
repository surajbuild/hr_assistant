/**
 * Dashboard — four intentionally different layouts, all from existing endpoints:
 *  - admin:    system overview — KPIs, attendance trend, today, departments, approvals, AI activity, access (GET /users, /chat/logs)
 *  - hr:       people operations — approvals first, payroll snapshot (GET /salary), leave usage, departments
 *  - manager:  team board — check-in hero, team status, team approvals, own month/balance/payslip (GET /dashboard/me)
 *  - employee: personal hero — check-in, my month ring + heat-map, leave balance rings, latest payslip
 * Greeting wording is unchanged from the previous design.
 */
import { CalendarCheck, CalendarX, Clock, Info, Palmtree, RefreshCw, TrendingUp, UserCheck, UserPlus, Users, UserX } from "lucide-react";
import { AttendanceHeatmap } from "@/components/AttendanceHeatmap";
import { LeaveBalanceGrid } from "@/components/LeaveBalanceGrid";
import { PageHeader, Panel } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, CardSkeletons, EmptyState, ErrorState, Notice } from "@/components/States";
import { TodayAttendanceCard } from "@/components/TodayAttendanceCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { displayName, useAuth } from "@/lib/auth";
import { formatDate, formatNumber, monthLabel } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { AttendanceRecord, DashboardMe, DashboardSummary, Role } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { useDailyTrend, useLatestPayroll, usePendingApprovals } from "./dashboard/data";
import {
  AccessPanel,
  AiActivityPanel,
  AskAiPanel,
  AttendanceTrendPanel,
  DepartmentPanel,
  LatePanel,
  LatestPayslipPanel,
  LeaveUsagePanel,
  MyMonthPanel,
  OvertimePanel,
  PayrollSnapshotPanel,
  PendingApprovalsPanel,
  QuickActions,
  RecentLeavesPanel,
  TeamPanel,
  TodayPanel,
} from "./dashboard/widgets";

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
  const g = greeting(role, displayName(user));
  if (role === "admin" || role === "hr") return <StaffDashboard role={role} title={g.title} subtitle={g.subtitle} />;
  return <PersonalDashboard role={role} title={g.title} subtitle={g.subtitle} />;
}

function RefreshButton({ onClick, busy }: { onClick: () => void; busy: boolean }) {
  return (
    <Button variant="outline" size="sm" onClick={onClick} disabled={busy}>
      <RefreshCw className={busy ? "animate-spin" : undefined} /> Refresh
    </Button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Admin / HR
// ─────────────────────────────────────────────────────────────────────────────

function StaffDashboard({ role, title, subtitle }: { role: "admin" | "hr"; title: string; subtitle: string }) {
  const summary = useFetch<DashboardSummary>("/dashboard/summary");
  const trend = useDailyTrend(summary.data?.reference_date);
  const approvals = usePendingApprovals();
  const payroll = useLatestPayroll();

  function reloadAll() {
    summary.reload();
    trend.reload();
    approvals.reload();
    payroll.reload();
  }
  const data = summary.data;

  return (
    <>
      <PageHeader
        title={title}
        subtitle={
          <>
            {subtitle}
            {data?.month && <span> · Period: {data.month}</span>}
          </>
        }
        actions={
          <>
            <RefreshButton onClick={reloadAll} busy={summary.loading} />
            <Button size="sm" onClick={() => navigate("/employees/add")}>
              <UserPlus /> Add employee
            </Button>
          </>
        }
      />
      <AsyncContent
        loading={summary.loading && !data}
        error={summary.error}
        onRetry={summary.reload}
        skeleton={
          <div className="flex flex-col gap-5">
            <CardSkeletons count={6} className="grid-cols-2 md:grid-cols-3 xl:grid-cols-6" />
            <div className="grid gap-5 lg:grid-cols-3">
              <Skeleton className="h-[360px] lg:col-span-2" />
              <Skeleton className="h-[360px]" />
            </div>
          </div>
        }
      >
        {data && (
          <div className="flex flex-col gap-5">
            {data.is_fallback_date && (
              <Notice tone="info" icon={<Info />}>
                Showing data for <strong>{formatDate(data.reference_date)}</strong> — latest available.
              </Notice>
            )}

            <KpiRow data={data} spark={trend.days.map((d) => d.attending)} />

            {role === "admin" ? (
              <>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <AttendanceTrendPanel days={trend.days} loading={trend.loading} error={trend.error} onRetry={trend.reload} monthly={data.monthly_attendance ?? []} monthName={data.month} />
                  </div>
                  <TodayPanel data={data} />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <DepartmentPanel data={data} className="lg:col-span-2" />
                  <PendingApprovalsPanel items={approvals.items} loading={approvals.loading} error={approvals.error} onRetry={approvals.reload} />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <AiActivityPanel className="lg:col-span-2" />
                  <AccessPanel />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <OvertimePanel data={data} />
                  <LatePanel data={data} />
                  <LeaveUsagePanel data={data} />
                </div>
              </>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <PendingApprovalsPanel className="lg:col-span-2" items={approvals.items} loading={approvals.loading} error={approvals.error} onRetry={approvals.reload} />
                  <TodayPanel data={data} />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <div className="lg:col-span-2">
                    <AttendanceTrendPanel days={trend.days} loading={trend.loading} error={trend.error} onRetry={trend.reload} monthly={data.monthly_attendance ?? []} monthName={data.month} />
                  </div>
                  <PayrollSnapshotPanel snapshot={payroll.snapshot} loading={payroll.loading} error={payroll.error} onRetry={payroll.reload} />
                </div>
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
                  <DepartmentPanel data={data} />
                  <LeaveUsagePanel data={data} />
                  <QuickActions canAdd />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  <OvertimePanel data={data} />
                  <LatePanel data={data} />
                </div>
              </>
            )}

            <RecentLeavesPanel data={data} />
          </div>
        )}
      </AsyncContent>
    </>
  );
}

function KpiRow({ data, spark }: { data: DashboardSummary; spark: number[] }) {
  const { kpis } = data;
  const share = kpis.total_employees > 0 ? (kpis.present_today / kpis.total_employees) * 100 : 0;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 sm:gap-4">
      <StatCard label="Employees" numeric={kpis.total_employees} hint="Active staff" icon={<Users />} tone="brand" />
      <StatCard label="Present" numeric={kpis.present_today} hint={`${formatNumber(share, 0)}% of staff · ${formatDate(data.reference_date)}`} icon={<UserCheck />} tone="present" spark={spark} />
      <StatCard label="Absent" numeric={kpis.absent_today} hint="Unplanned" icon={<UserX />} tone="absent" />
      <StatCard label="On leave" numeric={kpis.on_leave_today} hint="Approved leave" icon={<Palmtree />} tone="leave" />
      <StatCard label="Late" numeric={kpis.late_today} hint="After 09:15" icon={<Clock />} tone="late" />
      <StatCard label="Overtime" numeric={kpis.total_overtime_hours} format={(n) => `${formatNumber(n, 1)}h`} hint={data.month} icon={<TrendingUp />} tone="half" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Employee / Manager
// ─────────────────────────────────────────────────────────────────────────────

function PersonalDashboard({ role, title, subtitle }: { role: Role | null; title: string; subtitle: string }) {
  const me = useFetch<DashboardMe>("/dashboard/me");
  const isManager = role === "manager";
  const approvals = usePendingApprovals(isManager);
  const data = me.data;

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
          <RefreshButton
            onClick={() => {
              me.reload();
              if (isManager) approvals.reload();
            }}
            busy={me.loading}
          />
        }
      />
      <AsyncContent
        loading={me.loading && !data}
        error={me.error}
        onRetry={me.reload}
        skeleton={
          <div className="grid gap-5 lg:grid-cols-3">
            <Skeleton className="h-[340px]" />
            <Skeleton className="h-[340px]" />
            <Skeleton className="h-[340px]" />
          </div>
        }
      >
        {data && (
          <div className="flex flex-col gap-5">
            {!data.employee && (
              <Notice tone="warning" icon={<Info />}>
                Your login is not linked to an employee profile yet. Some sections may be empty — contact HR.
              </Notice>
            )}

            {isManager && data.team ? (
              <>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <TodayAttendanceCard onChange={me.reload} />
                  <TeamPanel team={data.team} className="lg:col-span-2" />
                </div>
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                  <PendingApprovalsPanel className="lg:col-span-2" title="Team approvals" items={approvals.items} loading={approvals.loading} error={approvals.error} onRetry={approvals.reload} />
                  <MyMonthPanel data={data} />
                </div>
              </>
            ) : (
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
                <TodayAttendanceCard onChange={me.reload} />
                <MyMonthPanel data={data} />
                <MonthHeatmapPanel />
              </div>
            )}

            <Panel
              title="Leave balance"
              subtitle={data.leave_balance[0]?.year ? `Calendar year ${data.leave_balance[0].year}` : "Current calendar year"}
              icon={<Palmtree />}
              actions={
                <Button variant="ghost" size="sm" onClick={() => navigate("/leave")}>
                  Apply leave
                </Button>
              }
            >
              {data.leave_balance.length === 0 ? <EmptyState title="No leave balance available" className="py-8" /> : <LeaveBalanceGrid balances={data.leave_balance} />}
            </Panel>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <LatestPayslipPanel data={data} />
              <AskAiPanel
                suggestions={
                  isManager
                    ? ["Who on my team is on leave today?", "What is my leave balance?"]
                    : ["What is my leave balance?", "How many days was I late this month?"]
                }
              />
            </div>
          </div>
        )}
      </AsyncContent>
    </>
  );
}

/** Heat-map of the employee's own days (GET /attendance/me), for the month of their latest record. */
function MonthHeatmapPanel() {
  const { data, loading, error, reload } = useFetch<AttendanceRecord[]>("/attendance/me");
  const records = data ?? [];
  const latest = records.reduce((m, r) => (r.attendance_date > m ? r.attendance_date : m), "");
  const [y, m] = latest ? latest.split("-").map(Number) : [0, 0];
  return (
    <Panel title="Month at a glance" subtitle={y && m ? monthLabel(m, y) : undefined} icon={<CalendarX />}>
      {loading ? (
        <Skeleton className="h-[220px] w-full" />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} className="py-6" />
      ) : !y || !m ? (
        <EmptyState icon={<CalendarCheck />} title="No attendance yet" description="Your days will appear here after your first check-in." className="py-8" />
      ) : (
        <AttendanceHeatmap records={records} year={y} month={m} />
      )}
    </Panel>
  );
}
