/**
 * My payslips (employee / manager): GET /salary/me — the caller's OWN salary rows only (salary visibility unchanged:
 * managers never see anyone else's salary). KPIs are derived client-side from those rows.
 */
import { useState } from "react";
import { ArrowRight, Banknote, CalendarRange, Landmark, MinusCircle, Receipt, UserX } from "lucide-react";
import { PayslipModal } from "@/components/PayslipModal";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { CardSkeletons, EmptyState, ErrorState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/lib/auth";
import { formatDate, formatINR, monthLabel } from "@/lib/format";
import type { SalaryRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { plural } from "./shared";

export function MyPayslips() {
  const { user } = useAuth();
  const linked = !!user?.employee;
  const { data, loading, error, reload } = useFetch<SalaryRecord[]>(linked ? "/salary/me" : null);
  const [slip, setSlip] = useState<SalaryRecord | null>(null);

  const rows = (data ?? []).slice().sort((a, b) => b.year - a.year || b.month - a.month);
  const latest = rows[0];
  const latestYearRows = latest ? rows.filter((r) => r.year === latest.year) : [];
  const yearNet = latestYearRows.reduce((t, r) => t + Number(r.net_salary), 0);

  let body;
  if (!linked) {
    body = (
      <div className="hr-card">
        <EmptyState icon={<UserX />} title="No employee profile linked" description="Your account isn't linked to an employee record, so there are no payslips to show. Contact HR if this is unexpected." />
      </div>
    );
  } else if (loading) {
    body = (
      <>
        <CardSkeletons count={4} className="mb-5 grid-cols-2 sm:gap-4 md:grid-cols-4" />
        <CardSkeletons count={6} className="grid-cols-1 sm:grid-cols-2 xl:grid-cols-3" itemClassName="h-40" />
      </>
    );
  } else if (error) {
    body = (
      <div className="hr-card">
        <ErrorState message={error} onRetry={reload} />
      </div>
    );
  } else if (!latest) {
    body = (
      <div className="hr-card">
        <EmptyState icon={<Receipt />} title="No payslips yet" description="Your payslips will appear here once HR runs payroll for a month." />
      </div>
    );
  } else {
    body = (
      <>
        <div className="mb-5 grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4">
          <StatCard
            label="Latest net pay"
            numeric={Number(latest.net_salary)}
            format={(n) => formatINR(n)}
            hint={monthLabel(latest.month, latest.year)}
            icon={<Landmark />}
            tone="brand"
          />
          <StatCard label="Earnings (latest)" numeric={Number(latest.gross_salary) + Number(latest.overtime_amount)} format={(n) => formatINR(n)} hint={`Incl. ${formatINR(latest.overtime_amount)} overtime`} icon={<Banknote />} tone="brand" />
          <StatCard
            label="Deductions (latest)"
            numeric={Number(latest.pf) + Number(latest.deductions)}
            format={(n) => formatINR(n)}
            hint={`PF ${formatINR(latest.pf)} · other ${formatINR(latest.deductions)}`}
            icon={<MinusCircle />}
            tone="neutral"
          />
          <StatCard label={`Net pay in ${latest.year}`} numeric={yearNet} format={(n) => formatINR(n)} hint={plural(latestYearRows.length, "payslip")} icon={<CalendarRange />} tone="neutral" />
        </div>

        <h2 className="mb-3 text-base font-semibold text-foreground">All payslips</h2>
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((r) => (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => setSlip(r)}
                aria-label={`View payslip for ${monthLabel(r.month, r.year)}`}
                className="card-interactive group flex h-full w-full flex-col rounded-xl border border-border bg-surface p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <span className="flex size-8 items-center justify-center rounded-lg bg-brand-subtle text-brand-subtle-foreground">
                      <Receipt className="size-4" aria-hidden="true" />
                    </span>
                    {monthLabel(r.month, r.year)}
                  </span>
                  <StatusBadge status={r.paid_at ? "paid" : "unpaid"} />
                </span>
                <span className="mt-4 text-[28px] leading-9 font-semibold tracking-tight text-foreground tabular-nums">{formatINR(r.net_salary)}</span>
                <span className="text-xs text-muted-foreground">
                  Net pay · Gross {formatINR(r.gross_salary)} · Deductions {formatINR(Number(r.pf) + Number(r.deductions))}
                </span>
                <span className="mt-4 flex items-center justify-between gap-2 border-t border-border pt-3 text-xs">
                  <span className="text-muted-foreground">{r.paid_at ? `Paid on ${formatDate(r.paid_at)}` : "Awaiting payment"}</span>
                  <span className="inline-flex items-center gap-1 font-medium text-brand">
                    View payslip <ArrowRight className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden="true" />
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </>
    );
  }

  return (
    <>
      <PageHeader title="My payslips" subtitle="Your monthly salary statements" />
      {body}
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
