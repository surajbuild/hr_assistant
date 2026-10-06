/**
 * Settings → Users & Roles (admin). GET /users · PATCH /users/{id} {role?, status?}.
 * Every change is confirmed in a dialog. The admin's own row has no actions — the API refuses changing your own
 * role or deactivating yourself — and a notice explains why.
 */
import { useMemo, useState } from "react";
import { KeyRound, MoreHorizontal, ShieldCheck, UserCheck, UserCog, UserMinus, Users } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { NativeSelect, SearchInput } from "@/components/Field";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { RoleBadge, StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import type { AppUser, Role } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";

/** GET /users also returns how the account signs in (not in the shared AppUser type). */
type UserRow = AppUser & { has_password?: boolean; has_google?: boolean };

const ROLES: Role[] = ["employee", "manager", "hr", "admin"];

const ROLE_INFO: Record<Role, { label: string; access: string }> = {
  employee: { label: "Employee", access: "Own profile, attendance, leave and payslips." },
  manager: { label: "Manager", access: "Own data plus direct reports; approves the team's leave. No team salaries." },
  hr: { label: "HR", access: "Company-wide HR data including payroll; manages employees, leave and documents." },
  admin: { label: "Admin", access: "Full access, including user management and the AI chat audit log." },
};

type RoleFilter = "" | Role;

function signInLabel(u: UserRow): string | null {
  if (u.has_password === undefined && u.has_google === undefined) return null;
  const parts = [u.has_password && "Password", u.has_google && "Google"].filter(Boolean);
  return parts.length ? parts.join(" + ") : "No sign-in method";
}

export function UsersTab() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload, setData } = useFetch<UserRow[]>("/users");
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("");
  const [statusFilter, setStatusFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [roleTarget, setRoleTarget] = useState<UserRow | null>(null);
  const [statusTarget, setStatusTarget] = useState<UserRow | null>(null);

  const all = data ?? [];
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const u of all) c[u.role] = (c[u.role] ?? 0) + 1;
    return c;
  }, [all]);

  const q = search.trim().toLowerCase();
  const rows = all.filter(
    (u) =>
      (!roleFilter || u.role === roleFilter) &&
      (!statusFilter || u.status === statusFilter) &&
      (!q || u.email.toLowerCase().includes(q) || (u.employee_name ?? "").toLowerCase().includes(q) || (u.employee_code ?? "").toLowerCase().includes(q)),
  );
  const hasFilters = !!(q || roleFilter || statusFilter);
  const isMe = (u: UserRow) => u.id === me?.user_id;

  async function patch(u: UserRow, body: { role?: Role; status?: "active" | "inactive" }): Promise<boolean> {
    setBusy(true);
    try {
      const updated = await api.patch<UserRow>(`/users/${u.id}`, body);
      setData((prev) => (prev ?? []).map((x) => (x.id === u.id ? { ...x, ...body, ...(updated ?? {}) } : x)));
      const who = u.employee_name ?? u.email;
      toast.success(body.role ? `${who} is now ${ROLE_INFO[body.role].label}.` : `${who} has been ${body.status === "active" ? "reactivated" : "deactivated"}.`);
      return true;
    } catch (err) {
      toast.error(errorMessage(err, "Could not update the user."));
      return false;
    } finally {
      setBusy(false);
    }
  }

  function clearFilters() {
    setSearch("");
    setRoleFilter("");
    setStatusFilter("");
  }

  function rowMenu(u: UserRow) {
    if (isMe(u)) return <span className="text-xs text-muted-foreground">—</span>;
    const name = u.employee_name ?? u.email;
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${name}`}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={() => setRoleTarget(u)}>
            <UserCog /> Change role…
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          {u.status === "active" ? (
            <DropdownMenuItem destructive onSelect={() => setStatusTarget(u)}>
              <UserMinus /> Deactivate
            </DropdownMenuItem>
          ) : (
            <DropdownMenuItem onSelect={() => setStatusTarget(u)}>
              <UserCheck /> Reactivate
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  function userCell(u: UserRow) {
    return (
      <div className="flex min-w-0 items-center gap-3">
        <Avatar name={u.employee_name ?? u.email} seed={u.id} />
        <div className="min-w-0">
          <p className="truncate font-medium text-foreground">
            {u.employee_name ?? "—"}
            {isMe(u) && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(you)</span>}
          </p>
          <p className="truncate text-xs text-muted-foreground">{u.email}</p>
        </div>
      </div>
    );
  }

  const statusTargetName = statusTarget?.employee_name ?? statusTarget?.email;

  return (
    <section className="rounded-xl border border-border bg-surface" aria-labelledby="users-title">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-1">
        <div className="flex min-w-0 items-center gap-2.5">
          <Users className="size-4 text-muted-foreground" aria-hidden="true" />
          <div>
            <h2 id="users-title" className="text-base font-semibold text-foreground">
              Users &amp; roles
            </h2>
            <p className="text-xs font-medium text-muted-foreground">Login accounts, their role and whether they can sign in</p>
          </div>
        </div>
      </header>

      <div className="flex flex-col gap-3 border-b border-border p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <SearchInput value={search} onChange={setSearch} placeholder="Search name, email or code..." className="md:w-72" />
          <NativeSelect value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status filter" className="md:w-40">
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </NativeSelect>
          <p className="text-sm text-muted-foreground tabular-nums md:ml-auto" aria-live="polite">
            {!loading && !error && `${rows.length} of ${all.length} user${all.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <Segmented<RoleFilter>
          label="Role filter"
          value={roleFilter}
          onChange={setRoleFilter}
          options={[
            { value: "", label: <>All {data && <span className="tabular-nums text-muted-foreground">{all.length}</span>}</> },
            ...ROLES.map((r) => ({
              value: r as RoleFilter,
              label: (
                <>
                  {ROLE_INFO[r].label} {data && <span className="tabular-nums text-muted-foreground">{counts[r] ?? 0}</span>}
                </>
              ),
            })),
          ]}
        />
      </div>

      <Notice tone="info" icon={<ShieldCheck />} className="mx-4 mt-4">
        You can't change your own role or deactivate your own account — another admin has to do that.
      </Notice>

      <div className="pt-2">
        <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading users...">
          <DataTable
            rows={rows}
            rowKey={(u) => u.id}
            pageSize={10}
            empty={
              <EmptyState
                icon={<Users />}
                title={hasFilters ? "No users match your filters" : "No login accounts yet"}
                description={hasFilters ? "Try a different search or clear the filters." : "Accounts are created from the employee form (optional login)."}
                action={
                  hasFilters ? (
                    <Button variant="outline" size="sm" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            }
            mobileCard={(u) => (
              <div className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">{userCell(u)}</div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <RoleBadge role={u.role} />
                  <StatusBadge status={u.status} />
                </div>
                {rowMenu(u)}
              </div>
            )}
            columns={[
              { key: "user", header: "User", sortValue: (u) => u.employee_name ?? u.email, render: userCell },
              { key: "code", header: "Employee", sortValue: (u) => u.employee_code, render: (u) => <span className="text-muted-foreground">{u.employee_code ?? "Not linked"}</span> },
              { key: "role", header: "Role", sortValue: (u) => ROLES.indexOf(u.role), render: (u) => <RoleBadge role={u.role} /> },
              {
                key: "signin",
                header: "Sign-in",
                render: (u) => (
                  <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                    <KeyRound className="size-3.5" aria-hidden="true" />
                    {signInLabel(u) ?? "—"}
                  </span>
                ),
              },
              { key: "status", header: "Status", sortValue: (u) => u.status, render: (u) => <StatusBadge status={u.status} /> },
              { key: "created", header: "Created", sortValue: (u) => u.created_at, render: (u) => <span className="text-muted-foreground tabular-nums">{formatDate(u.created_at)}</span> },
              { key: "actions", header: <span className="sr-only">Actions</span>, align: "right", render: (u) => <div className="flex justify-end">{rowMenu(u)}</div> },
            ]}
          />
        </AsyncContent>
      </div>

      <RoleDialog
        user={roleTarget}
        busy={busy}
        onCancel={() => setRoleTarget(null)}
        onConfirm={async (role) => {
          if (roleTarget && (await patch(roleTarget, { role }))) setRoleTarget(null);
        }}
      />

      <ConfirmDialog
        open={!!statusTarget}
        title={statusTarget?.status === "active" ? "Deactivate user?" : "Reactivate user?"}
        tone={statusTarget?.status === "active" ? "danger" : "default"}
        confirmLabel={statusTarget?.status === "active" ? "Deactivate" : "Reactivate"}
        busy={busy}
        message={
          statusTarget?.status === "active" ? (
            <>
              <strong className="text-foreground">{statusTargetName}</strong> loses access immediately and can no longer sign in. Their employee record
              and history are not affected.
            </>
          ) : (
            <>
              <strong className="text-foreground">{statusTargetName}</strong> will be able to sign in again as{" "}
              {statusTarget ? ROLE_INFO[statusTarget.role]?.label ?? statusTarget.role : ""}.
            </>
          )
        }
        onCancel={() => setStatusTarget(null)}
        onConfirm={async () => {
          if (statusTarget && (await patch(statusTarget, { status: statusTarget.status === "active" ? "inactive" : "active" }))) setStatusTarget(null);
        }}
      />
    </section>
  );
}

/** Role picker dialog: radio cards with what each role can access; confirm only when the role changes. */
function RoleDialog({
  user,
  busy,
  onCancel,
  onConfirm,
}: {
  user: UserRow | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (role: Role) => void;
}) {
  const [picked, setPicked] = useState<Role | null>(null);
  const [lastUser, setLastUser] = useState<number | null>(null);
  // reset the selection whenever the dialog opens for another user
  if ((user?.id ?? null) !== lastUser) {
    setLastUser(user?.id ?? null);
    setPicked(user?.role ?? null);
  }
  const changed = !!user && !!picked && picked !== user.role;
  const name = user?.employee_name ?? user?.email ?? "";

  return (
    <Modal
      open={!!user}
      onClose={busy ? () => undefined : onCancel}
      title="Change role"
      description={user ? `${name} · currently ${ROLE_INFO[user.role]?.label ?? user.role}` : undefined}
      size="md"
      footer={
        <>
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => picked && onConfirm(picked)} disabled={!changed} loading={busy}>
            Change role
          </Button>
        </>
      }
    >
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm text-muted-foreground">Permissions change immediately; their menu updates the next time they load the app.</legend>
        {ROLES.map((r) => {
          const checked = picked === r;
          return (
            <label
              key={r}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border px-3.5 py-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                checked ? "border-brand bg-brand-subtle" : "border-border hover:bg-accent",
              )}
            >
              <input
                type="radio"
                name="role"
                value={r}
                checked={checked}
                onChange={() => setPicked(r)}
                className="mt-0.5 size-4 accent-[var(--brand)]"
              />
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                  {ROLE_INFO[r].label}
                  {user?.role === r && <span className="text-xs font-normal text-muted-foreground">(current)</span>}
                </span>
                <span className="block text-xs text-muted-foreground">{ROLE_INFO[r].access}</span>
              </span>
            </label>
          );
        })}
      </fieldset>
      {changed && picked === "admin" && (
        <Notice tone="warning" className="mt-3">
          Admins get full access, including user management and every user's chat history in the audit log.
        </Notice>
      )}
      {changed && user && (user.role === "hr" || user.role === "admin") && picked !== "admin" && picked !== "hr" && (
        <Notice tone="info" className="mt-3">
          {name} will lose company-wide access, including payroll data.
        </Notice>
      )}
    </Modal>
  );
}
