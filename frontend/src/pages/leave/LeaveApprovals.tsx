/**
 * Leave approvals for admin / hr / manager (team only — enforced by the API):
 * - ApprovalQueue: pending requests as cards (GET /leaves?status=pending, own excluded).
 * - AllRequests: searchable/sortable table of every in-scope request (GET /leaves?status=…).
 * Decisions go through a confirm dialog → PATCH /leaves/{id}/status {status}. Nobody — HR/Admin included — can decide
 * their own request (D-022), so those rows never get Approve/Reject and a Notice explains why.
 */
import { useState } from "react";
import { Check, ClipboardCheck, ListChecks, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { SearchInput } from "@/components/Field";
import { leaveTypeColor } from "@/components/LeaveBalanceGrid";
import { ConfirmDialog } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage, qs } from "@/lib/api";
import { daysBetween, formatDate, formatDateTime, humanize } from "@/lib/format";
import type { LeaveListItem } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

type Decision = { leave: LeaveListItem; status: "approved" | "rejected" };

/** Working days as computed by the API (`days`); calendar days only as a fallback. */
const workingDays = (l: LeaveListItem): number => l.days ?? daysBetween(l.from_date, l.to_date);

function useDecision(onChanged: () => void) {
  const toast = useToast();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [busy, setBusy] = useState(false);
  async function confirm() {
    if (!decision) return;
    const { leave, status } = decision;
    setBusy(true);
    try {
      await api.patch(`/leaves/${leave.id}/status`, { status });
      toast.success(`${humanize(leave.leave_type)} leave for ${leave.employee_name} ${status}.`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to update the leave request."));
    } finally {
      setBusy(false);
      setDecision(null);
      onChanged();
    }
  }
  const dialog = (
    <ConfirmDialog
      open={!!decision}
      title={decision?.status === "approved" ? "Approve leave?" : "Reject leave?"}
      tone={decision?.status === "approved" ? "default" : "danger"}
      message={
        decision && (
          <>
            <strong className="text-foreground">{decision.leave.employee_name}</strong> · {humanize(decision.leave.leave_type).toLowerCase()} leave,{" "}
            {formatDate(decision.leave.from_date)}
            {decision.leave.to_date !== decision.leave.from_date ? ` – ${formatDate(decision.leave.to_date)}` : ""} ({workingDays(decision.leave)} working day
            {workingDays(decision.leave) === 1 ? "" : "s"}).{" "}
            {decision.status === "approved" ? "The days are deducted from their balance." : "The employee will see the request as rejected."}
          </>
        )
      }
      confirmLabel={decision?.status === "approved" ? "Approve" : "Reject"}
      busy={busy}
      onConfirm={confirm}
      onCancel={() => setDecision(null)}
    />
  );
  return { ask: (leave: LeaveListItem, status: "approved" | "rejected") => setDecision({ leave, status }), dialog };
}

function DecisionButtons({ leave, ask }: { leave: LeaveListItem; ask: (l: LeaveListItem, s: "approved" | "rejected") => void }) {
  return (
    <div className="flex justify-end gap-1.5">
      <Button size="sm" variant="success" onClick={() => ask(leave, "approved")} aria-label={`Approve leave for ${leave.employee_name}`}>
        <Check /> Approve
      </Button>
      <Button size="sm" variant="outline" className="text-status-absent-fg" onClick={() => ask(leave, "rejected")} aria-label={`Reject leave for ${leave.employee_name}`}>
        <X /> Reject
      </Button>
    </div>
  );
}

function OwnNotice({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <Notice>
      You have {count} pending request{count === 1 ? "" : "s"} of your own. Nobody can approve their own leave — your reporting manager or another HR/admin user
      reviews {count === 1 ? "it" : "them"}. Track {count === 1 ? "it" : "them"} under <strong>My leaves</strong>.
    </Notice>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

export function ApprovalQueue({
  rows,
  ownPendingCount,
  loading,
  error,
  reload,
  onChanged,
  isManager,
}: {
  rows: LeaveListItem[];
  ownPendingCount: number;
  loading: boolean;
  error: string | null;
  reload: () => void;
  onChanged: () => void;
  isManager: boolean;
}) {
  const { ask, dialog } = useDecision(onChanged);
  const sorted = [...rows].sort((a, b) => a.from_date.localeCompare(b.from_date));
  return (
    <div className="flex flex-col gap-4">
      <OwnNotice count={ownPendingCount} />
      <Panel
        title={isManager ? "Team requests awaiting you" : "Requests awaiting a decision"}
        subtitle={loading && rows.length === 0 ? undefined : `${rows.length} pending · earliest start first`}
        icon={<ClipboardCheck />}
      >
        <AsyncContent
          loading={loading && rows.length === 0}
          error={error}
          onRetry={reload}
          skeleton={
            <div className="grid gap-3 lg:grid-cols-2" role="status">
              <span className="sr-only">Loading pending requests</span>
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-40" />
              ))}
            </div>
          }
        >
          {sorted.length === 0 ? (
            <EmptyState icon={<ClipboardCheck />} title="All caught up" description={isManager ? "No pending leave requests from your team." : "There are no pending leave requests."} />
          ) : (
            <ul className="grid gap-3 lg:grid-cols-2">
              {sorted.map((l) => (
                <li key={l.id} className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
                  <div className="flex items-start gap-3">
                    <Avatar name={l.employee_name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-foreground">{l.employee_name}</p>
                      <p className="truncate text-xs text-muted-foreground">{[l.employee_code, l.department].filter(Boolean).join(" · ")}</p>
                    </div>
                    <StatusBadge status={l.status} />
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <span className="flex items-center gap-1.5 font-medium text-foreground">
                      <span className="size-2 rounded-full" style={{ background: leaveTypeColor(l.leave_type) }} aria-hidden="true" />
                      {humanize(l.leave_type)}
                    </span>
                    <span className="text-muted-foreground tabular-nums">
                      {formatDate(l.from_date)}
                      {l.to_date !== l.from_date && ` – ${formatDate(l.to_date)}`}
                    </span>
                    <Badge tone="brand" className="tabular-nums">
                      {workingDays(l)} working day{workingDays(l) === 1 ? "" : "s"}
                    </Badge>
                  </div>
                  <p className="line-clamp-3 text-sm text-foreground">{l.reason || <span className="text-muted-foreground">No reason given</span>}</p>
                  <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
                    <span className="text-xs text-muted-foreground tabular-nums">{l.applied_at ? `Applied ${formatDateTime(l.applied_at)}` : ""}</span>
                    <DecisionButtons leave={l} ask={ask} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </AsyncContent>
      </Panel>
      {dialog}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

type StatusFilter = "" | "pending" | "approved" | "rejected" | "cancelled";

export function AllRequests({ ownEmployeeId, onChanged, isManager }: { ownEmployeeId?: number; onChanged: () => void; isManager: boolean }) {
  const [status, setStatus] = useState<StatusFilter>("");
  const [search, setSearch] = useState("");
  const state = useFetch<LeaveListItem[]>(`/leaves${qs({ status })}`);
  const { ask, dialog } = useDecision(() => {
    state.reload();
    onChanged();
  });
  const q = search.trim().toLowerCase();
  const rows = (state.data ?? [])
    .filter((l) => !q || l.employee_name?.toLowerCase().includes(q) || (l.department ?? "").toLowerCase().includes(q) || (l.employee_code ?? "").toLowerCase().includes(q))
    .sort((a, b) => b.from_date.localeCompare(a.from_date));
  const ownPending = (state.data ?? []).filter((l) => l.employee_id === ownEmployeeId && l.status === "pending").length;

  const actions = (l: LeaveListItem) =>
    l.status === "pending" ? (
      l.employee_id === ownEmployeeId ? (
        <span className="text-xs text-muted-foreground">Your request</span>
      ) : (
        <DecisionButtons leave={l} ask={ask} />
      )
    ) : null;

  return (
    <Panel title={isManager ? "Team leave" : "All leave requests"} subtitle={state.loading && !state.data ? undefined : `${rows.length} shown`} icon={<ListChecks />} bodyClassName="p-0">
      <div className="flex flex-col gap-3 border-b border-border p-4 lg:flex-row lg:items-center">
        <SearchInput value={search} onChange={setSearch} placeholder="Search name, code or department..." className="lg:w-80" />
        <Segmented<StatusFilter>
          label="Status filter"
          value={status}
          onChange={setStatus}
          className="lg:ml-auto"
          options={[
            { value: "", label: "All" },
            { value: "pending", label: "Pending" },
            { value: "approved", label: "Approved" },
            { value: "rejected", label: "Rejected" },
            { value: "cancelled", label: "Cancelled" },
          ]}
        />
      </div>
      {ownPending > 0 && (
        <div className="border-b border-border p-4">
          <OwnNotice count={ownPending} />
        </div>
      )}
      <AsyncContent loading={state.loading && !state.data} error={state.error} onRetry={state.reload} loadingLabel="Loading leave requests...">
        <DataTable
          rows={rows}
          rowKey={(l) => l.id}
          pageSize={15}
          empty={
            <EmptyState
              icon={<ListChecks />}
              title="No leave requests found"
              description={q || status ? "Try another search or status." : "Requests appear here once employees apply."}
              action={
                q || status ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSearch("");
                      setStatus("");
                    }}
                  >
                    Clear filters
                  </Button>
                ) : undefined
              }
            />
          }
          mobileCard={(l) => (
            <div className="flex flex-col gap-2 px-4 py-3">
              <div className="flex items-start gap-3">
                <Avatar name={l.employee_name} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {l.employee_name}
                    {l.employee_id === ownEmployeeId && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(you)</span>}
                  </p>
                  <p className="text-xs text-muted-foreground tabular-nums">
                    {humanize(l.leave_type)} · {formatDate(l.from_date)}
                    {l.to_date !== l.from_date && ` – ${formatDate(l.to_date)}`} · {workingDays(l)}d
                  </p>
                </div>
                <StatusBadge status={l.status} />
              </div>
              {l.status === "pending" && l.employee_id !== ownEmployeeId && <DecisionButtons leave={l} ask={ask} />}
            </div>
          )}
          columns={[
            {
              key: "emp",
              header: "Employee",
              sortValue: (l) => l.employee_name,
              render: (l) => (
                <div className="flex items-center gap-2.5">
                  <Avatar name={l.employee_name} size="sm" />
                  <div>
                    <p className="font-medium">
                      {l.employee_name}
                      {l.employee_id === ownEmployeeId && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(you)</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">{[l.employee_code, l.department].filter(Boolean).join(" · ")}</p>
                  </div>
                </div>
              ),
            },
            {
              key: "type",
              header: "Type",
              sortValue: (l) => l.leave_type,
              render: (l) => (
                <span className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full" style={{ background: leaveTypeColor(l.leave_type) }} aria-hidden="true" />
                  {humanize(l.leave_type)}
                </span>
              ),
            },
            {
              key: "dates",
              header: "Dates",
              sortValue: (l) => l.from_date,
              render: (l) => (
                <span className="tabular-nums">
                  {formatDate(l.from_date)}
                  {l.to_date !== l.from_date && ` – ${formatDate(l.to_date)}`}
                </span>
              ),
            },
            { key: "days", header: "Days", align: "right", sortValue: (l) => l.days ?? 0, render: (l) => <span className="tabular-nums">{workingDays(l)}</span> },
            {
              key: "reason",
              header: "Reason",
              render: (l) => (
                <span className="block max-w-[220px] truncate text-muted-foreground" title={l.reason ?? ""}>
                  {l.reason || "—"}
                </span>
              ),
            },
            { key: "applied", header: "Applied", sortValue: (l) => l.applied_at ?? "", render: (l) => <span className="text-xs text-muted-foreground tabular-nums">{l.applied_at ? formatDateTime(l.applied_at) : "—"}</span> },
            { key: "status", header: "Status", sortValue: (l) => l.status, render: (l) => <StatusBadge status={l.status} /> },
            { key: "actions", header: <span className="sr-only">Actions</span>, align: "right", render: actions },
          ]}
        />
      </AsyncContent>
      {dialog}
    </Panel>
  );
}
