/**
 * Payroll — admin/hr: monthly salary register (GET /salary, /salary/summary) + CSV export
 * + "Generate payroll" (POST /salary/generate, payroll engine — D-021).
 * employee/manager: My Payslips (GET /salary/me) with printable payslip modal.
 */
import { useState } from "react";
import { Banknote, Calculator, Download, Landmark, MinusCircle, PiggyBank, Receipt, TrendingUp, Users, Wallet } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { MonthSelect, SearchInput, YearSelect } from "@/components/Field";
import { GeneratePayrollModal } from "@/components/GeneratePayrollModal";
import { PageHeader, Panel } from "@/components/PageHeader";
import { PayslipModal } from "@/components/PayslipModal";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCSV, formatDate, formatINR, monthLabel } from "@/lib/format";
import type { SalaryList, SalaryRecord, SalarySummary } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export function PayrollPage() {
  const { role } = useAuth();
  return role === "admin" || role === "hr" ? <PayrollRegister /> : <MyPayslips />;
}

function PayrollRegister() {
  const [sel, setSel] = useState<{ month: number; year: number } | null>(null);
  const list = useFetch<SalaryList>(`/salary${qs({ month: sel?.month, year: sel?.year })}`);
  const month = sel?.month ?? list.data?.month ?? new Date().getMonth() + 1;
  const year = sel?.year ?? list.data?.year ?? new Date().getFullYear();
  const summary = useFetch<SalarySummary>(list.data || sel ? `/salary/summary${qs({ month, year })}` : null);
  const [search, setSearch] = useState("");
  const [slip, setSlip] = useState<SalaryRecord | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const now = new Date();
  const isFuture = year > now.getFullYear() || (year === now.getFullYear() && month > now.getMonth() + 1);

  const items = list.data?.items ?? [];
  const q = search.toLowerCase();
  const rows = items.filter(
    (r) => !q || (r.employee_name ?? "").toLowerCase().includes(q) || (r.employee_code ?? "").toLowerCase().includes(q) || (r.department ?? "").toLowerCase().includes(q),
  );
  const s = summary.data;

  function exportCSV() {
    downloadCSV(
      `payroll_${year}_${String(month).padStart(2, "0")}.csv`,
      ["Code", "Employee", "Department", "Month", "Year", "Gross", "Overtime", "PF", "Deductions", "Net", "Paid At"],
      rows.map((r) => [r.employee_code, r.employee_name, r.department, r.month, r.year, r.gross_salary, r.overtime_amount, r.pf, r.deductions, r.net_salary, r.paid_at]),
    );
  }

  return (
    <>
      <PageHeader
        title="Payroll"
        subtitle={`Salary register · ${monthLabel(month, year)}`}
        actions={
          <>
            <MonthSelect value={month} onChange={(m) => setSel({ month: m, year })} />
            <YearSelect value={year} onChange={(y) => setSel({ month, year: y })} />
            <Button variant="outline" className="bg-white" onClick={exportCSV} disabled={rows.length === 0}>
              <Download className="size-4" /> Export
            </Button>
            <Button
              onClick={() => setGenerateOpen(true)}
              disabled={isFuture}
              title={isFuture ? "Payroll cannot be generated for a future month" : undefined}
            >
              <Calculator className="size-4" /> Generate payroll
            </Button>
          </>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6 sm:gap-4">
        <StatCard label="Employees" value={s?.employee_count ?? items.length} icon={<Users />} tone="navy" />
        <StatCard label="Gross" value={formatINR(s?.total_gross_salary)} icon={<Banknote />} tone="blue" />
        <StatCard label="Overtime" value={formatINR(s?.total_overtime_amount)} icon={<TrendingUp />} tone="violet" />
        <StatCard label="PF" value={formatINR(s?.total_pf)} icon={<PiggyBank />} tone="amber" />
        <StatCard label="Deductions" value={formatINR(s?.total_deductions)} icon={<MinusCircle />} tone="red" />
        <StatCard label="Net Payout" value={formatINR(s?.total_net_salary)} icon={<Landmark />} tone="green" />
      </div>

      <Panel
        title="Salary Register"
        subtitle={list.loading ? undefined : `${rows.length} record${rows.length === 1 ? "" : "s"}`}
        icon={<Wallet />}
        bodyClassName="p-0"
        actions={<SearchInput value={search} onChange={setSearch} placeholder="Search employee..." className="w-full sm:w-64" />}
      >
        <AsyncContent loading={list.loading} error={list.error} onRetry={list.reload} loadingLabel="Loading payroll...">
          <DataTable
            rows={rows}
            rowKey={(r) => r.id}
            onRowClick={setSlip}
            empty={<EmptyState icon={<Wallet className="size-6" />} title="No salary records" description={`No payroll found for ${monthLabel(month, year)}.`} />}
            columns={[
              {
                key: "emp",
                header: "Employee",
                render: (r) => (
                  <div>
                    <p className="font-medium">{r.employee_name ?? `#${r.employee_id}`}</p>
                    <p className="text-xs text-ink-muted">{r.employee_code}</p>
                  </div>
                ),
              },
              { key: "dept", header: "Department", render: (r) => r.department ?? "—" },
              { key: "gross", header: "Gross", align: "right", render: (r) => formatINR(r.gross_salary) },
              { key: "ot", header: "Overtime", align: "right", render: (r) => formatINR(r.overtime_amount) },
              { key: "pf", header: "PF", align: "right", render: (r) => formatINR(r.pf) },
              { key: "ded", header: "Deductions", align: "right", render: (r) => formatINR(r.deductions) },
              { key: "net", header: "Net Pay", align: "right", render: (r) => <span className="font-semibold text-navy">{formatINR(r.net_salary)}</span> },
              {
                key: "paid",
                header: "Status",
                render: (r) => <StatusBadge status={r.paid_at ? "paid" : "unpaid"} label={r.paid_at ? `Paid ${formatDate(r.paid_at)}` : "Unpaid"} />,
              },
            ]}
          />
        </AsyncContent>
      </Panel>
      <PayslipModal slip={slip} onClose={() => setSlip(null)} />
      <GeneratePayrollModal
        open={generateOpen}
        month={month}
        year={year}
        onClose={() => setGenerateOpen(false)}
        onGenerated={() => {
          setSel({ month, year });
          list.reload();
          summary.reload();
        }}
      />
    </>
  );
}

function MyPayslips() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch<SalaryRecord[]>("/salary/me");
  const [slip, setSlip] = useState<SalaryRecord | null>(null);
  const rows = (data ?? []).slice().sort((a, b) => b.year - a.year || b.month - a.month);
  const latest = rows[0];

  return (
    <>
      <PageHeader title="My Payslips" subtitle="Your monthly salary statements" />
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading payslips...">
        {rows.length === 0 ? (
          <div className="hr-card">
            <EmptyState icon={<Receipt className="size-6" />} title="No payslips yet" description="Your payslips will appear here once payroll is processed." />
          </div>
        ) : (
          <>
            {latest && (
              <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4 sm:gap-4">
                <StatCard label="Latest net pay" value={formatINR(latest.net_salary)} hint={monthLabel(latest.month, latest.year)} icon={<Landmark />} tone="green" />
                <StatCard label="Gross" value={formatINR(latest.gross_salary)} icon={<Banknote />} tone="blue" />
                <StatCard label="Overtime" value={formatINR(latest.overtime_amount)} icon={<TrendingUp />} tone="violet" />
                <StatCard label="PF + Deductions" value={formatINR(Number(latest.pf) + Number(latest.deductions))} icon={<MinusCircle />} tone="red" />
              </div>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {rows.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setSlip(r)}
                  className="hr-card group flex flex-col p-5 text-left transition-shadow hover:border-brand/40 hover:shadow-md focus-visible:outline-2 focus-visible:outline-brand"
                >
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Receipt className="size-4 text-brand" />
                      {monthLabel(r.month, r.year)}
                    </span>
                    <StatusBadge status={r.paid_at ? "paid" : "unpaid"} />
                  </div>
                  <p className="mt-3 text-2xl font-bold tabular-nums text-navy">{formatINR(r.net_salary)}</p>
                  <p className="text-xs text-ink-muted">Net pay · Gross {formatINR(r.gross_salary)}</p>
                  <span className="mt-3 text-sm font-medium text-brand group-hover:underline">View payslip →</span>
                </button>
              ))}
            </div>
          </>
        )}
      </AsyncContent>
      <PayslipModal
        slip={slip}
        employeeName={user?.employee?.name}
        employeeCode={user?.employee?.employee_code}
        department={user?.employee?.department}
        designation={user?.employee?.designation}
        onClose={() => setSlip(null)}
      />
    </>
  );
}
