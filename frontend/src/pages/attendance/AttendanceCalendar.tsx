/**
 * Interactive month calendar for "My attendance": one button per day, tinted by that day's REAL attendance status
 * (same per-status tokens as StatusBadge / heat-map), holidays from GET /holidays, a marker for pending correction
 * requests. Keyboard: roving focus, ←/→ ±1 day, ↑/↓ ±1 week, Home/End = first/last day; Enter/Space selects.
 */
import { useMemo, useRef, type KeyboardEvent } from "react";
import { Legend } from "@/components/charts";
import { formatDate, formatMinutes, formatTime, humanize } from "@/lib/format";
import type { AttendanceCorrection, AttendanceRecord, Holiday } from "@/lib/types";
import { cn } from "@/lib/utils";

export type DayKind = "present" | "late" | "half_day" | "leave" | "absent" | "off" | "holiday" | "weekend" | "none";

export function dayKind(rec: AttendanceRecord | undefined, holiday: Holiday | undefined, weekend: boolean): DayKind {
  if (rec) {
    if (rec.status === "present") return rec.late_minutes > 0 ? "late" : "present";
    if (rec.status === "half_day") return "half_day";
    if (rec.status === "leave") return "leave";
    if (rec.status === "absent") return "absent";
    if (rec.status === "holiday") return "holiday";
    return "weekend";
  }
  if (holiday) return "holiday";
  if (weekend) return "weekend";
  return "none";
}

export function kindLabel(kind: DayKind): string {
  if (kind === "late") return "Present (late)";
  if (kind === "none") return "No record";
  return humanize(kind);
}

const CELL: Record<DayKind, string> = {
  present: "bg-status-present-bg text-status-present-fg",
  late: "bg-status-late-bg text-status-late-fg",
  half_day: "bg-status-half-bg text-status-half-fg",
  leave: "bg-status-leave-bg text-status-leave-fg",
  absent: "bg-status-absent-bg text-status-absent-fg",
  holiday: "bg-status-neutral-bg text-status-neutral-fg",
  weekend: "bg-surface-muted text-muted-foreground",
  off: "bg-status-neutral-bg text-status-neutral-fg",
  none: "border border-dashed border-border text-muted-foreground",
};

const BAR: Partial<Record<DayKind, string>> = {
  present: "bg-status-present",
  late: "bg-status-late",
  half_day: "bg-status-half",
  leave: "bg-status-leave",
  absent: "bg-status-absent",
  holiday: "bg-status-neutral",
};

