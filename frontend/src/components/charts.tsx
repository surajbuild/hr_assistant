/** Shared chart pieces (palette validated for CVD separation in this stack order). */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Attendance status colors — stacking order matters (validated adjacent pairs). */
export const ATTENDANCE_SERIES = [
  { key: "present", label: "Present", color: "#059669" },
  { key: "leave", label: "Leave", color: "#7c3aed" },
  { key: "late", label: "Late", color: "#d97706" },
  { key: "half_day", label: "Half day", color: "#2563eb" },
  { key: "absent", label: "Absent", color: "#dc2626" },
] as const;

export const AXIS_TICK = { fontSize: 12, fill: "#64748b" };
export const GRID_STROKE = "#e2e8f0";
export const TOOLTIP_STYLE = {
  contentStyle: {
    borderRadius: 8,
    border: "1px solid #e2e8f0",
    boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
    fontSize: 12,
    padding: "8px 10px",
  },
  labelStyle: { color: "#0f172a", fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: "#334155", padding: 0 },
  cursor: { fill: "rgba(37,99,235,0.06)" },
};

export function Legend({ items, className }: { items: { label: string; color: string }[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted", className)}>
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: i.color }} aria-hidden="true" />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/** Horizontal bar list (single series): label · bar · value. */
export function BarList({
  items,
  max,
  color = "#2563eb",
  formatValue = (v) => String(v),
}: {
  items: { label: ReactNode; sublabel?: ReactNode; value: number; key: string; color?: string; title?: string }[];
  max?: number;
  color?: string;
  formatValue?: (v: number) => ReactNode;
}) {
  const top = max ?? Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="flex flex-col gap-3.5">
      {items.map((i) => {
        const pct = Math.max(0, Math.min(100, (i.value / top) * 100));
        return (
          <li key={i.key} title={i.title}>
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate font-medium text-ink">
                {i.label}
                {i.sublabel && <span className="ml-1.5 text-xs font-normal text-ink-muted">{i.sublabel}</span>}
              </span>
              <span className="shrink-0 text-sm font-semibold tabular-nums text-ink">{formatValue(i.value)}</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{ width: `${pct}%`, background: i.color ?? color }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
