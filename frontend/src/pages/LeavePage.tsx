/**
 * Leave: balance, apply, my leaves (cancel pending) · Approvals / All Requests for admin, hr, manager.
 */
import { useState, type FormEvent } from "react";
import { CalendarDays, CalendarPlus, Check, ClipboardCheck, ListChecks, Palmtree, Send, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { Field, NativeSelect, SearchInput } from "@/components/Field";
import { LeaveBalanceGrid } from "@/components/LeaveBalanceGrid";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { PageHeader, Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice, Spinner } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Tabs } from "@/components/Tabs";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { daysBetween, formatDate, formatDateTime, formatNumber, humanize, toISODate } from "@/lib/format";
import type { Leave, LeaveBalance, LeaveListItem, LeaveType } from "@/lib/types";
import { useFetch, type FetchState } from "@/lib/useFetch";

const LEAVE_TYPES: LeaveType[] = ["casual", "sick", "earned", "unpaid", "maternity", "paternity"];
type TabKey = "mine" | "approvals" | "all";

function asList<T>(data: T[] | { items: T[] } | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.items ?? []);
}

export function LeavePage() {
  const { role, user } = useAuth();
  const ownEmployeeId = user?.employee?.id;
  const isApprover = role === "admin" || role === "hr" || role === "manager";
  const [tab, setTab] = useState<TabKey>(isApprover ? "approvals" : "mine");
  const [applyOpen, setApplyOpen] = useState(false);

  const balance = useFetch<LeaveBalance[]>("/leaves/balance/me");
  const mine = useFetch<Leave[]>("/leaves/me");
  const pending = useFetch<LeaveListItem[] | { items: LeaveListItem[] }>(isApprover ? "/leaves?status=pending" : null);
  // Nobody approves their own request (backend enforces this too) — keep it out of the queue
  const approvalQueue = asList(pending.data).filter((l) => l.employee_id !== ownEmployeeId);
  const ownPendingCount = asList(pending.data).length - approvalQueue.length;
  const pendingCount = approvalQueue.length;

  const tabs = [
    ...(isApprover
      ? [{ key: "approvals" as const, label: role === "manager" ? "Team Approvals" : "Approvals", icon: <ClipboardCheck />, count: pending.loading ? undefined : pendingCount }]
      : []),
    { key: "mine" as const, label: "My Leaves", icon: <CalendarDays /> },
    ...(isApprover ? [{ key: "all" as const, label: role === "manager" ? "Team Leaves" : "All Requests", icon: <ListChecks /> }] : []),
  ];

  return (
    <>
      <PageHeader
        title="Leave"
        subtitle="Apply for leave, track balances and manage approvals"
        actions={
          <Button onClick={() => setApplyOpen(true)}>
            <CalendarPlus className="size-4" /> Apply Leave
          </Button>
        }
      />

      <Panel title="My Leave Balance" subtitle={balance.data?.[0]?.year ? `Calendar year ${balance.data[0].year}` : "Current calendar year"} icon={<Palmtree />} className="mb-5">
        <AsyncContent loading={balance.loading} error={balance.error} onRetry={balance.reload} loadingLabel="Loading balance...">
          {(balance.data ?? []).length === 0 ? <EmptyState title="No leave balance available" /> : <LeaveBalanceGrid balances={balance.data ?? []} />}
        </AsyncContent>
      </Panel>

      {tabs.length > 1 && <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5" />}

      {tab === "mine" && (
        <MyLeaves
          state={mine}
          onChanged={() => {
            mine.reload();
            balance.reload();
          }}
        />
      )}
      {tab === "approvals" && isApprover && (
        <Approvals
          rows={approvalQueue}
          ownPendingCount={ownPendingCount}
          loading={pending.loading}
          error={pending.error}
          reload={pending.reload}
          onChanged={() => {
            pending.reload();
            mine.reload();
          }}
        />
      )}
      {tab === "all" && isApprover && <AllRequests onChanged={pending.reload} />}

      <ApplyLeaveModal
        open={applyOpen}
        balances={balance.data ?? []}
        onClose={() => setApplyOpen(false)}
        onApplied={() => {
          setApplyOpen(false);
          mine.reload();
          balance.reload();
          if (isApprover) pending.reload();
          setTab("mine");
        }}
      />
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function MyLeaves({ state, onChanged }: { state: FetchState<Leave[]>; onChanged: () => void }) {
  const toast = useToast();
  const [cancelling, setCancelling] = useState<Leave | null>(null);
  const [busy, setBusy] = useState(false);
  const rows = (state.data ?? []).slice().sort((a, b) => b.from_date.localeCompare(a.from_date));

  async function confirmCancel() {
    if (!cancelling) return;
    setBusy(true);
    try {
      await api.post(`/leaves/${cancelling.id}/cancel`);
      toast.success("Leave request cancelled.");
      setCancelling(null);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to cancel leave."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="My Leave Requests" icon={<CalendarDays />} bodyClassName="p-0">
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} loadingLabel="Loading leaves...">
        <DataTable
          rows={rows}
          rowKey={(l) => l.id}
          empty={<EmptyState icon={<CalendarDays className="size-6" />} title="No leave requests yet" description="Use “Apply Leave” to submit your first request." />}
          columns={[
            { key: "type", header: "Type", render: (l) => <span className="font-medium">{humanize(l.leave_type)}</span> },
            { key: "from", header: "From", render: (l) => formatDate(l.from_date) },
            { key: "to", header: "To", render: (l) => formatDate(l.to_date) },
            { key: "days", header: "Days", align: "right", render: (l) => daysBetween(l.from_date, l.to_date) },
            { key: "reason", header: "Reason", render: (l) => <span className="block max-w-[280px] truncate text-ink-muted">{l.reason || "—"}</span> },
            { key: "status", header: "Status", render: (l) => <StatusBadge status={l.status} /> },
            {
              key: "actions",
              header: <span className="sr-only">Actions</span>,
              align: "right",
              render: (l) =>
                l.status?.toLowerCase() === "pending" ? (
                  <Button variant="ghost" size="sm" className="text-danger hover:bg-danger-light hover:text-danger" onClick={() => setCancelling(l)}>
                    Cancel
                  </Button>
                ) : null,
            },
          ]}
        />
      </AsyncContent>
      <ConfirmDialog
        open={!!cancelling}
        title="Cancel leave request?"
        message={
          cancelling && (
            <>
              Your {humanize(cancelling.leave_type).toLowerCase()} leave from {formatDate(cancelling.from_date)} to {formatDate(cancelling.to_date)} will be
              cancelled.
            </>
          )
        }
        confirmLabel="Cancel request"
        busy={busy}
        onConfirm={confirmCancel}
        onCancel={() => setCancelling(null)}
      />
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function useDecide(onChanged: () => void) {
  const toast = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);
  async function decide(leave: LeaveListItem, status: "approved" | "rejected") {
    setBusyId(leave.id);
    try {
      await api.patch(`/leaves/${leave.id}/status`, { status });
      toast.success(`Leave for ${leave.employee_name} ${status}.`);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to update leave."));
    } finally {
      setBusyId(null);
    }
  }
  return { decide, busyId };
}

function leaveColumns(
  decide: ((l: LeaveListItem, s: "approved" | "rejected") => void) | null,
  busyId: number | null,
  ownEmployeeId?: number,
) {
  return [
    {
      key: "emp",
      header: "Employee",
      render: (l: LeaveListItem) => (
        <div className="flex items-center gap-2.5">
          <Avatar name={l.employee_name} size="sm" />
          <div>
            <p className="font-medium">{l.employee_name}</p>
            <p className="text-xs text-ink-muted">{[l.employee_code, l.department].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
      ),
    },
    { key: "type", header: "Type", render: (l: LeaveListItem) => humanize(l.leave_type) },
    { key: "dates", header: "Dates", render: (l: LeaveListItem) => `${formatDate(l.from_date)} – ${formatDate(l.to_date)}` },
    { key: "days", header: "Days", align: "right" as const, render: (l: LeaveListItem) => l.days ?? daysBetween(l.from_date, l.to_date) },
    { key: "reason", header: "Reason", render: (l: LeaveListItem) => <span className="block max-w-[240px] truncate text-ink-muted" title={l.reason ?? ""}>{l.reason || "—"}</span> },
    { key: "applied", header: "Applied", render: (l: LeaveListItem) => <span className="text-ink-muted">{l.applied_at ? formatDateTime(l.applied_at) : "—"}</span> },
    { key: "status", header: "Status", render: (l: LeaveListItem) => <StatusBadge status={l.status} /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right" as const,
      render: (l: LeaveListItem) =>
        // No approve/reject on your own request — the API refuses self-approval
        decide && l.status?.toLowerCase() === "pending" && l.employee_id !== ownEmployeeId ? (
          <div className="flex justify-end gap-1.5">
            <Button size="sm" className="bg-success hover:bg-success/90" disabled={busyId === l.id} onClick={() => decide(l, "approved")}>
              {busyId === l.id ? <Spinner /> : <Check className="size-3.5" />} Approve
            </Button>
            <Button size="sm" variant="outline" className="text-danger hover:bg-danger-light hover:text-danger" disabled={busyId === l.id} onClick={() => decide(l, "rejected")}>
              <X className="size-3.5" /> Reject
            </Button>
          </div>
        ) : null,
    },
  ];
}

function Approvals({
  rows,
  ownPendingCount = 0,
  loading,
  error,
  reload,
  onChanged,
}: {
  rows: LeaveListItem[];
  ownPendingCount?: number;
  loading: boolean;
  error: string | null;
  reload: () => void;
  onChanged: () => void;
}) {
  const { decide, busyId } = useDecide(onChanged);
  return (
    <Panel title="Pending Approvals" subtitle={loading ? undefined : `${rows.length} awaiting decision`} icon={<ClipboardCheck />} bodyClassName="p-0">
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading pending requests...">
        {ownPendingCount > 0 && (
          <Notice className="m-4">
            You have {ownPendingCount} pending request{ownPendingCount === 1 ? "" : "s"} of your own. Nobody can approve their own
            leave — another HR/admin user or your reporting manager will review {ownPendingCount === 1 ? "it" : "them"}. Track
            {ownPendingCount === 1 ? " it" : " them"} under <strong>My Leaves</strong>.
          </Notice>
        )}
        <DataTable
          rows={rows}
          rowKey={(l) => l.id}
          empty={<EmptyState icon={<ClipboardCheck className="size-6" />} title="All caught up" description="There are no pending leave requests." />}
          columns={leaveColumns(decide, busyId)}
        />
      </AsyncContent>
    </Panel>
  );
}

function AllRequests({ onChanged }: { onChanged: () => void }) {
  const { user } = useAuth();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const state = useFetch<LeaveListItem[] | { items: LeaveListItem[] }>(`/leaves${qs({ status })}`);
  const { decide, busyId } = useDecide(() => {
    state.reload();
    onChanged();
  });
  const q = search.toLowerCase();
  const rows = asList(state.data)
    .filter((l) => !q || l.employee_name?.toLowerCase().includes(q) || (l.department ?? "").toLowerCase().includes(q))
    .sort((a, b) => b.from_date.localeCompare(a.from_date));

  return (
    <Panel title="Leave Requests" icon={<ListChecks />} bodyClassName="p-0">
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row">
        <SearchInput value={search} onChange={setSearch} placeholder="Search employee or department..." className="sm:w-72" />
        <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
          <option value="">All statuses</option>
          {["pending", "approved", "rejected", "cancelled"].map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <AsyncContent loading={state.loading} error={state.error} onRetry={state.reload} loadingLabel="Loading leave requests...">
        <DataTable rows={rows} rowKey={(l) => l.id} empty={<EmptyState title="No leave requests found" />} columns={leaveColumns(decide, busyId, user?.employee?.id)} />
      </AsyncContent>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ApplyLeaveModal({
  open,
  balances,
  onClose,
  onApplied,
}: {
  open: boolean;
  balances: LeaveBalance[];
  onClose: () => void;
  onApplied: () => void;
}) {
  const toast = useToast();
  const today = toISODate(new Date());
  const [form, setForm] = useState({ leave_type: "casual", start_date: today, end_date: today, reason: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const days = form.start_date && form.end_date && form.end_date >= form.start_date ? daysBetween(form.start_date, form.end_date) : 0;
  const bal = balances.find((b) => b.leave_type.toLowerCase() === form.leave_type);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!form.start_date || !form.end_date) return setErr("Please choose start and end dates.");
    if (form.end_date < form.start_date) return setErr("End date cannot be before start date.");
    setSaving(true);
    try {
      await api.post("/leaves", {
        leave_type: form.leave_type,
        start_date: form.start_date,
        end_date: form.end_date,
        reason: form.reason.trim() || null,
      });
      toast.success("Leave request submitted.");
      setForm({ leave_type: "casual", start_date: today, end_date: today, reason: "" });
      onApplied();
    } catch (error) {
      setErr(errorMessage(error, "Failed to submit leave request."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Apply Leave"
      description="Your request will be sent to your manager / HR for approval"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="apply-leave-form" disabled={saving}>
            {saving ? <Spinner /> : <Send className="size-4" />} Submit request
          </Button>
        </>
      }
    >
      <form id="apply-leave-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
        <Field label="Leave type" htmlFor="lv-type" required className="sm:col-span-2">
          <NativeSelect id="lv-type" value={form.leave_type} onChange={(e) => setForm((f) => ({ ...f, leave_type: e.target.value }))} className="w-full">
            {LEAVE_TYPES.map((t) => (
              <option key={t} value={t}>
                {humanize(t)}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="From" htmlFor="lv-from" required>
          <Input
            id="lv-from"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value, end_date: f.end_date < e.target.value ? e.target.value : f.end_date }))}
          />
        </Field>
        <Field label="To" htmlFor="lv-to" required>
          <Input id="lv-to" type="date" min={form.start_date} value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
        </Field>
        <Field label="Reason" htmlFor="lv-reason" className="sm:col-span-2">
          <Textarea id="lv-reason" rows={3} value={form.reason} onChange={(e) => setForm((f) => ({ ...f, reason: e.target.value }))} placeholder="Briefly describe the reason" />
        </Field>
        <div className="flex flex-wrap gap-2 text-xs sm:col-span-2">
          <span className="rounded-md bg-slate-100 px-2 py-1 text-ink-muted">
            Duration: <strong className="text-ink">{days} day{days === 1 ? "" : "s"}</strong>
          </span>
          {bal && (
            <span className={`rounded-md px-2 py-1 ${days > bal.remaining ? "bg-warning-light text-amber-800" : "bg-slate-100 text-ink-muted"}`}>
              {humanize(bal.leave_type)} remaining: <strong>{formatNumber(bal.remaining, 1)}</strong>
            </span>
          )}
        </div>
        {err && (
          <Notice tone="danger" className="sm:col-span-2">
            {err}
          </Notice>
        )}
      </form>
    </Modal>
  );
}
