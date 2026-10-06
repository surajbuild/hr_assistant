/**
 * Employees: search + department/status filters (kept in the URL), table ⇄ card view, sortable columns,
 * pagination, row menu (view / edit / deactivate), CSV export. API behaviour unchanged:
 * GET /employees?search&department&status · DELETE /employees/{id} (soft delete). Managers only get their team.
 */
import { useEffect, useMemo, useState } from "react";
import { Download, Eye, LayoutGrid, MoreHorizontal, Pencil, Rows3, UserMinus, UserPlus, Users } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable, Pagination } from "@/components/DataTable";
import { NativeSelect, SearchInput } from "@/components/Field";
import { ConfirmDialog } from "@/components/Modal";
import { PageHeader } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState, LoadingState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCSV, formatDate, humanize } from "@/lib/format";
import { navigate, useRoute } from "@/lib/router";
import type { Department, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "on_notice", label: "On notice" },
  { value: "terminated", label: "Terminated" },
];

const VIEW_KEY = "hr_employees_view";
type View = "table" | "cards";

function readView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "cards" ? "cards" : "table";
  } catch {
    return "table";
  }
}

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function EmployeesPage() {
  const { role, user } = useAuth();
  const canEdit = role === "admin" || role === "hr";
  const toast = useToast();
  const { query } = useRoute();

  const [search, setSearch] = useState(query.get("search") ?? "");
  const [department, setDepartment] = useState(query.get("department") ?? "");
  const [status, setStatus] = useState(query.get("status") ?? "");
  const [view, setViewState] = useState<View>(readView);
  const [page, setPage] = useState(0);
  const debouncedSearch = useDebounced(search);

  function setView(v: View) {
    setViewState(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* ignore */
    }
  }

  // keep URL in sync (so filters survive reload / back)
  useEffect(() => {
    const next = `/employees${qs({ search: debouncedSearch, department, status })}`;
    if (next !== window.location.pathname + window.location.search) navigate(next, { replace: true });
    setPage(0);
  }, [debouncedSearch, department, status]);

  const { data, loading, error, reload } = useFetch<Employee[]>(`/employees${qs({ search: debouncedSearch, department, status })}`);
  const depts = useFetch<Department[]>("/departments");
  const deptNames = useMemo(() => {
    const names = new Set<string>((depts.data ?? []).map((d) => d.name));
    if (department) names.add(department);
    return [...names].sort();
  }, [depts.data, department]);

  const [toDelete, setToDelete] = useState<Employee | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.del(`/employees/${toDelete.id}`);
      toast.success(`${toDelete.name} has been deactivated.`);
      setToDelete(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to deactivate employee."));
    } finally {
      setDeleting(false);
    }
  }

  const rows = data ?? [];

  function exportCSV() {
    downloadCSV(
      "employees.csv",
      ["Code", "Name", "Department", "Designation", "Joining Date", "Status", "Manager", "Email", "Role"],
      rows.map((e) => [e.employee_code, e.name, e.department, e.designation, e.joining_date, e.status, e.manager_name, e.email, e.role]),
    );
  }

  const hasFilters = !!(search || department || status);
  const CARD_PAGE = 12;
  const cardRows = rows.slice(page * CARD_PAGE, page * CARD_PAGE + CARD_PAGE);

  /** Row menu: view always; edit/deactivate for HR/Admin (deactivate hidden on your own row — the API refuses it). */
  function rowMenu(e: Employee) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${e.name}`} onClick={(ev) => ev.stopPropagation()}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent onClick={(ev) => ev.stopPropagation()}>
          <DropdownMenuItem onSelect={() => navigate(`/employees/${e.id}`)}>
            <Eye /> View profile
          </DropdownMenuItem>
          {canEdit && (
            <DropdownMenuItem onSelect={() => navigate(`/employees/${e.id}/edit`)}>
              <Pencil /> Edit
            </DropdownMenuItem>
          )}
          {canEdit && e.id !== user?.employee?.id && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive disabled={e.status === "inactive"} onSelect={() => setToDelete(e)}>
                <UserMinus /> Deactivate
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  const emptyState = (
    <EmptyState
      icon={<Users />}
      title={hasFilters ? "No employees match your filters" : "No employees yet"}
      description={hasFilters ? "Try a different search or clear the filters." : canEdit ? "Add your first employee to get started." : undefined}
      action={
        hasFilters ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSearch("");
              setDepartment("");
              setStatus("");
            }}
          >
            Clear filters
          </Button>
        ) : canEdit ? (
          <Button size="sm" onClick={() => navigate("/employees/add")}>
            <UserPlus /> Add employee
          </Button>
        ) : undefined
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Employees"
        subtitle={role === "manager" ? "You and your direct reports" : "Manage employee records"}
        actions={
          <>
            <Button variant="outline" onClick={exportCSV} disabled={rows.length === 0}>
              <Download /> Export CSV
            </Button>
            {canEdit && (
              <Button onClick={() => navigate("/employees/add")}>
                <UserPlus /> Add employee
              </Button>
            )}
          </>
        }
      />

      <div className="hr-card">
        <div className="flex flex-col gap-3 border-b border-border p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <SearchInput value={search} onChange={setSearch} placeholder="Search name or code..." className="md:w-72" />
            <NativeSelect value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Department filter" className="md:w-52">
              <option value="">All departments</option>
              {deptNames.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </NativeSelect>
            <div className="flex items-center gap-3 md:ml-auto">
              <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
                {!loading && `${rows.length} employee${rows.length === 1 ? "" : "s"}`}
              </p>
              <Segmented<View>
                label="View"
                value={view}
                onChange={setView}
                options={[
                  { value: "table", label: <Rows3 />, ariaLabel: "Table view" },
                  { value: "cards", label: <LayoutGrid />, ariaLabel: "Card view" },
                ]}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented label="Status filter" value={status} onChange={setStatus} options={STATUS_OPTIONS} />
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearch("");
                  setDepartment("");
                  setStatus("");
                }}
              >
                Clear filters
              </Button>
            )}
          </div>
        </div>

        <AsyncContent
          loading={loading}
          error={error}
          onRetry={reload}
          skeleton={
            view === "cards" ? (
              <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3" role="status">
                <span className="sr-only">Loading employees</span>
                {Array.from({ length: 6 }, (_, i) => (
                  <Skeleton key={i} className="h-36" />
                ))}
              </div>
            ) : (
              <LoadingState label="Loading employees..." rows={5} />
            )
          }
        >
          {rows.length === 0 ? (
            emptyState
          ) : view === "cards" ? (
            <>
              <ul className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-3">
                {cardRows.map((e) => (
                  <li key={e.id} className="relative">
                    <article
                      tabIndex={0}
                      onClick={() => navigate(`/employees/${e.id}`)}
                      onKeyDown={(ev) => {
                        if (ev.target === ev.currentTarget && (ev.key === "Enter" || ev.key === " ")) {
                          ev.preventDefault();
                          navigate(`/employees/${e.id}`);
                        }
                      }}
                      className="card-interactive flex h-full cursor-pointer flex-col gap-4 rounded-xl border border-border bg-surface p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`${e.name}, ${e.designation ?? "employee"}`}
                    >
                      <div className="flex items-start gap-3">
                        <Avatar name={e.name} size="lg" />
                        <div className="min-w-0 flex-1 pr-8">
                          <p className="truncate text-sm font-semibold text-foreground">{e.name}</p>
                          <p className="truncate text-xs text-muted-foreground">{e.designation ?? "—"}</p>
                          <p className="truncate text-xs text-muted-foreground">{e.employee_code}</p>
                        </div>
                      </div>
                      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
                        <dt className="text-muted-foreground">Department</dt>
                        <dd className="truncate text-right font-medium text-foreground">{e.department ?? "—"}</dd>
                        <dt className="text-muted-foreground">Manager</dt>
                        <dd className="truncate text-right font-medium text-foreground">{e.manager_name ?? "—"}</dd>
                        <dt className="text-muted-foreground">Joined</dt>
                        <dd className="text-right font-medium text-foreground tabular-nums">{formatDate(e.joining_date)}</dd>
                      </dl>
                      <div className="mt-auto">
                        <StatusBadge status={e.status} />
                      </div>
                    </article>
                    <div className="absolute top-3 right-3">
                      {rowMenu(e)}
                    </div>
                  </li>
                ))}
              </ul>
              <Pagination page={page} pageSize={CARD_PAGE} total={rows.length} onPage={setPage} />
            </>
          ) : (
            <DataTable
              rows={rows}
              rowKey={(e) => e.id}
              onRowClick={(e) => navigate(`/employees/${e.id}`)}
              pageSize={10}
              mobileCard={(e) => (
                <div
                  className="flex items-center gap-3 px-4 py-3"
                  onClick={() => navigate(`/employees/${e.id}`)}
                  role="link"
                  tabIndex={0}
                  onKeyDown={(ev) => ev.key === "Enter" && navigate(`/employees/${e.id}`)}
                  aria-label={`${e.name}, view profile`}
                >
                  <Avatar name={e.name} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{e.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{[e.designation, e.department].filter(Boolean).join(" · ") || e.employee_code}</p>
                  </div>
                  <StatusBadge status={e.status} />
                  {rowMenu(e)}
                </div>
              )}
              columns={[
                {
                  key: "name",
                  header: "Employee",
                  label: "employee",
                  sortValue: (e) => e.name,
                  render: (e) => (
                    <div className="flex items-center gap-3">
                      <Avatar name={e.name} />
                      <div>
                        <p className="font-medium text-foreground">{e.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {e.employee_code}
                          {e.email ? ` · ${e.email}` : ""}
                        </p>
                      </div>
                    </div>
                  ),
                },
                { key: "dept", header: "Department", sortValue: (e) => e.department, render: (e) => e.department ?? "—" },
                { key: "desig", header: "Designation", sortValue: (e) => e.designation, render: (e) => e.designation ?? "—" },
                { key: "manager", header: "Manager", render: (e) => <span className="text-muted-foreground">{e.manager_name ?? "—"}</span> },
                { key: "join", header: "Joined", label: "joining date", sortValue: (e) => e.joining_date, render: (e) => <span className="tabular-nums">{formatDate(e.joining_date)}</span> },
                { key: "status", header: "Status", sortValue: (e) => humanize(e.status), render: (e) => <StatusBadge status={e.status} /> },
                {
                  key: "actions",
                  header: <span className="sr-only">Actions</span>,
                  align: "right",
                  render: (e) => <div className="flex justify-end" onClick={(ev) => ev.stopPropagation()}>{rowMenu(e)}</div>,
                },
              ]}
            />
          )}
        </AsyncContent>
      </div>

      <ConfirmDialog
        open={!!toDelete}
        title="Deactivate employee?"
        message={
          <>
            <strong className="text-foreground">{toDelete?.name}</strong> will be marked inactive and their login disabled. Attendance, leave and salary history is preserved.
          </>
        }
        confirmLabel="Deactivate"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  );
}
