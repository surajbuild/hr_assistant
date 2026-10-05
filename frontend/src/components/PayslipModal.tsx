/** Payslip view (earnings / deductions / net pay) with print support. */
import { useRef } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDate, formatINR, monthLabel } from "@/lib/format";
import type { SalaryRecord } from "@/lib/types";
import { Modal } from "./Modal";

export function PayslipModal({
  slip,
  employeeName,
  employeeCode,
  department,
  designation,
  onClose,
}: {
  slip: SalaryRecord | null;
  employeeName?: string | null;
  employeeCode?: string | null;
  department?: string | null;
  designation?: string | null;
  onClose: () => void;
}) {
  const contentRef = useRef<HTMLDivElement>(null);

  function handlePrint() {
    const html = contentRef.current?.innerHTML;
    if (!html) return;
    const w = window.open("", "_blank", "width=800,height=900");
    if (!w) {
      window.print();
      return;
    }
    // Copy the app's stylesheets so Tailwind classes render in the print window.
    const styles = [...document.querySelectorAll('link[rel="stylesheet"], style')].map((n) => n.outerHTML).join("\n");
    w.document.write(
      `<!doctype html><html><head><meta charset="utf-8"><title>Payslip</title>${styles}<style>body{background:#fff;padding:24px;font-family:Inter,system-ui,sans-serif}</style></head><body>${html}</body></html>`,
    );
    w.document.close();
    w.focus();
    setTimeout(() => {
      w.print();
    }, 400);
  }

  if (!slip) return null;
  const name = employeeName ?? slip.employee_name ?? "";
  const code = employeeCode ?? slip.employee_code ?? "";
  const dept = department ?? slip.department ?? "";
  const totalEarnings = Number(slip.gross_salary) + Number(slip.overtime_amount);
  const totalDeductions = Number(slip.pf) + Number(slip.deductions);

  return (
    <Modal
      open={!!slip}
      onClose={onClose}
      title="Payslip"
      description={monthLabel(slip.month, slip.year)}
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button onClick={handlePrint}>
            <Printer className="size-4" /> Print
          </Button>
        </>
      }
    >
      <div ref={contentRef}>
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-4">
          <div>
            <p className="text-lg font-bold text-navy">AI HR Assistant</p>
            <p className="text-xs text-ink-muted">Salary slip for {monthLabel(slip.month, slip.year)}</p>
          </div>
          <div className="text-right text-sm">
            <p className="font-semibold text-ink">{name || "—"}</p>
            <p className="text-xs text-ink-muted">
              {[code, dept, designation].filter(Boolean).join(" · ") || "—"}
            </p>
            <p className="text-xs text-ink-muted">Paid on: {slip.paid_at ? formatDate(slip.paid_at) : "Not paid yet"}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 py-4 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-success">Earnings</p>
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Gross salary</dt>
                <dd className="tabular-nums">{formatINR(slip.gross_salary, true)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Overtime</dt>
                <dd className="tabular-nums">{formatINR(slip.overtime_amount, true)}</dd>
              </div>
              <div className="flex justify-between border-t border-border pt-1.5 font-semibold">
                <dt>Total earnings</dt>
                <dd className="tabular-nums">{formatINR(totalEarnings, true)}</dd>
              </div>
            </dl>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-danger">Deductions</p>
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Provident fund (PF)</dt>
                <dd className="tabular-nums">{formatINR(slip.pf, true)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Other deductions</dt>
                <dd className="tabular-nums">{formatINR(slip.deductions, true)}</dd>
              </div>
              <div className="flex justify-between border-t border-border pt-1.5 font-semibold">
                <dt>Total deductions</dt>
                <dd className="tabular-nums">{formatINR(totalDeductions, true)}</dd>
              </div>
            </dl>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-lg bg-navy px-4 py-3 text-white">
          <span className="text-sm font-medium">Net pay</span>
          <span className="text-xl font-bold tabular-nums">{formatINR(slip.net_salary, true)}</span>
        </div>
        <p className="mt-3 text-[11px] text-ink-muted">This is a system-generated payslip and does not require a signature.</p>
      </div>
    </Modal>
  );
}
