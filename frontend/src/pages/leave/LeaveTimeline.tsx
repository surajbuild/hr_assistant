/**
 * My leaves as a timeline (GET /leaves/me): upcoming & ongoing first, then history; status filter; cancel pending
 * requests (POST /leaves/{id}/cancel, with confirm). Working days use the holiday calendar (same rule as the backend).
 */
import { useMemo, useState } from "react";
import { CalendarDays, CalendarPlus, History } from "lucide-react";
import { leaveTypeColor } from "@/components/LeaveBalanceGrid";
import { ConfirmDialog } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatDate, humanize, toISODate } from "@/lib/format";
import type { Leave } from "@/lib/types";
import type { FetchState } from "@/lib/useFetch";
import { cn } from "@/lib/utils";
import { useHolidays, workingDaysBetween } from "./holidays";

type Filter = "all" | "pending" | "approved" | "rejected" | "cancelled";

const DOT: Record<string, string> = {
  pending: "bg-status-late",
  approved: "bg-status-present",
  rejected: "bg-status-absent",
  cancelled: "bg-status-neutral",
};

/** "05 Oct 2026" → "Oct" (same abbreviations as formatDate). */
const MONTH = (iso: string) => formatDate(iso).slice(3, 6);

export function LeaveTimeline({ state, onChanged, onApply }: { state: FetchState<Leave[]>; onChanged: () => void; onApply: () => void }) {
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>("all");
  const [cancelling, setCancelling] = useState<Leave | null>(null);
  const [busy, setBusy] = useState(false);
  const today = toISODate(new Date());

  const all = state.data ?? [];
  const years = useMemo(() => [...new Set(all.flatMap((l) => [Number(l.from_date.slice(0, 4)), Number(l.to_date.slice(0, 4))]))], [all]);
  const holidays = useHolidays(years);
  const rows = all.filter((l) => filter === "all" || l.status === filter);
  const upcoming = rows.filter((l) => l.to_date >= today).sort((a, b) => a.from_date.localeCompare(b.from_date));
  const past = rows.filter((l) => l.to_date < today).sort((a, b) => b.from_date.localeCompare(a.from_date));
  const counts = all.reduce<Record<string, number>>((acc, l) => ((acc[l.status] = (acc[l.status] ?? 0) + 1), acc), {});

  async function confirmCancel() {
    if (!cancelling) return;
    setBusy(true);
    try {
      await api.post(`/leaves/${cancelling.id}/cancel`);
      toast.success("Leave request cancelled.");
      setCancelling(null);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to cancel the leave request."));
      setCancelling(null);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  function item(l: Leave) {
    const days = holidays.loading ? null : workingDaysBetween(l.from_date, l.to_date, holidays.byDate).days;
    const ongoing = l.from_date <= today && l.to_date >= today && l.status === "approved";
    return (
      <li key={l.id} className="group relative flex gap-4 pb-5 last:pb-0">
        {/* rail */}
        <span className="absolute top-3 bottom-0 left-[1.6rem] w-px bg-border group-last:hidden" aria-hidden="true" />
        <div className="relative z-10 flex w-[3.25rem] shrink-0 flex-col self-start items-center rounded-lg border border-border bg-surface py-1.5 text-center">
          <span className="text-[11px] font-medium text-muted-foreground uppercase">{MONTH(l.from_date)}</span>
          <span className="text-lg leading-6 font-semibold text-foreground tabular-nums">{l.from_date.slice(8, 10)}</span>
          <span className={cn("mt-0.5 size-1.5 rounded-full", DOT[l.status] ?? "bg-status-neutral")} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 rounded-xl border border-border bg-surface px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <span className="size-2 shrink-0 rounded-full" style={{ background: leaveTypeColor(l.leave_type) }} aria-hidden="true" />
                {humanize(l.leave_type)} leave
                {ongoing && <span className="rounded-full bg-brand-subtle px-2 py-px text-[11px] font-medium text-brand-subtle-foreground">On leave now</span>}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">
                {formatDate(l.from_date)}
                {l.to_date !== l.from_date && ` – ${formatDate(l.to_date)}`}
                {days !== null && ` · ${days} working day${days === 1 ? "" : "s"}`}
              </p>
            </div>
            <StatusBadge status={l.status} />
          </div>
          {l.reason && <p className="mt-2 text-sm text-foreground">{l.reason}</p>}
          {l.status === "pending" && (
            <div className="mt-2 flex justify-end">
              <Button variant="ghost" size="sm" className="h-7 text-status-absent-fg hover:bg-status-absent-bg" onClick={() => setCancelling(l)}>
                Cancel request
              </Button>
            </div>
          )}
        </div>
      </li>
    );
  }

  return (
    <Panel
      title="My leave requests"
      subtitle={state.loading && !state.data ? undefined : `${all.length} request${all.length === 1 ? "" : "s"}${counts.pending ? ` · ${counts.pending} pending` : ""}`}
      icon={<CalendarDays />}
    >
      {all.length > 0 && (
        <Segmented<Filter>
          label="Status filter"
          value={filter}
          onChange={setFilter}
          className="mb-4"
          options={[
            { value: "all", label: "All" },
            { value: "pending", label: "Pending" },
            { value: "approved", label: "Approved" },
            { value: "rejected", label: "Rejected" },
            { value: "cancelled", label: "Cancelled" },
          ]}
        />
      )}
      <AsyncContent loading={state.loading && !state.data} error={state.error} onRetry={state.reload} loadingLabel="Loading your leave requests...">
        {rows.length === 0 ? (
          <EmptyState
            icon={<CalendarDays />}
            title={all.length === 0 ? "No leave requests yet" : `No ${filter} requests`}
            description={all.length === 0 ? "Plan time off — your request goes to your manager or HR." : "Try another status."}
            action={
              all.length === 0 ? (
                <Button size="sm" onClick={onApply}>
                  <CalendarPlus /> Apply for leave
                </Button>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setFilter("all")}>
                  Show all
                </Button>
              )
            }
          />
        ) : (
          <div className="flex flex-col gap-6">
            {upcoming.length > 0 && (
              <section aria-labelledby="lv-upcoming">
                <h3 id="lv-upcoming" className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                  Upcoming & ongoing
                </h3>
                <ol className="flex flex-col">{upcoming.map(item)}</ol>
              </section>
            )}
            {past.length > 0 && (
              <section aria-labelledby="lv-past">
                <h3 id="lv-past" className="mb-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                  <History className="size-3.5" aria-hidden="true" /> History
                </h3>
                <ol className="flex flex-col">{past.map(item)}</ol>
              </section>
            )}
          </div>
        )}
      </AsyncContent>
      <ConfirmDialog
        open={!!cancelling}
        title="Cancel leave request?"
        message={
          cancelling && (
            <>
              Your {humanize(cancelling.leave_type).toLowerCase()} leave {formatDate(cancelling.from_date)}
              {cancelling.to_date !== cancelling.from_date ? ` – ${formatDate(cancelling.to_date)}` : ""} will be cancelled.
            </>
          )
        }
        confirmLabel="Yes, cancel leave"
        busy={busy}
        onConfirm={confirmCancel}
        onCancel={() => setCancelling(null)}
      />
    </Panel>
  );
}
