/**
 * Employee profile (/employees/:id) and My Profile (/my-profile → GET /employees/me).
 * Cover header + key facts, then tabs Overview · Attendance · Leave · Payroll (tab kept in `?tab=`).
 *
 * Reads: /employees/{id} | /employees/me · attendance: /attendance/me (self) | /attendance/records?employee_id
 * · leaves: /leaves?employee_id (staff roles, includes working days) | /leaves/me (employee role)
 * · /leaves/balance/me (self only) · salary: /salary/me (self) | /salary/{id} (HR/Admin)
 * · /employees (staff roles, for "Direct reports").
 * Payroll is visible only to the person themself and HR/Admin — managers never see a report's salary (D-021).
 */
import { useState } from "react";
import { ArrowLeft, CalendarCheck, LayoutDashboard, Palmtree, Pencil, UserX, Wallet } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { PayslipModal } from "@/components/PayslipModal";
import { EmptyState, ErrorState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { Button } from "@/components/ui/button";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { navigate, useRoute } from "@/lib/router";
import type { AttendanceRecord, Employee, LeaveBalance, SalaryRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { ProfileHeader, ProfileSkeleton, Surface } from "./people/profile";
import { AttendanceTab, LeaveTab, OverviewTab, PayrollTab, type LeaveRow, type ProfileData, type ProfileTab } from "./people/profileTabs";

const TAB_KEYS: ProfileTab[] = ["overview", "attendance", "leave", "payroll"];

export function EmployeeDetailPage({ id, self }: { id?: number; self?: boolean }) {
  const { user, role } = useAuth();
  const path = self ? "/employees/me" : id !== undefined && !Number.isNaN(id) ? `/employees/${id}` : null;
  const { data: emp, loading, error, reload } = useFetch<Employee>(path);

  const isHrAdmin = role === "admin" || role === "hr";
  const isStaff = isHrAdmin || role === "manager";
  const viewingSelf = !!self || (!!user?.employee && user.employee.id === id);
  const canSeeSalary = viewingSelf || isHrAdmin;

  const header = (
    <PageHeader
      title={self ? "My Profile" : "Employee profile"}
      subtitle={self ? "Your personal and employment details" : viewingSelf ? "This is your own profile" : undefined}
      actions={
        <>
          {!self && (
            <Button variant="outline" onClick={() => navigate("/employees")}>
              <ArrowLeft /> Employees
            </Button>
          )}
          {isHrAdmin && emp && (
            <Button onClick={() => navigate(`/employees/${emp.id}/edit`)}>
              <Pencil /> Edit
            </Button>
          )}
        </>
      }
    />
  );

  if (path === null) {
    return (
      <>
        {header}
        <Surface>
          <EmptyState icon={<UserX />} title="Employee not found" action={<Button size="sm" onClick={() => navigate("/employees")}>Back to employees</Button>} />
        </Surface>
      </>
    );
  }

  if (loading && !emp) {
    return (
      <>
        {header}
        <ProfileSkeleton />
      </>
    );
  }

  if (error || !emp) {
    const notLinked = self && /not found|404/i.test(error ?? "");
    return (
      <>
        {header}
        <Surface>
          {notLinked ? (
            <EmptyState
              icon={<UserX />}
              title="No employee profile linked"
              description="Your login is not linked to an employee profile yet. Contact HR."
              action={
                <Button size="sm" variant="outline" onClick={() => navigate("/dashboard")}>
                  Go to dashboard
                </Button>
              }
            />
          ) : (
            <ErrorState message={error ?? "Failed to load the profile."} onRetry={reload} />
          )}
        </Surface>
      </>
    );
  }

  return (
    <>
      {header}
      <ProfileBody key={emp.id} emp={emp} viewingSelf={viewingSelf} canSeeSalary={canSeeSalary} isStaff={isStaff} isHrAdmin={isHrAdmin} />
    </>
  );
}

function ProfileBody({
  emp,
  viewingSelf,
  canSeeSalary,
  isStaff,
  isHrAdmin,
}: {
  emp: Employee;
  viewingSelf: boolean;
  canSeeSalary: boolean;
  isStaff: boolean;
  isHrAdmin: boolean;
}) {
  const { user } = useAuth();
  const { pathname, query } = useRoute();

  // ── data (fetched once; tabs only render it) ──
  const attendance = useFetch<AttendanceRecord[]>(viewingSelf ? "/attendance/me" : `/attendance/records${qs({ employee_id: emp.id })}`);
  const leaves = useFetch<LeaveRow[]>(isStaff ? `/leaves${qs({ employee_id: emp.id })}` : "/leaves/me");
  const balance = useFetch<LeaveBalance[]>(viewingSelf ? "/leaves/balance/me" : null);
  const salary = useFetch<SalaryRecord[]>(canSeeSalary ? (viewingSelf ? "/salary/me" : `/salary/${emp.id}`) : null);
  const directory = useFetch<Employee[]>(isStaff ? "/employees" : null);
  const reports = (directory.data ?? []).filter((e) => e.manager_id === emp.id && e.id !== emp.id).sort((a, b) => a.name.localeCompare(b.name));

  const data: ProfileData = {
    attendance,
    leaves,
    balance: viewingSelf ? balance : null,
    salary: canSeeSalary ? salary : null,
    reports,
  };

  // ── tabs (?tab= keeps the choice across reloads / back) ──
  const requested = query.get("tab") as ProfileTab | null;
  const tab: ProfileTab = requested && TAB_KEYS.includes(requested) && (requested !== "payroll" || canSeeSalary) ? requested : "overview";
  function setTab(t: ProfileTab) {
    navigate(t === "overview" ? pathname : `${pathname}${qs({ tab: t })}`, { replace: true });
  }
  const tabs = [
    { key: "overview" as const, label: "Overview", icon: <LayoutDashboard /> },
    { key: "attendance" as const, label: "Attendance", icon: <CalendarCheck /> },
    { key: "leave" as const, label: "Leave", icon: <Palmtree /> },
    ...(canSeeSalary ? [{ key: "payroll" as const, label: "Payroll", icon: <Wallet /> }] : []),
  ];

  const [slip, setSlip] = useState<SalaryRecord | null>(null);

  // Manager link only where the API allows opening that profile: HR/Admin (anyone) or your own profile.
  const managerHref = emp.manager_id
    ? emp.manager_id === user?.employee?.id
      ? "/my-profile"
      : isHrAdmin
        ? `/employees/${emp.manager_id}`
        : null
    : null;

  return (
    <div className="flex flex-col gap-5">
      <ProfileHeader
        emp={emp}
        email={viewingSelf ? (emp.email ?? user?.email) : emp.email}
        role={viewingSelf ? (emp.role ?? user?.role) : emp.role}
        managerHref={managerHref}
        showSalary={canSeeSalary}
      />

      <div>
        <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5 max-sm:[&_svg]:hidden" />
        <div role="tabpanel" aria-label={tabs.find((t) => t.key === tab)?.label} className="animate-page-in">
          {tab === "overview" && <OverviewTab data={data} viewingSelf={viewingSelf} onTab={setTab} onOpenSlip={setSlip} />}
          {tab === "attendance" && <AttendanceTab state={attendance} />}
          {tab === "leave" && <LeaveTab data={data} viewingSelf={viewingSelf} />}
          {tab === "payroll" && canSeeSalary && <PayrollTab state={salary} emp={emp} viewingSelf={viewingSelf} onOpenSlip={setSlip} />}
        </div>
      </div>

      {canSeeSalary && (
        <PayslipModal
          slip={slip}
          employeeName={emp.name}
          employeeCode={emp.employee_code}
          department={emp.department}
          designation={emp.designation}
          onClose={() => setSlip(null)}
        />
      )}
    </div>
  );
}
