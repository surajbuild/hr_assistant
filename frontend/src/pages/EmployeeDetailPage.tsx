/**
 * Employee profile (/employees/:id) and My Profile (/my-profile → GET /employees/me).
 * Tabs: Attendance · Leaves · Salary (salary hidden for managers viewing others).
 */
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Briefcase, Building2, CalendarCheck, CalendarDays, Hash, Mail, Pencil, UserRound, Wallet } from "lucide-react";
import { AttendanceTable, MonthKeySelect, monthsInRecords, summarize } from "@/components/AttendanceTable";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { PayslipModal } from "@/components/PayslipModal";
import { AsyncContent, EmptyState, ErrorState, LoadingState } from "@/components/States";
import { RoleBadge, StatusBadge } from "@/components/StatusBadge";
import { Tabs } from "@/components/Tabs";
import { Button } from "@/components/ui/button";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { daysBetween, formatDate, formatINR, formatMinutes, humanize, monthLabel } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { AttendanceRecord, Employee, Leave, LeaveListItem, SalaryRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

type TabKey = "attendance" | "leaves" | "salary";

export function EmployeeDetailPage({ id, self }: { id?: number; self?: boolean }) {
  const { user, role } = useAuth();
  const viewingSelf = !!self || (!!user?.employee && user.employee.id === id);
  const path = self ? "/employees/me" : `/employees/${id}`;
  const { data: emp, loading, error, reload } = useFetch<Employee>(path);

  const canEdit = role === "admin" || role === "hr";
  const canSeeSalary = viewingSelf || canEdit;

  if (loading) return <LoadingState label="Loading profile..." />;
  if (error) {
    return (
      <>
        <PageHeader title={self ? "My Profile" : "Employee"} />
        <div className="hr-card">
          <ErrorState
            message={self && /not found|404/i.test(error) ? "Your login is not linked to an employee profile yet. Contact HR." : error}
            onRetry={reload}
          />
        </div>
      </>
    );
  }
  if (!emp) return null;

  return (
    <>
      <PageHeader
        title={self ? "My Profile" : "Employee Profile"}
        subtitle={self ? "Your personal and employment details" : undefined}
        actions={
          <>
            {!self && (
              <Button variant="outline" className="bg-white" onClick={() => navigate("/employees")}>
                <ArrowLeft className="size-4" /> Back
              </Button>
            )}
            {canEdit && (
              <Button onClick={() => navigate(`/employees/${emp.id}/edit`)}>
                <Pencil className="size-4" /> Edit
              </Button>
            )}
          </>
        }
      />

      <ProfileHeader emp={emp} email={viewingSelf ? (emp.email ?? user?.email) : emp.email} role={viewingSelf ? (emp.role ?? user?.role) : emp.role} />

      <ProfileTabs emp={emp} viewingSelf={viewingSelf} canSeeSalary={canSeeSalary} />
    </>
  );
}

function ProfileHeader({ emp, email, role }: { emp: Employee; email?: string | null; role?: string | null }) {
  const info = [
    { icon: Hash, label: "Employee code", value: emp.employee_code },
    { icon: Building2, label: "Department", value: emp.department ?? "—" },
    { icon: Briefcase, label: "Designation", value: emp.designation ?? "—" },
    { icon: CalendarDays, label: "Joining date", value: formatDate(emp.joining_date) },
    { icon: UserRound, label: "Reporting manager", value: emp.manager_name ?? (emp.manager_id ? `#${emp.manager_id}` : "—") },
    { icon: Mail, label: "Email", value: email ?? "—" },
  ];
  return (
    <section className="hr-card mb-5 overflow-hidden">
      <div className="h-20 bg-gradient-to-r from-navy to-brand" />
      <div className="px-5 pb-5">
        {/* Avatar overlaps the 80px banner by 40px; the name block starts below the banner so dark text never sits on navy */}
        <div className="-mt-10 flex flex-col gap-4 sm:flex-row sm:items-start">
          <Avatar name={emp.name} size="xl" className="ring-4 ring-white" />
          <div className="min-w-0 flex-1 sm:pt-12">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-bold text-ink">{emp.name}</h2>
              <StatusBadge status={emp.status} />
              {role && <RoleBadge role={role} />}
            </div>
            <p className="text-sm text-ink-muted">
              {[emp.designation, emp.department].filter(Boolean).join(" · ") || "—"} · {emp.employee_code}
            </p>
          </div>
        </div>
        <dl className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {info.map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-2.5">
              <Icon className="mt-0.5 size-4 shrink-0 text-ink-muted" />
              <div className="min-w-0">
                <dt className="text-xs text-ink-muted">{label}</dt>
                <dd className="truncate text-sm font-medium text-ink">{value}</dd>
              </div>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

function ProfileTabs({ emp, viewingSelf, canSeeSalary }: { emp: Employee; viewingSelf: boolean; canSeeSalary: boolean }) {
  const [tab, setTab] = useState<TabKey>("attendance");
  const tabs = [
    { key: "attendance" as const, label: "Attendance", icon: <CalendarCheck /> },
    { key: "leaves" as const, label: "Leaves", icon: <CalendarDays /> },
    ...(canSeeSalary ? [{ key: "salary" as const, label: "Salary", icon: <Wallet /> }] : []),
  ];
  return (
    <div className="hr-card">
      <Tabs tabs={tabs} value={tab} onChange={setTab} className="px-3" />
      <div className="p-0">
        {tab === "attendance" && <AttendanceTab emp={emp} viewingSelf={viewingSelf} />}
        {tab === "leaves" && <LeavesTab emp={emp} viewingSelf={viewingSelf} />}
        {tab === "salary" && canSeeSalary && <SalaryTab emp={emp} viewingSelf={viewingSelf} />}
      </div>
    </div>
  );
}

function AttendanceTab({ emp, viewingSelf }: { emp: Employee; viewingSelf: boolean }) {
  const path = viewingSelf ? "/attendance/me" : `/attendance/records${qs({ employee_id: emp.id })}`;
  const { data, loading, error, reload } = useFetch<AttendanceRecord[]>(path);
  const records = data ?? [];
  const months = useMemo(() => monthsInRecords(records), [records]);
  const [month, setMonth] = useState<string | null>(null);
  useEffect(() => {
    if (month === null && months.length > 0) setMonth(months[0]!);
  }, [months, month]);
  const filtered = month ? records.filter((r) => r.attendance_date.startsWith(month)) : records;
  const s = summarize(filtered);

  return (
    <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading attendance...">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div className="flex flex-wrap gap-2 text-xs">
          <Chip label="Present" value={s.present} />
          <Chip label="Absent" value={s.absent} />
          <Chip label="Half day" value={s.half} />
          <Chip label="Leave" value={s.leave} />
          <Chip label="Late" value={s.late} />
          <Chip label="Worked" value={formatMinutes(s.work)} />
          <Chip label="Overtime" value={formatMinutes(s.ot)} />
        </div>
        <MonthKeySelect months={months} value={month ?? ""} onChange={setMonth} />
      </div>
      <AttendanceTable records={filtered} />
    </AsyncContent>
  );
}

function Chip({ label, value }: { label: string; value: string | number }) {
  return (
    <span className="rounded-md bg-slate-100 px-2 py-1 text-ink-muted">
      {label}: <strong className="text-ink">{value}</strong>
    </span>
  );
}

function LeavesTab({ emp, viewingSelf }: { emp: Employee; viewingSelf: boolean }) {
  const { role } = useAuth();
  // self → /leaves/me · hr/admin → /leaves/{id} · manager → /leaves (team) filtered client-side
  const path = viewingSelf ? "/leaves/me" : role === "manager" ? "/leaves" : `/leaves/${emp.id}`;
  const { data, loading, error, reload } = useFetch<(Leave | LeaveListItem)[] | { items: LeaveListItem[] }>(path);
  const list: (Leave | LeaveListItem)[] = Array.isArray(data) ? data : (data?.items ?? []);
  const rows = (role === "manager" && !viewingSelf ? list.filter((l) => l.employee_id === emp.id) : list)
    .slice()
    .sort((a, b) => b.from_date.localeCompare(a.from_date));

  return (
    <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading leaves...">
      <DataTable
        rows={rows}
        rowKey={(l) => l.id}
        empty={<EmptyState icon={<CalendarDays className="size-6" />} title="No leave records" />}
        columns={[
          { key: "type", header: "Type", render: (l) => <span className="font-medium">{humanize(l.leave_type)}</span> },
          { key: "from", header: "From", render: (l) => formatDate(l.from_date) },
          { key: "to", header: "To", render: (l) => formatDate(l.to_date) },
          { key: "days", header: "Days", align: "right", render: (l) => ("days" in l && l.days ? l.days : daysBetween(l.from_date, l.to_date)) },
          { key: "reason", header: "Reason", render: (l) => <span className="block max-w-[280px] truncate text-ink-muted">{l.reason || "—"}</span> },
          { key: "status", header: "Status", render: (l) => <StatusBadge status={l.status} /> },
        ]}
      />
    </AsyncContent>
  );
}

function SalaryTab({ emp, viewingSelf }: { emp: Employee; viewingSelf: boolean }) {
  const path = viewingSelf ? "/salary/me" : `/salary/${emp.id}`;
  const { data, loading, error, reload } = useFetch<SalaryRecord[]>(path);
  const [slip, setSlip] = useState<SalaryRecord | null>(null);
  const rows = (data ?? []).slice().sort((a, b) => b.year - a.year || b.month - a.month);

  return (
    <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading salary...">
      <DataTable
        rows={rows}
        rowKey={(r) => r.id}
        onRowClick={setSlip}
        empty={<EmptyState icon={<Wallet className="size-6" />} title="No salary records" />}
        columns={[
          { key: "month", header: "Month", render: (r) => <span className="font-medium">{monthLabel(r.month, r.year)}</span> },
          { key: "gross", header: "Gross", align: "right", render: (r) => formatINR(r.gross_salary) },
          { key: "ot", header: "Overtime", align: "right", render: (r) => formatINR(r.overtime_amount) },
          { key: "pf", header: "PF", align: "right", render: (r) => formatINR(r.pf) },
          { key: "ded", header: "Deductions", align: "right", render: (r) => formatINR(r.deductions) },
          { key: "net", header: "Net Pay", align: "right", render: (r) => <span className="font-semibold text-navy">{formatINR(r.net_salary)}</span> },
          {
            key: "view",
            header: <span className="sr-only">View</span>,
            align: "right",
            render: (r) => (
              <Button variant="ghost" size="sm" className="text-brand" onClick={(e) => (e.stopPropagation(), setSlip(r))}>
                View payslip
              </Button>
            ),
          },
        ]}
      />
      <PayslipModal
        slip={slip}
        employeeName={emp.name}
        employeeCode={emp.employee_code}
        department={emp.department}
        designation={emp.designation}
        onClose={() => setSlip(null)}
      />
    </AsyncContent>
  );
}
