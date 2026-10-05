/** Settings (admin): Users & Roles · AI Chat Audit Log · Company Policy. */
import { Fragment, useState } from "react";
import { Bot, Building, ChevronDown, ChevronRight, Clock, Palmtree, ScrollText, ShieldCheck, Timer, UserCog, Users } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { NativeSelect, SearchInput } from "@/components/Field";
import { ConfirmDialog } from "@/components/Modal";
import { PageHeader, Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Tabs } from "@/components/Tabs";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatDateTime, humanize } from "@/lib/format";
import type { AppUser, ChatLog, Role } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";

type TabKey = "users" | "logs" | "policy";
const ROLES: Role[] = ["employee", "manager", "hr", "admin"];

export function SettingsPage() {
  const [tab, setTab] = useState<TabKey>("users");
  return (
    <>
      <PageHeader title="Settings" subtitle="System administration" />
      <Tabs
        tabs={[
          { key: "users", label: "Users & Roles", icon: <UserCog /> },
          { key: "logs", label: "AI Chat Audit Log", icon: <ScrollText /> },
          { key: "policy", label: "Company Policy", icon: <Building /> },
        ]}
        value={tab}
        onChange={setTab}
        className="mb-5"
      />
      {tab === "users" && <UsersTab />}
      {tab === "logs" && <ChatLogsTab />}
      {tab === "policy" && <PolicyTab />}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function UsersTab() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload, setData } = useFetch<AppUser[]>("/users");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [confirm, setConfirm] = useState<AppUser | null>(null);

  const q = search.toLowerCase();
  const rows = (data ?? []).filter(
    (u) =>
      (!roleFilter || u.role === roleFilter) &&
      (!q || u.email.toLowerCase().includes(q) || (u.employee_name ?? "").toLowerCase().includes(q) || (u.employee_code ?? "").toLowerCase().includes(q)),
  );

  async function update(u: AppUser, patch: { role?: Role; status?: string }) {
    setBusyId(u.id);
    try {
      const updated = await api.patch<AppUser>(`/users/${u.id}`, patch);
      setData((prev) => (prev ?? []).map((x) => (x.id === u.id ? { ...x, ...patch, ...(updated ?? {}) } : x)));
      toast.success(patch.role ? `${u.email} is now ${patch.role === "hr" ? "HR" : humanize(patch.role)}.` : `${u.email} ${patch.status === "active" ? "activated" : "deactivated"}.`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to update user."));
    } finally {
      setBusyId(null);
      setConfirm(null);
    }
  }

  return (
    <Panel
      title="Users & Roles"
      subtitle={loading ? undefined : `${rows.length} user${rows.length === 1 ? "" : "s"}`}
      icon={<Users />}
      bodyClassName="p-0"
    >
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row">
        <SearchInput value={search} onChange={setSearch} placeholder="Search email or employee..." className="sm:w-72" />
        <NativeSelect value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Role filter">
          <option value="">All roles</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r === "hr" ? "HR" : humanize(r)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading users...">
        <DataTable
          rows={rows}
          rowKey={(u) => u.id}
          empty={<EmptyState icon={<Users className="size-6" />} title="No users found" />}
          columns={[
            {
              key: "user",
              header: "User",
              render: (u) => (
                <div className="flex items-center gap-2.5">
                  <Avatar name={u.employee_name ?? u.email} size="sm" />
                  <div>
                    <p className="font-medium">
                      {u.employee_name ?? "—"}
                      {u.id === me?.user_id && <span className="ml-1.5 text-xs font-normal text-ink-muted">(you)</span>}
                    </p>
                    <p className="text-xs text-ink-muted">{u.email}</p>
                  </div>
                </div>
              ),
            },
            { key: "code", header: "Employee", render: (u) => <span className="text-ink-muted">{u.employee_code ?? "Not linked"}</span> },
            {
              key: "role",
              header: "Role",
              render: (u) => (
                <NativeSelect
                  value={u.role}
                  disabled={busyId === u.id || u.id === me?.user_id}
                  onChange={(e) => void update(u, { role: e.target.value as Role })}
                  aria-label={`Role for ${u.email}`}
                  className="h-8 text-[13px]"
                  title={u.id === me?.user_id ? "You cannot change your own role" : undefined}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r === "hr" ? "HR" : humanize(r)}
                    </option>
                  ))}
                </NativeSelect>
              ),
            },
            { key: "status", header: "Status", render: (u) => <StatusBadge status={u.status} /> },
            { key: "created", header: "Created", render: (u) => <span className="text-ink-muted">{formatDate(u.created_at)}</span> },
            {
              key: "actions",
              header: <span className="sr-only">Actions</span>,
              align: "right",
              render: (u) =>
                u.id === me?.user_id ? null : u.status === "active" ? (
                  <Button variant="outline" size="sm" className="text-danger hover:bg-danger-light hover:text-danger" disabled={busyId === u.id} onClick={() => setConfirm(u)}>
                    Deactivate
                  </Button>
                ) : (
                  <Button variant="outline" size="sm" className="text-success hover:bg-success-light hover:text-success" disabled={busyId === u.id} onClick={() => void update(u, { status: "active" })}>
                    Activate
                  </Button>
                ),
            },
          ]}
        />
      </AsyncContent>
      <ConfirmDialog
        open={!!confirm}
        title="Deactivate user?"
        message={
          <>
            <strong className="text-ink">{confirm?.email}</strong> will no longer be able to sign in.
          </>
        }
        confirmLabel="Deactivate"
        busy={busyId === confirm?.id}
        onConfirm={() => confirm && void update(confirm, { status: "inactive" })}
        onCancel={() => setConfirm(null)}
      />
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function ChatLogsTab() {
  const { data, loading, error, reload } = useFetch<ChatLog[]>("/chat/logs?limit=100");
  const [search, setSearch] = useState("");
  const [intent, setIntent] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const intents = [...new Set((data ?? []).map((l) => l.detected_intent).filter(Boolean) as string[])].sort();
  const q = search.toLowerCase();
  const rows = (data ?? []).filter(
    (l) =>
      (!intent || l.detected_intent === intent) &&
      (!q || l.question.toLowerCase().includes(q) || (l.user_email ?? "").toLowerCase().includes(q)),
  );

  return (
    <Panel
      title="AI Chat Audit Log"
      subtitle="Last 100 interactions · every question is logged with intent, source and latency"
      icon={<Bot />}
      bodyClassName="p-0"
      actions={
        <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
          Refresh
        </Button>
      }
    >
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row">
        <SearchInput value={search} onChange={setSearch} placeholder="Search question or user..." className="sm:w-72" />
        <NativeSelect value={intent} onChange={(e) => setIntent(e.target.value)} aria-label="Intent filter">
          <option value="">All intents</option>
          {intents.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </NativeSelect>
      </div>
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading audit log...">
        {rows.length === 0 ? (
          <EmptyState icon={<ScrollText className="size-6" />} title="No chat logs" />
        ) : (
          <div className="relative w-full overflow-x-auto">
            <table className="w-full min-w-max text-sm">
              <thead>
                <tr className="border-b border-border bg-slate-50/80 text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="w-8 px-3 py-2.5" />
                  <th className="px-4 py-2.5">Time</th>
                  <th className="px-4 py-2.5">User</th>
                  <th className="px-4 py-2.5">Question</th>
                  <th className="px-4 py-2.5">Intent</th>
                  <th className="px-4 py-2.5">Source</th>
                  <th className="px-4 py-2.5 text-right">Latency</th>
                  <th className="px-4 py-2.5">Result</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((l) => {
                  const open = expanded === l.id;
                  return (
                    <Fragment key={l.id}>
                      <tr
                        className={cn("cursor-pointer border-b border-border hover:bg-slate-50", open && "bg-slate-50")}
                        onClick={() => setExpanded(open ? null : l.id)}
                      >
                        <td className="px-3 py-2.5 text-ink-muted">
                          <button type="button" aria-expanded={open} aria-label={open ? "Collapse" : "Expand"} className="rounded p-0.5 hover:bg-slate-200">
                            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                          </button>
                        </td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-ink-muted">{formatDateTime(l.timestamp)}</td>
                        <td className="whitespace-nowrap px-4 py-2.5">{l.user_email ?? (l.user_id ? `User #${l.user_id}` : "—")}</td>
                        <td className="max-w-[340px] truncate px-4 py-2.5">{l.question}</td>
                        <td className="px-4 py-2.5">
                          {l.detected_intent ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">{l.detected_intent}</span> : "—"}
                        </td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-ink-muted">{l.data_source ?? "—"}</td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums text-ink-muted">
                          {l.response_time_ms !== null && l.response_time_ms !== undefined ? `${l.response_time_ms} ms` : "—"}
                        </td>
                        <td className="px-4 py-2.5">{l.error ? <StatusBadge status="failed" label="Error" /> : <StatusBadge status="active" label="OK" />}</td>
                      </tr>
                      {open && (
                        <tr className="border-b border-border bg-slate-50">
                          <td />
                          <td colSpan={7} className="px-4 pt-1 pb-4">
                            <p className="text-xs font-semibold text-ink-muted uppercase">Question</p>
                            <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{l.question}</p>
                            <p className="mt-3 text-xs font-semibold text-ink-muted uppercase">Response</p>
                            <p className="mt-1 max-w-4xl whitespace-pre-wrap text-sm text-ink">{l.response || "—"}</p>
                            {l.error && (
                              <>
                                <p className="mt-3 text-xs font-semibold text-danger uppercase">Error</p>
                                <p className="mt-1 whitespace-pre-wrap text-sm text-red-700">{l.error}</p>
                              </>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function PolicyTab() {
  const items = [
    { icon: Clock, title: "Working hours", lines: ["09:00 – 18:00 (9 hours incl. break)", "Standard day: 540 minutes"] },
    { icon: Timer, title: "Late & grace period", lines: ["15-minute grace period", "Check-in after 09:15 is marked late"] },
    { icon: ShieldCheck, title: "Overtime", lines: ["Overtime counts after 9 hours (540 min) of work", "Calculated by the system from check-in/out"] },
  ];
  const leaves = [
    { type: "Casual", days: 12 },
    { type: "Sick", days: 10 },
    { type: "Earned", days: 15 },
  ];
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <Panel title="Attendance policy" icon={<Clock />}>
        <ul className="flex flex-col gap-4">
          {items.map(({ icon: Icon, title, lines }) => (
            <li key={title} className="flex gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-light text-brand">
                <Icon className="size-4" />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">{title}</p>
                {lines.map((l) => (
                  <p key={l} className="text-sm text-ink-muted">
                    {l}
                  </p>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Leave entitlements" subtitle="Per calendar year" icon={<Palmtree />}>
        <div className="grid grid-cols-3 gap-3">
          {leaves.map((l) => (
            <div key={l.type} className="rounded-lg border border-border p-4 text-center">
              <p className="text-3xl font-bold text-navy">{l.days}</p>
              <p className="text-xs text-ink-muted">{l.type} leave days</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-ink-muted">
          Unpaid, maternity and paternity leave are granted as per company policy. These values are read-only here and are configured in the
          backend (<code className="rounded bg-slate-100 px-1 text-xs">LEAVE_ENTITLEMENTS</code>).
        </p>
      </Panel>
    </div>
  );
}
