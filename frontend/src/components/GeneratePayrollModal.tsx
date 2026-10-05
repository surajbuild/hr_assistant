/**
 * "Generate payroll" dialog (HR/Admin) — POST /api/salary/generate {month, year}.
 * Explains the rules (PROJECT_DECISIONS D-021), confirms, then shows what was created / updated / skipped.
 */
import { useState } from "react";
import { Calculator } from "lucide-react";
import { Modal } from "@/components/Modal";
import { Notice, Spinner } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatINR, monthLabel } from "@/lib/format";
import type { PayrollGenerateResult } from "@/lib/types";

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

  function close() {
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
      toast.success(`Payroll for ${monthLabel(month, year)}: ${res.created} created, ${res.updated} updated.`);
      onGenerated();
    } catch (err) {
      setError(errorMessage(err, "Failed to generate payroll."));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title={`Generate payroll · ${monthLabel(month, year)}`}
      description="Salary rows are calculated by the server from each employee's monthly gross salary, attendance and leave."
      footer={
        result ? (
          <Button onClick={close}>Done</Button>
        ) : (
          <>
            <Button variant="outline" onClick={close} disabled={running}>
              Cancel
            </Button>
            <Button onClick={run} disabled={running}>
              {running ? <Spinner /> : <Calculator className="size-4" />} Generate
            </Button>
          </>
        )
      }
    >
      {!result && (
        <div className="space-y-3 text-sm text-ink">
          <ul className="list-disc space-y-1 pl-5 text-ink-muted">
            <li>Working days = Mon–Fri minus company holidays.</li>
            <li>Loss of pay = absent days + ½ × half days + approved unpaid leave, at gross ÷ working days per day.</li>
            <li>PF = 12% of earned basic (basic = 35% of gross).</li>
            <li>Overtime = OT hours × (gross ÷ (working days × 8)) × 1.5.</li>
            <li>Re-running updates unpaid rows only; rows already marked paid are locked.</li>
          </ul>
          {error && <Notice tone="danger">{error}</Notice>}
        </div>
      )}
      {result && (
        <div className="space-y-4 text-sm">
          {result.provisional && (
            <Notice tone="warning">
              {monthLabel(month, year)} is not over yet — these figures are provisional and will change as attendance is recorded.
            </Notice>
          )}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs text-ink-muted">Created</p>
              <p className="text-xl font-bold text-ink">{result.created}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs text-ink-muted">Updated</p>
              <p className="text-xl font-bold text-ink">{result.updated}</p>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs text-ink-muted">Skipped</p>
              <p className="text-xl font-bold text-ink">{result.skipped.length}</p>
            </div>
          </div>
          {result.items.length > 0 && (
            <div className="relative max-h-64 overflow-auto rounded-lg border border-border">
              <table className="w-full min-w-max text-xs">
                <thead className="bg-slate-50 text-ink-muted">
                  <tr>
                    <th className="px-3 py-2 text-left">Employee</th>
                    <th className="px-3 py-2 text-right">LOP days</th>
                    <th className="px-3 py-2 text-right">OT</th>
                    <th className="px-3 py-2 text-right">Net pay</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((i) => (
                    <tr key={i.employee_id} className="border-t border-border">
                      <td className="px-3 py-2">{i.employee_name}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{i.lop_days}</td>
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
              <p className="mb-1 font-medium">Skipped</p>
              <ul className="space-y-1 text-ink-muted">
                {result.skipped.map((s) => (
                  <li key={s.employee_id}>
                    <span className="text-ink">{s.employee_name}</span> — {s.reason}
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
