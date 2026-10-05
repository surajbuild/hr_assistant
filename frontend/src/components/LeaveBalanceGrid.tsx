/** Leave balance cards: remaining / entitled with usage bar. */
import { formatNumber, humanize } from "@/lib/format";
import type { LeaveBalance } from "@/lib/types";

export function LeaveBalanceGrid({ balances }: { balances: LeaveBalance[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {balances.map((b) => {
        const pct = b.entitled > 0 ? Math.min(100, ((b.used + b.pending) / b.entitled) * 100) : 0;
        return (
          <div key={b.leave_type} className="rounded-lg border border-border p-3">
            <p className="text-xs font-medium text-ink-muted">{humanize(b.leave_type)}</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-ink">
              {formatNumber(b.remaining, 1)}
              <span className="text-sm font-normal text-ink-muted"> / {formatNumber(b.entitled, 1)}</span>
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-1.5 text-[11px] text-ink-muted">
              {formatNumber(b.used, 1)} used{b.pending > 0 ? ` · ${formatNumber(b.pending, 1)} pending` : ""}
            </p>
          </div>
        );
      })}
    </div>
  );
}
