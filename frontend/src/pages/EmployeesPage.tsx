/** Employees list: search + department/status filters, view/edit/deactivate, CSV export. */
import { useEffect, useMemo, useState } from "react";
import { Download, Eye, Pencil, UserMinus, UserPlus, Users } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { NativeSelect, SearchInput } from "@/components/Field";
import { ConfirmDialog } from "@/components/Modal";
import { PageHeader } from "@/components/PageHeader";
import { AsyncContent, EmptyState } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCSV, formatDate, humanize } from "@/lib/format";
import { navigate, useRoute } from "@/lib/router";
import type { Department, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const STATUSES = ["active", "inactive", "on_notice", "terminated"];

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
  const debouncedSearch = useDebounced(search);

  // keep URL in sync (so filters survive reload / back)
  useEffect(() => {
    const next = `/employees${qs({ search: debouncedSearch, department, status })}`;
    if (next !== window.location.pathname + window.location.search) navigate(next, { replace: true });
  }, [debouncedSearch, department, status]);

  const { data, loading, error, reload } = useFetch<Employee[]>(
    `/employees${qs({ search: debouncedSearch, department, status })}`,
  );
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

  return (
    <>
      <PageHeader
        title="Employees"
        subtitle={role === "manager" ? "You and your direct reports" : "Manage employee records"}
        actions={
          <>
            <Button variant="outline" onClick={exportCSV} disabled={rows.length === 0} className="bg-white">
              <Download className="size-4" /> Export CSV
            </Button>
            {canEdit && (
              <Button onClick={() => navigate("/employees/add")}>
                <UserPlus className="size-4" /> Add Employee
              </Button>
            )}
          </>
        }
      />

      <div className="hr-card">
        <div className="flex flex-col gap-3 border-b border-border p-4 md:flex-row md:items-center">
          <SearchInput value={search} onChange={setSearch} placeholder="Search name or code..." className="md:max-w-xs md:flex-1" />
          <div className="grid grid-cols-2 gap-3 md:flex">
            <NativeSelect value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Department filter">
              <option value="">All departments</option>
              {deptNames.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </NativeSelect>
            <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
              <option value="">All statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </NativeSelect>
          </div>
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
          <p className="text-sm text-ink-muted md:ml-auto">{!loading && `${rows.length} employee${rows.length === 1 ? "" : "s"}`}</p>
        </div>

        <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading employees...">
          <DataTable
            rows={rows}
            rowKey={(e) => e.id}
            onRowClick={(e) => navigate(`/employees/${e.id}`)}
            empty={
              <EmptyState
                icon={<Users className="size-6" />}
                title={hasFilters ? "No employees match your filters" : "No employees yet"}
                description={hasFilters ? "Try a different search or clear the filters." : undefined}
              />
            }
            columns={[
              {
                key: "name",
                header: "Employee",
                render: (e) => (
                  <div className="flex items-center gap-3">
                    <Avatar name={e.name} />
                    <div>
                      <p className="font-medium text-ink">{e.name}</p>
                      <p className="text-xs text-ink-muted">
                        {e.employee_code}
                        {e.email ? ` · ${e.email}` : ""}
                      </p>
                    </div>
                  </div>
                ),
              },
              { key: "dept", header: "Department", render: (e) => e.department ?? "—" },
              { key: "desig", header: "Designation", render: (e) => e.designation ?? "—" },
              { key: "manager", header: "Manager", render: (e) => <span className="text-ink-muted">{e.manager_name ?? "—"}</span> },
              { key: "join", header: "Joining Date", render: (e) => formatDate(e.joining_date) },
              { key: "status", header: "Status", render: (e) => <StatusBadge status={e.status} /> },
              {
                key: "actions",
                header: <span className="sr-only">Actions</span>,
                align: "right",
                render: (e) => (
                  <div className="flex justify-end gap-1" onClick={(ev) => ev.stopPropagation()}>
                    <Button variant="ghost" size="icon-sm" onClick={() => navigate(`/employees/${e.id}`)} aria-label={`View ${e.name}`} title="View">
                      <Eye className="size-4" />
                    </Button>
                    {canEdit && (
                      <>
                        {/* Pencil always; deactivate hidden on your own row (the API refuses self-deactivation) */}
                        <Button variant="ghost" size="icon-sm" onClick={() => navigate(`/employees/${e.id}/edit`)} aria-label={`Edit ${e.name}`} title="Edit">
                          <Pencil className="size-4" />
                        </Button>
                        {e.id !== user?.employee?.id && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setToDelete(e)}
                          disabled={e.status === "inactive"}
                          aria-label={`Deactivate ${e.name}`}
                          title="Deactivate"
                          className="text-danger hover:bg-danger-light hover:text-danger"
                        >
                          <UserMinus className="size-4" />
                        </Button>
                        )}
                      </>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </AsyncContent>
      </div>

      <ConfirmDialog
        open={!!toDelete}
        title="Deactivate employee?"
        message={
          <>
            <strong className="text-ink">{toDelete?.name}</strong> will be marked inactive and their login disabled. Attendance, leave
            and salary history is preserved.
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
