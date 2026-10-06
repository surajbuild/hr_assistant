/**
 * KPI card: label (12/500) · value (tabular numerals, count-up) · hint · optional trend delta and sparkline.
 * `numeric` + `format` animate the value; otherwise `value` is rendered as-is. Deltas and sparklines must be
 * derived from real data by the caller — never invent them.
 */
import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp } from "@/lib/useCountUp";
import { cn } from "@/lib/utils";
import { Sparkline } from "./charts";

/** Tones map onto the fixed status colours. Legacy names (blue/green/red/amber/violet/navy/slate) still work. */
export type StatTone = "brand" | "present" | "absent" | "late" | "half" | "leave" | "neutral" | "blue" | "green" | "red" | "amber" | "violet" | "navy" | "slate";

const TONES: Record<string, { icon: string; spark: string }> = {
  brand: { icon: "bg-brand-subtle text-brand-subtle-foreground", spark: "var(--brand)" },
  present: { icon: "bg-status-present-bg text-status-present-fg", spark: "var(--status-present)" },
  absent: { icon: "bg-status-absent-bg text-status-absent-fg", spark: "var(--status-absent)" },
  late: { icon: "bg-status-late-bg text-status-late-fg", spark: "var(--status-late)" },
  half: { icon: "bg-status-half-bg text-status-half-fg", spark: "var(--status-half)" },
  leave: { icon: "bg-status-leave-bg text-status-leave-fg", spark: "var(--status-leave)" },
  neutral: { icon: "bg-status-neutral-bg text-status-neutral-fg", spark: "var(--status-neutral)" },
};
const ALIAS: Record<string, string> = { blue: "brand", navy: "brand", green: "present", red: "absent", amber: "late", violet: "leave", slate: "neutral" };

export interface StatDelta {
  /** Signed change (e.g. +1.6). */
  value: number;
  /** Unit appended to the number, e.g. " pts" or "%". */
  suffix?: string;
  /** What it is compared against, e.g. "vs Sep 2026". */
  label?: string;
  /** Whether an increase is good (default) or bad (e.g. absences). */
  upIsGood?: boolean;
}

function Delta({ delta }: { delta: StatDelta }) {
  const flat = Math.abs(delta.value) < 0.05;
  const up = delta.value > 0;
  const good = flat ? null : up === (delta.upIsGood ?? true);
  const Icon = flat ? Minus : up ? ArrowUpRight : ArrowDownRight;
  return (
    <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-xs">
      <span
        className={cn(
          "inline-flex items-center gap-0.5 rounded-full px-1.5 py-px font-medium tabular-nums",
          good === null ? "bg-status-neutral-bg text-status-neutral-fg" : good ? "bg-status-present-bg text-status-present-fg" : "bg-status-absent-bg text-status-absent-fg",
        )}
      >
        <Icon className="size-3" aria-hidden="true" />
        {flat ? "0" : `${up ? "+" : "−"}${Math.abs(delta.value).toLocaleString("en-IN", { maximumFractionDigits: 1 })}`}
        {delta.suffix}
      </span>
      {delta.label && <span className="text-muted-foreground">{delta.label}</span>}
    </p>
  );
}

export function StatCard({
  label,
  value,
  numeric,
  format,
  hint,
  icon,
  tone = "brand",
  delta,
  spark,
  loading,
  className,
}: {
  label: string;
  value?: ReactNode;
  /** Animated count-up target; shown through `format` (default: locale integer). */
  numeric?: number;
  format?: (n: number) => string;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: StatTone;
  delta?: StatDelta;
  /** Real series for a small trend line (needs ≥ 2 points). */
  spark?: number[];
  loading?: boolean;
  className?: string;
}) {
  const t = TONES[ALIAS[tone] ?? tone] ?? TONES.brand!;
  const animated = useCountUp(numeric ?? 0);
  const shown = numeric !== undefined ? (format ? format(animated) : Math.round(animated).toLocaleString("en-IN")) : value;

  if (loading) {
    return (
      <div className={cn("hr-card flex flex-col gap-3 p-4", className)} role="status">
        <span className="sr-only">Loading {label}</span>
        <Skeleton className="h-3 w-1/3" />
        <Skeleton className="h-7 w-1/2" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    );
  }

  return (
    <div className={cn("hr-card card-interactive flex flex-col p-4", className)}>
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-2 min-w-0 text-xs font-medium break-words text-muted-foreground">{label}</p>
        {icon && <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg [&_svg]:size-4", t.icon)}>{icon}</div>}
      </div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <p className="text-[28px] leading-9 font-semibold tracking-tight text-foreground tabular-nums">{shown}</p>
        {spark && spark.length >= 3 && <Sparkline values={spark} color={t.spark} className="mb-1.5 h-6 w-14 shrink-0" />}
      </div>
      {delta && <Delta delta={delta} />}
      {hint && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
