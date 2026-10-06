/**
 * Correction approvals (D-033) for approver roles: GET /attendance/corrections?status=… (manager → direct reports,
 * HR/Admin → everyone; the caller's own requests are never listed). Approve/Reject via
 * POST /attendance/corrections/{id}/approve|reject {note?} — approval recomputes the day on the server.
 */
import { useState, type FormEvent } from "react";
import { ArrowRight, Check, ClipboardCheck, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { Field } from "@/components/Field";
import { Modal } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage, qs } from "@/lib/api";
import { formatDate, formatDateTime, formatMinutes, formatTime } from "@/lib/format";
import type { AttendanceCorrection, Role } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { toMinutes, weekdayName } from "./shared";

type Filter = "pending" | "approved" | "rejected" | "cancelled" | "all";
type Decision = { item: AttendanceCorrection; approve: boolean };

function span(a: string | null, b: string | null): string | null {
  const x = toMinutes(a);
  const y = toMinutes(b);
  return x !== null && y !== null && y > x ? formatMinutes(y - x) : null;
}

function CurrentCell({ c }: { c: AttendanceCorrection }) {
  if (!c.current_status) return <span className="text-xs text-muted-foreground">No record</span>;
  return (
    <div className="flex flex-col items-start gap-0.5">
      <StatusBadge status={c.current_status} />
      <span className="text-xs text-muted-foreground tabular-nums">
        {formatTime(c.current_in_time)} – {formatTime(c.current_out_time)}
      </span>
    </div>
  );
}

function RequestedCell({ c }: { c: AttendanceCorrection }) {
  const d = span(c.requested_in_time, c.requested_out_time);
  return (
    <div>
      <p className="font-medium text-foreground tabular-nums">
        {formatTime(c.requested_in_time)} – {formatTime(c.requested_out_time)}
      </p>
      {d && <p className="text-xs text-muted-foreground tabular-nums">{d}</p>}
    </div>
  );
}

