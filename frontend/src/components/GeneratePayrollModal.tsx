/**
 * "Generate payroll" dialog (HR/Admin) — POST /api/salary/generate {month, year}.
 * Explains the rules (PROJECT_DECISIONS D-021), warns when the month is still running (provisional), then shows what
 * was created / updated / skipped. Paid rows are locked server-side (D-036) and are reported as skipped.
 */
import { useState } from "react";
import { Calculator, Lock } from "lucide-react";
import { Modal } from "@/components/Modal";
import { Notice } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatINR, formatNumber, monthLabel } from "@/lib/format";
import type { PayrollGenerateResult } from "@/lib/types";

function isCurrentMonth(month: number, year: number): boolean {
  const now = new Date();
  return year === now.getFullYear() && month === now.getMonth() + 1;
}

function ResultTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface-muted p-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold text-foreground tabular-nums">{value}</p>
    </div>
  );
}

export function GeneratePayrollModal({
  open,
  month,
  year,
  onClose,
  onGenerated,
}: {
  open: boolean;
  month: number;
  year: number;
  onClose: () => void;
  onGenerated: () => void;
}) {
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PayrollGenerateResult | null>(null);
  const period = monthLabel(month, year);

  function close() {
    if (running) return;
    setResult(null);
    setError(null);
    onClose();
  }

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await api.post<PayrollGenerateResult>("/salary/generate", { month, year });
      setResult(res);
      const skipped = res.skipped.length ? `, ${res.skipped.length} skipped` : "";
      toast.success(`Payroll for ${period}: ${res.created} created, ${res.updated} updated${skipped}.`);
      onGenerated();
    } catch (err) {
      const msg = errorMessage(err, "Failed to generate payroll.");
      setError(msg);
      toast.error(msg);
    } finally {
      setRunning(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title={`Generate payroll · ${period}`}
      description="Salary rows are calculated by the server from each employee's monthly gross salary, attendance and leave."
      footer={
        result ? (
          <Button onClick={close}>Done</Button>
        ) : (
          <>
            <Button variant="outline" onClick={close} disabled={running}>
              Cancel
            </Button>
            <Button onClick={run} loading={running}>
              {!running && <Calculator />} {running ? "Generating..." : "Generate"}
            </Button>
          </>
        )
      }
    >
      {!result && (
        <div className="flex flex-col gap-4 text-sm text-foreground">
          {isCurrentMonth(month, year) && (
            <Notice tone="warning">{period} is not over yet — the figures will be provisional and change as attendance is recorded.</Notice>
          )}
          <div>
            <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">How it is calculated</p>
            <ul className="flex list-disc flex-col gap-1 pl-5 text-muted-foreground">
              <li>Working days = Mon–Fri minus company holidays.</li>
              <li>Loss of pay = absent days + ½ × half days + approved unpaid leave, at gross ÷ working days per day.</li>
              <li>PF = 12% of earned basic (basic = 35% of gross).</li>
              <li>Overtime = OT hours × (gross ÷ (working days × 8)) × 1.5.</li>
            </ul>
          </div>
          <p className="flex items-start gap-2 rounded-lg border border-border bg-surface-muted px-3 py-2.5 text-muted-foreground">
            <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            Re-running updates unpaid rows only; rows already marked paid are locked and skipped.
          </p>
          {error && (
            <Notice tone="danger">
              <span role="alert">{error}</span>
            </Notice>
          )}
        </div>
      )}
      {result && (
        <div className="flex flex-col gap-4 text-sm">
          {result.provisional && (
            <Notice tone="warning">{period} is not over yet — these figures are provisional and will change as attendance is recorded.</Notice>
          )}
          <div className="grid grid-cols-3 gap-3">
            <ResultTile label="Created" value={result.created} />
            <ResultTile label="Updated" value={result.updated} />
            <ResultTile label="Skipped" value={result.skipped.length} />
          </div>
          <p className="text-xs text-muted-foreground">
            {formatNumber(result.working_days)} working days in {period}.
          </p>
          {result.items.length > 0 && (
            <div className="relative max-h-64 overflow-auto rounded-lg border border-border">
              <table className="w-full min-w-max text-xs">
                <thead className="sticky top-0 bg-surface-muted text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left font-medium">Employee</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">LOP days</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Overtime</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Net pay</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((i) => (
                    <tr key={i.employee_id} className="border-t border-border">
                      <td className="px-3 py-2 text-foreground">{i.employee_name}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatNumber(i.lop_days, 1)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{formatINR(i.overtime_amount)}</td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums">{formatINR(i.net_salary)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.skipped.length > 0 && (
            <div>
              <p className="mb-1 font-medium text-foreground">Skipped</p>
              <ul className="flex flex-col gap-1 text-muted-foreground">
                {result.skipped.map((s) => (
                  <li key={s.employee_id}>
                    <span className="text-foreground">{s.employee_name}</span> — {s.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
