/** Departments (derived from employees.department): GET /departments. Click → employees filtered by department. */
import { useState } from "react";
import { ArrowRight, Building2, UserCheck, Users } from "lucide-react";
import { SearchInput } from "@/components/Field";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState } from "@/components/States";
import { qs } from "@/lib/api";
import { Link } from "@/lib/router";
import type { Department } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export function DepartmentsPage() {
  const { data, loading, error, reload } = useFetch<Department[]>("/departments");
  const [search, setSearch] = useState("");
  const all = data ?? [];
  const list = all.filter((d) => d.name.toLowerCase().includes(search.toLowerCase()));
  const totalEmployees = all.reduce((s, d) => s + d.employee_count, 0);
  const totalActive = all.reduce((s, d) => s + d.active_count, 0);

  return (
    <>
      <PageHeader title="Departments" subtitle="Organisation structure derived from employee records" />
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading departments...">
        <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
          <StatCard label="Departments" value={all.length} icon={<Building2 />} tone="navy" />
          <StatCard label="Employees" value={totalEmployees} icon={<Users />} tone="blue" />
          <StatCard label="Active" value={totalActive} icon={<UserCheck />} tone="green" />
        </div>

        <div className="mb-4 max-w-xs">
          <SearchInput value={search} onChange={setSearch} placeholder="Search departments..." />
        </div>

        {list.length === 0 ? (
          <div className="hr-card">
            <EmptyState icon={<Building2 className="size-6" />} title={search ? "No departments match your search" : "No departments yet"} />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {list.map((d) => (
              <Link
                key={d.name}
                to={`/employees${qs({ department: d.name })}`}
                className="hr-card group flex flex-col p-5 transition-shadow hover:border-brand/40 hover:shadow-md focus-visible:outline-2 focus-visible:outline-brand"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-light text-brand">
                      <Building2 className="size-5" />
                    </span>
                    <div className="min-w-0">
                      <h2 className="truncate font-semibold text-ink">{d.name}</h2>
                      <p className="truncate text-xs text-ink-muted">
                        {d.managers.length > 0 ? `Manager: ${d.managers.join(", ")}` : "No manager assigned"}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className="size-4 shrink-0 text-ink-muted transition-transform group-hover:translate-x-0.5 group-hover:text-brand" />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="text-xl font-bold text-ink">{d.employee_count}</p>
                    <p className="text-xs text-ink-muted">Employees</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="text-xl font-bold text-success">{d.active_count}</p>
                    <p className="text-xs text-ink-muted">Active</p>
                  </div>
                </div>
                {d.designations.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {d.designations.map((x) => (
                      <span key={x} className="rounded-full border border-border bg-white px-2 py-0.5 text-[11px] text-ink-muted">
                        {x}
                      </span>
                    ))}
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </AsyncContent>
    </>
  );
}
