/**
 * Departments — derived from employees.department (D-005). GET /departments (HR/Admin: all; Manager: own team only)
 * plus GET /employees (same scope) for the member avatars. Click a card → /employees?department=<name>.
 * KPIs: departments, headcount, active (share of headcount), people managers — all from the two responses.
 */
import { useMemo, useState } from "react";
import { ArrowRight, Building2, UserCheck, UserPlus, Users, UsersRound } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { SearchInput } from "@/components/Field";
import { PageHeader } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { StatCard } from "@/components/StatCard";
import { EmptyState, ErrorState } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatNumber } from "@/lib/format";
import { Link, navigate } from "@/lib/router";
import type { Department, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { Surface } from "./people/profile";

type SortKey = "name" | "size";
const MAX_AVATARS = 5;
const MAX_DESIGNATIONS = 4;

export function DepartmentsPage() {
  const { role } = useAuth();
  const canAdd = role === "admin" || role === "hr";
  const { data, loading, error, reload } = useFetch<Department[]>("/departments");
  const people = useFetch<Employee[]>("/employees");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("name");

  const all = data ?? [];
  const totalEmployees = all.reduce((s, d) => s + d.employee_count, 0);
  const totalActive = all.reduce((s, d) => s + d.active_count, 0);
  const managerCount = new Set(all.flatMap((d) => d.managers)).size;
  const largest = all.reduce<Department | null>((best, d) => (!best || d.employee_count > best.employee_count ? d : best), null);

  const membersByDept = useMemo(() => {
    const map = new Map<string, Employee[]>();
    for (const e of people.data ?? []) {
      if (!e.department) continue;
      const list = map.get(e.department) ?? [];
      list.push(e);
      map.set(e.department, list);
    }
    // active people first, then alphabetical
    for (const list of map.values()) list.sort((a, b) => Number(b.status === "active") - Number(a.status === "active") || a.name.localeCompare(b.name));
    return map;
  }, [people.data]);

  const q = search.trim().toLowerCase();
  const list = all
    .filter((d) => !q || d.name.toLowerCase().includes(q) || d.designations.some((x) => x.toLowerCase().includes(q)) || d.managers.some((m) => m.toLowerCase().includes(q)))
    .sort((a, b) => (sort === "size" ? b.employee_count - a.employee_count || a.name.localeCompare(b.name) : a.name.localeCompare(b.name)));

  return (
    <>
      <PageHeader
        title="Departments"
        subtitle={role === "manager" ? "Departments of you and your direct reports" : "Organisation structure derived from employee records"}
        actions={
          canAdd && (
            <Button variant="outline" onClick={() => navigate("/employees/add")}>
              <UserPlus /> Add employee
            </Button>
          )
        }
      />

      {loading ? (
        <DepartmentsSkeleton />
      ) : error ? (
        <Surface>
          <ErrorState message={error} onRetry={reload} />
        </Surface>
      ) : all.length === 0 ? (
        <Surface>
          <EmptyState
            icon={<Building2 />}
            title="No departments yet"
            description="Departments appear automatically once employees are assigned to one."
            action={
              canAdd ? (
                <Button size="sm" onClick={() => navigate("/employees/add")}>
                  <UserPlus /> Add employee
                </Button>
              ) : undefined
            }
          />
        </Surface>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Departments" numeric={all.length} icon={<Building2 />} tone="brand" hint={largest ? `Largest: ${largest.name}` : undefined} />
            <StatCard label="Employees" numeric={totalEmployees} icon={<Users />} tone="half" />
            <StatCard
              label="Active"
              numeric={totalActive}
              icon={<UserCheck />}
              tone="present"
              hint={totalEmployees > 0 ? `${formatNumber((totalActive / totalEmployees) * 100, 0)}% of headcount` : undefined}
            />
            <StatCard label="People managers" numeric={managerCount} icon={<UsersRound />} tone="leave" />
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <SearchInput value={search} onChange={setSearch} placeholder="Search department, role or manager..." className="sm:w-80" />
            <div className="flex items-center gap-3 sm:ml-auto">
              <p className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
                {list.length} of {all.length}
              </p>
              <Segmented<SortKey>
                label="Sort departments"
                value={sort}
                onChange={setSort}
                options={[
                  { value: "name", label: "A–Z" },
                  { value: "size", label: "Largest" },
                ]}
              />
            </div>
          </div>

          {list.length === 0 ? (
            <Surface>
              <EmptyState
                icon={<Building2 />}
                title="No departments match your search"
                description="Try a different name, designation or manager."
                action={
                  <Button variant="outline" size="sm" onClick={() => setSearch("")}>
                    Clear search
                  </Button>
                }
              />
            </Surface>
          ) : (
            <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              {list.map((d) => (
                <li key={d.name} className="min-w-0">
                  <DepartmentCard dept={d} members={membersByDept.get(d.name) ?? []} membersLoading={people.loading} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}

function DepartmentCard({ dept, members, membersLoading }: { dept: Department; members: Employee[]; membersLoading: boolean }) {
  const activePct = dept.employee_count > 0 ? (dept.active_count / dept.employee_count) * 100 : 0;
  const inactive = dept.employee_count - dept.active_count;
  const shown = members.slice(0, MAX_AVATARS);
  const extra = Math.max(0, dept.employee_count - shown.length);
  return (
    <Link
      to={`/employees${qs({ department: dept.name })}`}
      aria-label={`${dept.name}: ${dept.employee_count} employees, ${dept.active_count} active. View employees`}
      className="card-interactive group flex h-full flex-col gap-4 rounded-xl border border-border bg-surface p-5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-subtle text-brand-subtle-foreground">
            <Building2 className="size-5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-foreground">{dept.name}</h2>
            <p className="truncate text-xs text-muted-foreground">{dept.managers.length > 0 ? `Manager: ${dept.managers.join(", ")}` : "No people manager"}</p>
          </div>
        </div>
        <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-foreground" aria-hidden="true" />
      </div>

      <div>
        <div className="flex items-end justify-between gap-3">
          <p className="text-[28px] leading-9 font-semibold tracking-tight text-foreground tabular-nums">
            {dept.employee_count}
            <span className="ml-1.5 text-sm font-normal text-muted-foreground">{dept.employee_count === 1 ? "employee" : "employees"}</span>
          </p>
          <p className="pb-1 text-xs text-muted-foreground tabular-nums">
            <span className="font-semibold text-status-present-fg">{dept.active_count}</span> active
            {inactive > 0 && <> · {inactive} other</>}
          </p>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted" aria-hidden="true">
          <div className="h-full rounded-full bg-status-present" style={{ width: `${activePct}%` }} />
        </div>
      </div>

      <div className="flex min-h-7 items-center" aria-hidden="true">
        {membersLoading ? (
          <Skeleton className="h-7 w-28 rounded-full" />
        ) : shown.length > 0 ? (
          <div className="flex -space-x-1">
            {shown.map((m) => (
              <span key={m.id} title={m.name} className="rounded-full ring-2 ring-surface">
                <Avatar name={m.name} size="sm" />
              </span>
            ))}
            {extra > 0 && (
              <span className="flex size-7 items-center justify-center rounded-full bg-surface-muted text-[11px] font-semibold text-muted-foreground ring-2 ring-surface tabular-nums">
                +{extra}
              </span>
            )}
          </div>
        ) : null}
      </div>

      {dept.designations.length > 0 && (
        <ul className="mt-auto flex flex-wrap gap-1.5 border-t border-border pt-4" aria-label="Designations">
          {dept.designations.slice(0, MAX_DESIGNATIONS).map((x) => (
            <li key={x} className="max-w-full truncate rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              {x}
            </li>
          ))}
          {dept.designations.length > MAX_DESIGNATIONS && (
            <li className="rounded-full px-1 py-0.5 text-[11px] font-medium text-muted-foreground">+{dept.designations.length - MAX_DESIGNATIONS} more</li>
          )}
        </ul>
      )}
    </Link>
  );
}

function DepartmentsSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-5">
      <span className="sr-only">Loading departments</span>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-[104px] rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-9 w-full max-w-80" />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-60 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
