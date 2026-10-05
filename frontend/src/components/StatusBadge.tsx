/** Colored status pills for attendance / leave / employee / document / user statuses. */
import { humanize } from "@/lib/format";
import { cn } from "@/lib/utils";

const STYLES: Record<string, string> = {
  // attendance
  present: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  absent: "bg-red-50 text-red-700 ring-red-600/20",
  late: "bg-amber-50 text-amber-700 ring-amber-600/20",
  half_day: "bg-blue-50 text-blue-700 ring-blue-600/20",
  leave: "bg-violet-50 text-violet-700 ring-violet-600/20",
  on_leave: "bg-violet-50 text-violet-700 ring-violet-600/20",
  holiday: "bg-slate-100 text-slate-600 ring-slate-500/20",
  weekend: "bg-slate-100 text-slate-600 ring-slate-500/20",
  not_marked: "bg-slate-50 text-slate-500 ring-slate-400/30",
  // leave
  pending: "bg-amber-50 text-amber-700 ring-amber-600/20",
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  rejected: "bg-red-50 text-red-700 ring-red-600/20",
  cancelled: "bg-slate-100 text-slate-600 ring-slate-500/20",
  // employee / user
  active: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  inactive: "bg-slate-100 text-slate-600 ring-slate-500/20",
  on_notice: "bg-amber-50 text-amber-700 ring-amber-600/20",
  terminated: "bg-red-50 text-red-700 ring-red-600/20",
  // documents
  processing: "bg-blue-50 text-blue-700 ring-blue-600/20",
  failed: "bg-red-50 text-red-700 ring-red-600/20",
  archived: "bg-slate-100 text-slate-600 ring-slate-500/20",
  // payroll
  paid: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  unpaid: "bg-amber-50 text-amber-700 ring-amber-600/20",
};

const DOTS: Record<string, string> = {
  present: "bg-emerald-500",
  approved: "bg-emerald-500",
  active: "bg-emerald-500",
  paid: "bg-emerald-500",
  absent: "bg-red-500",
  rejected: "bg-red-500",
  failed: "bg-red-500",
  terminated: "bg-red-500",
  late: "bg-amber-500",
  pending: "bg-amber-500",
  on_notice: "bg-amber-500",
  unpaid: "bg-amber-500",
  half_day: "bg-blue-500",
  processing: "bg-blue-500",
  leave: "bg-violet-500",
  on_leave: "bg-violet-500",
};

export function StatusBadge({ status, label, className }: { status: string | null | undefined; label?: string; className?: string }) {
  const key = (status ?? "").toLowerCase().replace(/[\s-]+/g, "_");
  const style = STYLES[key] ?? "bg-slate-100 text-slate-600 ring-slate-500/20";
  const dot = DOTS[key] ?? "bg-slate-400";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        style,
        className,
      )}
    >
      <span className={cn("size-1.5 rounded-full", dot)} aria-hidden="true" />
      {label ?? humanize(status)}
    </span>
  );
}

const ROLE_STYLES: Record<string, string> = {
  admin: "bg-navy text-white",
  hr: "bg-violet-100 text-violet-800",
  manager: "bg-blue-100 text-blue-800",
  employee: "bg-slate-100 text-slate-700",
};

export function RoleBadge({ role, className }: { role: string | null | undefined; className?: string }) {
  const key = (role ?? "").toLowerCase();
  const label = key === "hr" ? "HR" : humanize(key);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        ROLE_STYLES[key] ?? "bg-slate-100 text-slate-700",
        className,
      )}
    >
      {label}
    </span>
  );
}
