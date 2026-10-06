/**
 * Month heat-map: one cell per calendar day coloured by that day's attendance status.
 * Colours are the fixed per-status tokens (identical to StatusBadge and the charts). Built from REAL records only;
 * days without a record render as an empty outline. Used on the dashboard now and the Attendance page in Part 2.
 */
import { useMemo } from "react";
import type { AttendanceRecord } from "@/lib/types";
import { cn } from "@/lib/utils";
import { formatDate, humanize } from "@/lib/format";
import { Legend } from "./charts";

type Kind = "present" | "late" | "half_day" | "leave" | "absent" | "off" | "none";

const KIND_COLOR: Record<Exclude<Kind, "none">, string> = {
  present: "var(--status-present)",
  late: "var(--status-late)",
  half_day: "var(--status-half)",
  leave: "var(--status-leave)",
  absent: "var(--status-absent)",
  off: "var(--status-neutral)",
};

function kindOf(r: AttendanceRecord | undefined): Kind {
  if (!r) return "none";
  if (r.status === "present") return r.late_minutes > 0 ? "late" : "present";
  if (r.status === "half_day") return "half_day";
  if (r.status === "leave") return "leave";
  if (r.status === "absent") return "absent";
  return "off"; // weekend / holiday
}

export function AttendanceHeatmap({ records, year, month, className }: { records: AttendanceRecord[]; year: number; month: number; className?: string }) {
  const { cells, offset } = useMemo(() => {
    const byDate = new Map(records.map((r) => [r.attendance_date, r]));
    const days = new Date(year, month, 0).getDate();
    const first = new Date(year, month - 1, 1).getDay(); // 0 = Sunday
    const offset = (first + 6) % 7; // Monday-first
    const mm = String(month).padStart(2, "0");
    const cells = Array.from({ length: days }, (_, i) => {
      const iso = `${year}-${mm}-${String(i + 1).padStart(2, "0")}`;
      const rec = byDate.get(iso);
      return { day: i + 1, iso, rec, kind: kindOf(rec) };
    });
    return { cells, offset };
  }, [records, year, month]);

  return (
    <div className={className}>
      <div className="grid grid-cols-7 gap-1.5 text-center text-[11px] font-medium text-muted-foreground" aria-hidden="true">
        {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => (
          <span key={i}>{d}</span>
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-7 gap-1.5" role="list" aria-label="Attendance by day">
        {Array.from({ length: offset }, (_, i) => (
          <span key={`o${i}`} aria-hidden="true" />
        ))}
        {cells.map((c) => {
          const label = `${formatDate(c.iso)}: ${c.kind === "none" ? "no record" : c.kind === "off" ? humanize(c.rec?.status) : c.kind === "late" ? "Present (late)" : humanize(c.kind)}`;
          return (
            <span
              key={c.iso}
              role="listitem"
              title={label}
              aria-label={label}
              className={cn(
                "flex aspect-square items-center justify-center rounded-md text-[11px] font-medium tabular-nums transition-transform duration-150 hover:scale-110",
                c.kind === "none" ? "border border-dashed border-border text-muted-foreground" : c.kind === "off" ? "text-status-neutral-fg" : "text-brand-foreground",
              )}
              style={
                c.kind === "none"
                  ? undefined
                  : c.kind === "off"
                    ? { background: "var(--status-neutral-bg)" }
                    : { background: KIND_COLOR[c.kind], color: c.kind === "late" ? "var(--on-late)" : undefined }
              }
            >
              {c.day}
            </span>
          );
        })}
      </div>
      <Legend
        className="mt-3"
        items={[
          { label: "Present", color: KIND_COLOR.present },
          { label: "Late", color: KIND_COLOR.late },
          { label: "Half day", color: KIND_COLOR.half_day },
          { label: "Leave", color: KIND_COLOR.leave },
          { label: "Absent", color: KIND_COLOR.absent },
          { label: "Weekend / holiday", color: "var(--status-neutral-bg)" },
        ]}
      />
    </div>
  );
}
