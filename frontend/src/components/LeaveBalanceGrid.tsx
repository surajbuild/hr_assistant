/** Leave balance cards: a progress ring (used + pending of entitled) with remaining days in the centre. */
import { formatNumber, humanize } from "@/lib/format";
import type { LeaveBalance } from "@/lib/types";
import { RingProgress } from "./charts";

/** One fixed colour per leave type (chart tokens), used identically everywhere leave types are charted. */
const TYPE_COLOR: Record<string, string> = {
  casual: "var(--chart-1)",
  sick: "var(--chart-5)",
  earned: "var(--chart-4)",
  unpaid: "var(--status-neutral)",
  maternity: "var(--chart-3)",
  paternity: "var(--chart-2)",
};

export function leaveTypeColor(type: string): string {
  return TYPE_COLOR[type.toLowerCase()] ?? "var(--chart-1)";
}

export function LeaveBalanceGrid({ balances }: { balances: LeaveBalance[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {balances.map((b) => {
        const pct = b.entitled > 0 ? Math.min(100, ((b.used + b.pending) / b.entitled) * 100) : 0;
        return (
          <div key={b.leave_type} className="flex items-center gap-3.5 rounded-xl border border-border p-3.5">
            <RingProgress value={pct} size={56} stroke={6} color={leaveTypeColor(b.leave_type)} label={`${humanize(b.leave_type)}: ${formatNumber(b.remaining, 1)} of ${formatNumber(b.entitled, 1)} days left`}>
              <span className="text-[13px] font-semibold text-foreground tabular-nums">{formatNumber(b.remaining, 1)}</span>
            </RingProgress>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{humanize(b.leave_type)}</p>
              <p className="text-xs text-muted-foreground tabular-nums">
                {formatNumber(b.remaining, 1)} of {formatNumber(b.entitled, 1)} left
              </p>
              <p className="text-[11px] text-muted-foreground tabular-nums">
                {formatNumber(b.used, 1)} used{b.pending > 0 ? ` · ${formatNumber(b.pending, 1)} pending` : ""}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