export function AttendanceCalendar({
  month,
  records,
  holidays,
  pending,
  selected,
  onSelect,
  today,
}: {
  /** "YYYY-MM" */
  month: string;
  records: Map<string, AttendanceRecord>;
  holidays: Map<string, Holiday>;
  pending: Map<string, AttendanceCorrection>;
  selected: string | null;
  onSelect: (iso: string) => void;
  today: string;
}) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [y, m] = month.split("-").map(Number) as [number, number];

  const { cells, offset } = useMemo(() => {
    const days = new Date(y, m, 0).getDate();
    const first = new Date(y, m - 1, 1).getDay();
    const offset = (first + 6) % 7; // Monday first
    const cells = Array.from({ length: days }, (_, i) => {
      const iso = `${month}-${String(i + 1).padStart(2, "0")}`;
      const dow = new Date(y, m - 1, i + 1).getDay();
      const rec = records.get(iso);
      const holiday = holidays.get(iso);
      return { day: i + 1, iso, rec, holiday, kind: dayKind(rec, holiday, dow === 0 || dow === 6), future: iso > today };
    });
    return { cells, offset };
  }, [y, m, month, records, holidays, today]);

  const focusDay = selected && selected.startsWith(month) ? selected : (cells.find((c) => c.iso === today)?.iso ?? cells[0]!.iso);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const idx = cells.findIndex((c) => c.iso === focusDay);
    let next = -1;
    if (e.key === "ArrowRight") next = idx + 1;
    else if (e.key === "ArrowLeft") next = idx - 1;
    else if (e.key === "ArrowDown") next = idx + 7;
    else if (e.key === "ArrowUp") next = idx - 7;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = cells.length - 1;
    else return;
    e.preventDefault();
    next = Math.max(0, Math.min(cells.length - 1, next));
    const target = cells[next];
    if (!target) return;
    onSelect(target.iso);
    requestAnimationFrame(() => gridRef.current?.querySelector<HTMLElement>(`[data-iso="${target.iso}"]`)?.focus());
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-medium text-muted-foreground sm:gap-1.5" aria-hidden="true">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <span key={d}>
            <span className="sm:hidden">{d[0]}</span>
            <span className="hidden sm:inline">{d}</span>
          </span>
        ))}
      </div>
      <div ref={gridRef} className="mt-1.5 grid grid-cols-7 gap-1 sm:gap-1.5" role="group" aria-label={`Attendance calendar, use arrow keys to move between days`} onKeyDown={onKeyDown}>
        {Array.from({ length: offset }, (_, i) => (
          <span key={`o${i}`} aria-hidden="true" />
        ))}
        {cells.map((c) => {
          const isSel = c.iso === selected;
          const pend = pending.get(c.iso);
          const parts = [formatDate(c.iso), c.holiday ? `${c.holiday.name} (holiday)` : null, c.future && !c.rec ? null : kindLabel(c.kind)];
          if (c.rec?.in_time) parts.push(`${formatTime(c.rec.in_time)} to ${formatTime(c.rec.out_time)}`);
          if (pend) parts.push("correction pending");
          if (c.iso === today) parts.push("today");
          return (
            <button
              key={c.iso}
              type="button"
              data-iso={c.iso}
              tabIndex={c.iso === focusDay ? 0 : -1}
              aria-pressed={isSel}
              aria-label={parts.filter(Boolean).join(", ")}
              onClick={() => onSelect(c.iso)}
              className={cn(
                "group relative flex min-h-11 flex-col items-start justify-between overflow-hidden rounded-lg p-1.5 text-left transition-[box-shadow,transform] duration-150 outline-none sm:min-h-16 sm:p-2 lg:min-h-[4.5rem]",
                c.future && !c.rec ? "text-muted-foreground" : CELL[c.kind],
                c.future && !c.rec && !c.holiday && "border border-transparent",
                c.future && !c.rec && c.holiday && CELL.holiday,
                isSel ? "ring-2 ring-brand ring-offset-1 ring-offset-surface" : "hover:ring-1 hover:ring-border-strong",
                "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface",
              )}
            >
              <span className="flex w-full items-center justify-between gap-1">
                <span
                  className={cn(
                    "text-xs font-semibold tabular-nums sm:text-[13px]",
                    c.iso === today && "flex size-5 items-center justify-center rounded-full bg-brand text-brand-foreground sm:size-6",
                  )}
                >
                  {c.day}
                </span>
                {pend && <span className="size-2 shrink-0 rounded-full bg-status-late ring-2 ring-surface" aria-hidden="true" />}
              </span>
              {c.rec?.in_time ? (
                <span className="hidden w-full truncate text-[11px] leading-tight tabular-nums sm:block">
                  {formatTime(c.rec.in_time)}–{c.rec.out_time ? formatTime(c.rec.out_time) : "…"}
                </span>
              ) : c.holiday ? (
                <span className="hidden w-full truncate text-[11px] leading-tight sm:block">{c.holiday.name}</span>
              ) : c.rec ? (
                <span className="hidden w-full truncate text-[11px] leading-tight sm:block">{kindLabel(c.kind)}</span>
              ) : null}
              {BAR[c.kind] && !(c.future && !c.rec) && <span className={cn("absolute inset-x-0 bottom-0 h-0.5 sm:hidden", BAR[c.kind])} aria-hidden="true" />}
              {c.rec && c.rec.working_minutes ? <span className="sr-only">{formatMinutes(c.rec.working_minutes)} worked</span> : null}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        <Legend
          items={[
            { label: "Present", color: "var(--status-present)" },
            { label: "Late", color: "var(--status-late)" },
            { label: "Half day", color: "var(--status-half)" },
            { label: "Leave", color: "var(--status-leave)" },
            { label: "Absent", color: "var(--status-absent)" },
            { label: "Holiday", color: "var(--status-neutral)" },
          ]}
        />
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="flex size-4 items-center justify-center rounded border border-border" aria-hidden="true">
            <span className="size-1.5 rounded-full bg-status-late" />
          </span>
          Correction pending
        </span>
      </div>
    </div>
  );
}
