/**
 * Status pills for attendance / leave / employee / document / user / payroll statuses.
 * ONE fixed colour per status (tokens `--status-*`), identical in badges, charts and calendars:
 * present/approved/active/paid = green · absent/rejected/failed/terminated = red · late/pending/on_notice/unpaid = amber
 * half_day/processing = sky · leave = violet · holiday/weekend/inactive/cancelled/archived/not_marked = slate.
 */
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

export type StatusTone = "present" | "absent" | "late" | "half" | "leave" | "neutral";

const TONE: Record<string, StatusTone> = {
  present: "present",
  approved: "present",
  active: "present",
  paid: "present",
  absent: "absent",
  rejected: "absent",
  failed: "absent",
  terminated: "absent",
  late: "late",
  pending: "late",
  on_notice: "late",
  unpaid: "late",
  half_day: "half",
  processing: "half",
  leave: "leave",
  on_leave: "leave",
};

const PILL: Record<StatusTone, string> = {
  present: "bg-status-present-bg text-status-present-fg",
  absent: "bg-status-absent-bg text-status-absent-fg",
  late: "bg-status-late-bg text-status-late-fg",
  half: "bg-status-half-bg text-status-half-fg",
  leave: "bg-status-leave-bg text-status-leave-fg",
  neutral: "bg-status-neutral-bg text-status-neutral-fg",
};

const DOT: Record<StatusTone, string> = {
  present: "bg-status-present",
  absent: "bg-status-absent",
  late: "bg-status-late",
  half: "bg-status-half",
  leave: "bg-status-leave",
  neutral: "bg-status-neutral",
};

export function statusTone(status: string | null | undefined): StatusTone {
  const key = (status ?? "").toLowerCase().replace(/[\s-]+/g, "_");
  return TONE[key] ?? "neutral";
}

export function StatusBadge({ status, label, className }: { status: string | null | undefined; label?: string; className?: string }) {
  const tone = statusTone(status);
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", PILL[tone], className)}>
      <span className={cn("size-1.5 rounded-full", DOT[tone])} aria-hidden="true" />
      {label ?? humanize(status)}
    </span>
  );
}

const ROLE_STYLES: Record<string, string> = {
  admin: "bg-brand text-brand-foreground",
  hr: "bg-status-leave-bg text-status-leave-fg",
  manager: "bg-status-half-bg text-status-half-fg",
  employee: "bg-status-neutral-bg text-status-neutral-fg",
};

export function RoleBadge({ role, className }: { role: string | null | undefined; className?: string }) {
  const key = (role ?? "").toLowerCase();
  const label = key === "hr" ? "HR" : humanize(key);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase",
        ROLE_STYLES[key] ?? "bg-status-neutral-bg text-status-neutral-fg",
        className,
      )}
    >
      {label}
    </span>
  );
}
