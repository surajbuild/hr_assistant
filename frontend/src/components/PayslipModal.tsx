/**
 * Payslip view (earnings / deductions / net pay, paid status) with print support.
 *
 * Printing opens a clean window (light theme — the app's `.dark` class is not copied) with the app's stylesheets and
 * the `.print-area` block; if pop-ups are blocked it falls back to `window.print()`, where the `@media print` rules in
 * globals.css show only `.print-area`, hide `.no-print`, and force light colours even from dark mode. The printable block
 * therefore only uses surface / foreground / muted / border tokens (the ones those print rules override).
 *
 * Props are backwards compatible (EmployeeDetailPage, PayrollPage); `actions` adds extra footer buttons
 * (e.g. "Mark as paid" for HR/Admin on the payroll register).
 */
import { useRef, type ReactNode } from "react";
import { CheckCircle2, Clock, Printer } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { formatDate, formatINR, monthLabel } from "@/lib/format";
import type { SalaryRecord } from "@/lib/types";
import { Modal } from "./Modal";

type Slip = SalaryRecord & { designation?: string | null };

function Row({ label, value, strong }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className={strong ? "flex justify-between gap-4 border-t border-border pt-2 font-semibold text-foreground" : "flex justify-between gap-4"}>
      <dt className={strong ? undefined : "text-muted-foreground"}>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

export function PayslipModal({
  slip,
  employeeName,
  employeeCode,
  department,
  designation,
  onClose,
  actions,
}: {
  slip: SalaryRecord | null;
  employeeName?: string | null;
  employeeCode?: string | null;
  department?: string | null;
  designation?: string | null;
  onClose: () => void;
  /** Extra footer buttons, rendered before Print. */
  actions?: ReactNode;
}) {
  const contentRef = useRef<HTMLDivElement>(null);

  function handlePrint() {
    const html = contentRef.current?.outerHTML;
    if (!html) return;
    const w = window.open("", "_blank", "width=820,height=900");
    if (!w) {
      window.print();
      return;
    }
    // Copy the app's stylesheets so Tailwind classes and tokens render; <html> has no `.dark`, so tokens are light.
    // Links are re-emitted with their resolved absolute URL (relative hrefs don't resolve reliably in about:blank).
    const styles = [...document.querySelectorAll<HTMLLinkElement | HTMLStyleElement>('link[rel="stylesheet"], style')]
      .map((n) => (n instanceof HTMLLinkElement ? `<link rel="stylesheet" href="${n.href}">` : n.outerHTML))
      .join("\n");
    w.document.write(
      `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Payslip</title>${styles}<style>body{background:var(--surface);color:var(--foreground);padding:24px;font-family:var(--font-sans)}</style></head><body>${html}</body></html>`,
    );
    w.document.close();
    w.focus();
    // Print once the stylesheets have loaded (or after 1.5s at the latest).
    const links = [...w.document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')];
    let printed = false;
    const doPrint = () => {
      if (printed) return;
      printed = true;
      w.print();
    };
    const loaded = links.map(
      (l) =>
        new Promise<void>((resolve) => {
          if (l.sheet) return resolve();
          l.onload = () => resolve();
          l.onerror = () => resolve();
        }),
    );
    void Promise.all(loaded).then(() => setTimeout(doPrint, 100));
    setTimeout(doPrint, 1500);
  }

  if (!slip) return null;
  const s = slip as Slip;
  const name = employeeName ?? s.employee_name ?? "";
  const code = employeeCode ?? s.employee_code ?? "";
  const dept = department ?? s.department ?? "";
  const desig = designation ?? s.designation ?? "";
  const totalEarnings = Number(s.gross_salary) + Number(s.overtime_amount);
  const totalDeductions = Number(s.pf) + Number(s.deductions);
  const period = monthLabel(s.month, s.year);

  const facts: { label: string; value: string }[] = [
    { label: "Employee", value: name || "—" },
    { label: "Employee code", value: code || "—" },
    { label: "Department", value: dept || "—" },
    { label: "Designation", value: desig || "—" },
  ];

  return (
    <Modal
      open={!!slip}
      onClose={onClose}
      title="Payslip"
      description={name ? `${name} · ${period}` : period}
      size="lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          {actions}
          <Button variant={actions ? "outline" : "default"} onClick={handlePrint}>
            <Printer /> Print
          </Button>
        </>
      }
    >
      <div ref={contentRef} className="print-area flex flex-col gap-5 bg-surface text-sm text-foreground">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
          <div className="min-w-0">
            <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Salary slip</p>
            <p className="text-lg font-semibold tracking-tight">{period}</p>
            <p className="text-xs text-muted-foreground">AI HR Assistant</p>
          </div>
          <div className="flex flex-col items-start gap-1 sm:items-end">
            <span className="no-print">
              <StatusBadge status={s.paid_at ? "paid" : "unpaid"} label={s.paid_at ? "Paid" : "Unpaid"} />
            </span>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {s.paid_at ? <CheckCircle2 className="no-print size-3.5" aria-hidden="true" /> : <Clock className="no-print size-3.5" aria-hidden="true" />}
              {s.paid_at ? `Paid on ${formatDate(s.paid_at)}` : "Not paid yet"}
            </p>
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border border-border bg-surface-muted p-3.5 sm:grid-cols-4">
          {facts.map((f) => (
            <div key={f.label} className="min-w-0">
              <dt className="text-xs text-muted-foreground">{f.label}</dt>
              <dd className="truncate font-medium">{f.value}</dd>
            </div>
          ))}
        </dl>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <section aria-labelledby="slip-earnings">
            <h3 id="slip-earnings" className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Earnings
            </h3>
            <dl className="flex flex-col gap-2">
              <Row label="Gross salary" value={formatINR(s.gross_salary, true)} />
              <Row label="Overtime" value={formatINR(s.overtime_amount, true)} />
              <Row label="Total earnings" value={formatINR(totalEarnings, true)} strong />
            </dl>
          </section>
          <section aria-labelledby="slip-deductions">
            <h3 id="slip-deductions" className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              Deductions
            </h3>
            <dl className="flex flex-col gap-2">
              <Row label="Provident fund (PF)" value={formatINR(s.pf, true)} />
              <Row label="Other deductions" value={formatINR(s.deductions, true)} />
              <Row label="Total deductions" value={formatINR(totalDeductions, true)} strong />
            </dl>
          </section>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-strong bg-surface-muted px-4 py-3">
          <span className="text-sm font-medium text-muted-foreground">Net pay</span>
          <span className="text-2xl font-semibold tracking-tight tabular-nums">{formatINR(s.net_salary, true)}</span>
        </div>
        <p className="text-xs text-muted-foreground">This is a system-generated payslip and does not require a signature.</p>
      </div>
    </Modal>
  );
}
