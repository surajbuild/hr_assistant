/** Own correction requests (GET /attendance/corrections/me) with status, reviewer note and cancel for pending ones. */
import { useState } from "react";
import { FilePenLine, History } from "lucide-react";
import { ConfirmDialog } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatDateTime, formatTime } from "@/lib/format";
import type { AttendanceCorrection } from "@/lib/types";
import type { FetchState } from "@/lib/useFetch";
import { weekdayName } from "./shared";

export function MyCorrections({ state, onRequest }: { state: FetchState<AttendanceCorrection[]>; onRequest: () => void }) {
  const toast = useToast();
  const [cancelling, setCancelling] = useState<AttendanceCorrection | null>(null);
  const [busy, setBusy] = useState(false);
  const items = state.data ?? [];
  const pending = items.filter((c) => c.status === "pending").length;

  async function confirmCancel() {
    if (!cancelling) return;
    setBusy(true);
    try {
      await api.post(`/attendance/corrections/${cancelling.id}/cancel`);
      toast.success(`Correction request for ${formatDate(cancelling.attendance_date)} withdrawn.`);
      setCancelling(null);
      state.reload();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to cancel the request."));
      setCancelling(null);
      state.reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="My correction requests"
      subtitle={state.loading && !state.data ? undefined : pending ? `${pending} pending` : `${items.length} total`}
      icon={<History />}
      bodyClassName="p-0"
      actions={
        <Button variant="subtle" size="sm" onClick={onRequest}>
          <FilePenLine /> New
        </Button>
      }
    >
      <AsyncContent loading={state.loading && !state.data} error={state.error} onRetry={state.reload} loadingLabel="Loading correction requests..." >
        {items.length === 0 ? (
          <EmptyState
            className="py-8"
            icon={<FilePenLine />}
            title="No correction requests"
            description="Missed a check-out or punched the wrong time? Ask your manager or HR to fix the day."
            action={
              <Button size="sm" variant="outline" onClick={onRequest}>
                Request correction
              </Button>
            }
          />
        ) : (
          <ul className="max-h-[26rem] divide-y divide-border overflow-y-auto">
            {items.map((c) => (
              <li key={c.id} className="px-5 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground tabular-nums">
                      {formatDate(c.attendance_date)} <span className="font-normal text-muted-foreground">· {weekdayName(c.attendance_date, "short")}</span>
                    </p>
                    <p className="text-xs text-muted-foreground tabular-nums">
                      Requested {formatTime(c.requested_in_time)}–{formatTime(c.requested_out_time)}
                    </p>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
                <p className="mt-1.5 line-clamp-2 text-sm text-foreground" title={c.reason}>
                  {c.reason}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {c.reviewed_by_name && c.status !== "pending" && c.status !== "cancelled"
                      ? `${c.status === "approved" ? "Approved" : "Rejected"} by ${c.reviewed_by_name}${c.reviewed_at ? ` · ${formatDateTime(c.reviewed_at)}` : ""}`
                      : `Sent ${formatDateTime(c.requested_at)}`}
                  </p>
                  {c.status === "pending" && (
                    <Button variant="ghost" size="sm" className="h-7 text-status-absent-fg hover:bg-status-absent-bg" onClick={() => setCancelling(c)}>
                      Withdraw
                    </Button>
                  )}
                </div>
                {c.review_note && <p className="mt-1.5 rounded-md bg-surface-muted px-2.5 py-1.5 text-xs text-foreground">“{c.review_note}”</p>}
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
      <ConfirmDialog
        open={!!cancelling}
        title="Withdraw correction request?"
        message={cancelling && <>Your request to correct {formatDate(cancelling.attendance_date)} will be cancelled. You can send a new one later.</>}
        confirmLabel="Withdraw request"
        busy={busy}
        onConfirm={confirmCancel}
        onCancel={() => setCancelling(null)}
      />
    </Panel>
  );
}
