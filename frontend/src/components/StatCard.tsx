import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type StatTone = "blue" | "green" | "red" | "amber" | "violet" | "navy" | "slate";

const TONES: Record<StatTone, { icon: string; value: string }> = {
  blue: { icon: "bg-blue-50 text-blue-600", value: "text-ink" },
  green: { icon: "bg-emerald-50 text-emerald-600", value: "text-ink" },
  red: { icon: "bg-red-50 text-red-600", value: "text-ink" },
  amber: { icon: "bg-amber-50 text-amber-600", value: "text-ink" },
  violet: { icon: "bg-violet-50 text-violet-600", value: "text-ink" },
  navy: { icon: "bg-slate-100 text-navy", value: "text-ink" },
  slate: { icon: "bg-slate-100 text-slate-600", value: "text-ink" },
};

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "blue",
  className,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: StatTone;
  className?: string;
}) {
  const t = TONES[tone];
  return (
    <div className={cn("hr-card flex items-start justify-between gap-3 p-4", className)}>
      <div className="min-w-0">
        <p className="line-clamp-2 text-xs font-medium uppercase tracking-wide break-words text-ink-muted">{label}</p>
        <p className={cn("mt-1.5 text-2xl font-bold tabular-nums leading-tight", t.value)}>{value}</p>
        {hint && <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{hint}</p>}
      </div>
      {icon && (
        <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg [&_svg]:size-5", t.icon)}>{icon}</div>
      )}
    </div>
  );
}
