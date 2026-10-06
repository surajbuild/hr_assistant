/**
 * Shared chart pieces. Colours are CSS tokens (`var(--status-*)`, `var(--chart-*)`), so charts follow light/dark
 * automatically and use the same status colours as badges and calendars. Recharts is the only chart library.
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Attendance status series — stacking order matters; colours are the fixed per-status tokens. */
export const ATTENDANCE_SERIES = [
  { key: "present", label: "Present", color: "var(--status-present)" },
  { key: "leave", label: "Leave", color: "var(--status-leave)" },
  { key: "late", label: "Late", color: "var(--status-late)" },
  { key: "half_day", label: "Half day", color: "var(--status-half)" },
  { key: "absent", label: "Absent", color: "var(--status-absent)" },
] as const;

export const AXIS_TICK = { fontSize: 12, fill: "var(--muted-foreground)" };
export const GRID_STROKE = "var(--chart-grid)";
export const TOOLTIP_STYLE = {
  contentStyle: {
    borderRadius: 10,
    border: "1px solid var(--border)",
    background: "var(--popover)",
    boxShadow: "var(--shadow-float)",
    fontSize: 12,
    padding: "8px 10px",
  },
  labelStyle: { color: "var(--foreground)", fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: "var(--muted-foreground)", padding: 0 },
  cursor: { fill: "var(--accent)" },
};

export function Legend({ items, className }: { items: { label: string; color: string; value?: ReactNode }[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground", className)}>
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ background: i.color }} aria-hidden="true" />
          {i.label}
          {i.value !== undefined && <span className="font-medium text-foreground tabular-nums">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}

/** Horizontal bar list (single series): label · bar · value. */
export function BarList({
  items,
  max,
  color = "var(--brand)",
  formatValue = (v) => String(v),
}: {
  items: { label: ReactNode; sublabel?: ReactNode; value: number; key: string; color?: string; title?: string }[];
  max?: number;
  color?: string;
  formatValue?: (v: number) => ReactNode;
}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="flex flex-col gap-4">
      {items.map((i) => {
        const pct = Math.max(0, Math.min(100, (i.value / top) * 100));
        return (
          <li key={i.key} title={i.title}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate font-medium text-foreground">
                {i.label}
                {i.sublabel && <span className="ml-1.5 text-xs font-normal text-muted-foreground">{i.sublabel}</span>}
              </span>
              <span className="shrink-0 text-sm font-semibold text-foreground tabular-nums">{formatValue(i.value)}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
              <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: `${pct}%`, background: i.color ?? color }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Tiny trend line from a real series (≥ 2 points). */
export function Sparkline({ values, color = "var(--brand)", className }: { values: number[]; color?: string; className?: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${100 - ((v - min) / span) * 84 - 8}`).join(" ");
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className={className} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/** Circular progress ring (0–100). Children render in the centre. */
export function RingProgress({
  value,
  size = 96,
  stroke = 9,
  color = "var(--brand)",
  children,
  label,
  className,
}: {
  value: number;
  size?: number;
  stroke?: number;
  color?: string;
  children?: ReactNode;
  label?: string;
  className?: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div
      className={cn("relative inline-flex shrink-0 items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={label ?? `${Math.round(v)} percent`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-muted)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v / 100)}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-center">{children}</div>
    </div>
  );
}

/** Segmented donut from real counts. Segments with 0 are skipped. */
export function Donut({
  segments,
  size = 132,
  stroke = 16,
  children,
  className,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
  stroke?: number;
  children?: ReactNode;
  className?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className={cn("relative inline-flex shrink-0 items-center justify-center", className)} style={{ width: size, height: size }} role="img" aria-label={segments.map((s) => `${s.label} ${s.value}`).join(", ")}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-muted)" strokeWidth={stroke} />
        {total > 0 &&
          segments
            .filter((s) => s.value > 0)
            .map((s) => {
              const len = (s.value / total) * c;
              const el = (
                <circle
                  key={s.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={stroke}
                  strokeDasharray={`${Math.max(0, len - 2)} ${c - Math.max(0, len - 2)}`}
                  strokeDashoffset={-offset}
                />
              );
              offset += len;
              return el;
            })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">{children}</div>
    </div>
  );
}