export function CorrectionsQueue({ role, ownEmployeeId, onChanged }: { role: Role | null; ownEmployeeId?: number; onChanged: () => void }) {
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>("pending");
  const state = useFetch<AttendanceCorrection[]>(`/attendance/corrections${qs({ status: filter === "all" ? "" : filter })}`);
  // The API already excludes your own requests; filter again so an approve button can never appear on one (D-022/D-033)
  const rows = (state.data ?? []).filter((c) => c.employee_id !== ownEmployeeId);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function open(item: AttendanceCorrection, approve: boolean) {
    setNote("");
    setErr(null);
    setDecision({ item, approve });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!decision) return;
    const { item, approve } = decision;
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/attendance/corrections/${item.id}/${approve ? "approve" : "reject"}`, { note: note.trim() || null });
      toast.success(approve ? `Approved — ${item.employee_name}'s ${formatDate(item.attendance_date)} was updated.` : `Rejected ${item.employee_name}'s correction for ${formatDate(item.attendance_date)}.`);
      setDecision(null);
      state.reload();
      onChanged();
    } catch (error) {
      const msg = errorMessage(error, "Failed to review the request.");
      setErr(msg);
      toast.error(msg);
      state.reload();
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  const actions = (c: AttendanceCorrection) =>
    c.status === "pending" ? (
      <div className="flex justify-end gap-1.5">
        <Button size="sm" variant="success" onClick={() => open(c, true)} aria-label={`Approve correction for ${c.employee_name}, ${formatDate(c.attendance_date)}`}>
          <Check /> Approve
        </Button>
        <Button size="sm" variant="outline" className="text-status-absent-fg" onClick={() => open(c, false)} aria-label={`Reject correction for ${c.employee_name}, ${formatDate(c.attendance_date)}`}>
          <X /> Reject
        </Button>
      </div>
    ) : (
      <div className="text-right text-xs text-muted-foreground">
        {c.reviewed_by_name ? (
          <>
            by {c.reviewed_by_name}
            {c.reviewed_at && <span className="block tabular-nums">{formatDateTime(c.reviewed_at)}</span>}
          </>
        ) : (
          "—"
        )}
      </div>
    );

  return (
    <Panel
      title="Attendance corrections"
      subtitle={role === "manager" ? "Requests from your direct reports" : "Requests from employees to fix a day's times"}
      icon={<ClipboardCheck />}
      bodyClassName="p-0"
    >
      <div className="flex flex-col gap-2 border-b border-border px-5 pb-3">
        <Segmented<Filter>
          label="Status filter"
          value={filter}
          onChange={setFilter}
          className="self-start"
          options={[
            { value: "pending", label: "Pending" },
            { value: "approved", label: "Approved" },
            { value: "rejected", label: "Rejected" },
            { value: "cancelled", label: "Withdrawn" },
            { value: "all", label: "All" },
          ]}
        />
        <p className="text-xs text-muted-foreground">
          Approving sets the requested in/out time; the status (present or half day), late and overtime minutes are recalculated. Your own requests are reviewed
          by someone else and never appear here.
        </p>
      </div>
      <AsyncContent loading={state.loading && !state.data} error={state.error} onRetry={state.reload} loadingLabel="Loading correction requests...">
        <DataTable
          rows={rows}
          rowKey={(c) => c.id}
          pageSize={15}
          empty={
            <EmptyState
              icon={<ClipboardCheck />}
              title={filter === "pending" ? "All caught up" : "No requests"}
              description={filter === "pending" ? "There are no correction requests waiting for you." : "No correction requests with this status."}
              action={
                filter !== "all" ? (
                  <Button size="sm" variant="outline" onClick={() => setFilter("all")}>
                    Show all requests
                  </Button>
                ) : undefined
              }
            />
          }
          mobileCard={(c) => (
            <div className="flex flex-col gap-2 px-4 py-3">
              <div className="flex items-start gap-3">
                <Avatar name={c.employee_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{c.employee_name}</p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {formatDate(c.attendance_date)} · {weekdayName(c.attendance_date, "short")}
                  </p>
                </div>
                <StatusBadge status={c.status} />
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <CurrentCell c={c} />
                <ArrowRight className="size-3.5 text-muted-foreground" aria-label="changes to" />
                <RequestedCell c={c} />
              </div>
              <p className="text-sm text-foreground">{c.reason}</p>
              {actions(c)}
            </div>
          )}
          columns={[
            {
              key: "emp",
              header: "Employee",
              sortValue: (c) => c.employee_name,
              render: (c) => (
                <div className="flex items-center gap-2.5">
                  <Avatar name={c.employee_name} size="sm" />
                  <div>
                    <p className="font-medium">{c.employee_name}</p>
                    <p className="text-xs text-muted-foreground">{[c.employee_code, c.department].filter(Boolean).join(" · ")}</p>
                  </div>
                </div>
              ),
            },
            {
              key: "date",
              header: "Day",
              sortValue: (c) => c.attendance_date,
              render: (c) => (
                <div>
                  <p className="font-medium tabular-nums">{formatDate(c.attendance_date)}</p>
                  <p className="text-xs text-muted-foreground">{weekdayName(c.attendance_date)}</p>
                </div>
              ),
            },
            {
              key: "change",
              header: "Current → requested",
              label: "change",
              render: (c) => (
                <div className="flex items-center gap-2.5">
                  <CurrentCell c={c} />
                  <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-label="changes to" />
                  <RequestedCell c={c} />
                </div>
              ),
            },
            {
              key: "reason",
              header: "Reason",
              sortValue: (c) => c.requested_at,
              label: "date sent",
              render: (c) => (
                <div className="w-[220px] whitespace-normal">
                  <p className="line-clamp-2 text-sm" title={c.reason}>
                    {c.reason}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">Sent {formatDateTime(c.requested_at)}</p>
                  {c.review_note && (
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground" title={c.review_note}>
                      Note: {c.review_note}
                    </p>
                  )}
                </div>
              ),
            },
            ...(filter === "pending"
              ? []
              : [{ key: "status", header: "Status", render: (c: AttendanceCorrection) => <StatusBadge status={c.status} label={c.status === "cancelled" ? "Withdrawn" : undefined} /> }]),
            { key: "actions", header: <span className="sr-only">Actions</span>, align: "right" as const, render: actions },
          ]}
        />
      </AsyncContent>

      <Modal
        open={!!decision}
        onClose={busy ? () => undefined : () => setDecision(null)}
        title={decision?.approve ? "Approve correction?" : "Reject correction?"}
        size="sm"
        footer={
          <>
            <Button variant="outline" onClick={() => setDecision(null)} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" form="review-form" variant={decision?.approve ? "success" : "destructive"} loading={busy}>
              {decision?.approve ? "Approve" : "Reject"}
            </Button>
          </>
        }
      >
        {decision && (
          <form id="review-form" onSubmit={submit} className="flex flex-col gap-4" noValidate>
            <div className="rounded-lg border border-border bg-surface-muted p-3 text-sm">
              <p className="font-medium text-foreground">
                {decision.item.employee_name} · {formatDate(decision.item.attendance_date)}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <CurrentCell c={decision.item} />
                <ArrowRight className="size-3.5 text-muted-foreground" aria-label="changes to" />
                <RequestedCell c={decision.item} />
              </div>
              <p className="mt-2 text-muted-foreground">“{decision.item.reason}”</p>
            </div>
            <p className="text-sm text-muted-foreground">
              {decision.approve
                ? "The day will be set to the requested times and recalculated. This can't be undone from here."
                : "The attendance record stays as it is. The employee sees your note."}
            </p>
            <Field label="Note (optional)" htmlFor="review-note" hint="Visible to the employee">
              <Textarea id="review-note" rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} placeholder={decision.approve ? "e.g. Verified with access logs" : "e.g. Please attach the visit report"} />
            </Field>
            {err && <Notice tone="danger">{err}</Notice>}
          </form>
        )}
      </Modal>
    </Panel>
  );
}
