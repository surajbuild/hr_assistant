/**
 * Employee profile building blocks (cover header, key facts, skeleton, small stat tiles).
 * Used by EmployeeDetailPage (/employees/:id and /my-profile). Real data only — tenure is derived from joining_date.
 */
import type { ReactNode } from "react";
import { Briefcase, Building2, CalendarDays, Hash, Mail, UserRound, Wallet } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { RoleBadge, StatusBadge } from "@/components/StatusBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatINR, parseDate } from "@/lib/format";
import { Link } from "@/lib/router";
import type { Employee } from "@/lib/types";
import { cn } from "@/lib/utils";

/** "2y 3m" from an ISO joining date (null when the date is missing or in the future). */
export function tenure(joining: string | null | undefined, today = new Date()): string | null {
  const d = parseDate(joining);
  if (!d || d > today) return null;
  let months = (today.getFullYear() - d.getFullYear()) * 12 + (today.getMonth() - d.getMonth());
  if (today.getDate() < d.getDate()) months -= 1;
  if (months < 1) return "less than a month";
  const y = Math.floor(months / 12);
  const m = months % 12;
  return [y ? `${y}y` : "", m ? `${m}m` : ""].filter(Boolean).join(" ");
}

/** Plain card surface (same look as Panel without a header). */
export function Surface({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn("min-w-0 rounded-xl border border-border bg-surface", className)}>{children}</section>;
}

/** Small metric tile: coloured dot · label · tabular value. */
export function MiniStat({ label, value, color, hint }: { label: string; value: ReactNode; color?: string; hint?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-lg bg-surface-muted px-3 py-2.5">
      <p className="flex items-center gap-1.5 truncate text-xs font-medium text-muted-foreground">
        {color && <span className="size-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />}
        {label}
      </p>
      <p className="mt-0.5 text-xl leading-7 font-semibold tracking-tight text-foreground tabular-nums">{value}</p>
      {hint && <p className="truncate text-[11px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

interface Fact {
  icon: typeof Hash;
  label: string;
  value: ReactNode;
  title?: string;
}

/**
 * Cover band + overlapping avatar + identity + key facts.
 * `managerHref` is only passed when the viewer may open the manager's profile (avoids a link the API would refuse).
 */
export function ProfileHeader({
  emp,
  email,
  role,
  managerHref,
  showSalary,
  actions,
}: {
  emp: Employee;
  email?: string | null;
  role?: string | null;
  managerHref?: string | null;
  /** Salary structure — only when the viewer may see it (self or HR/Admin, D-021). */
  showSalary: boolean;
  actions?: ReactNode;
}) {
  const since = tenure(emp.joining_date);
  const managerName = emp.manager_name ?? (emp.manager_id ? `Employee #${emp.manager_id}` : null);
  const facts: Fact[] = [
    { icon: Hash, label: "Employee code", value: emp.employee_code },
    { icon: Building2, label: "Department", value: emp.department ?? "—" },
    { icon: Briefcase, label: "Designation", value: emp.designation ?? "—" },
    {
      icon: CalendarDays,
      label: "Joined",
      value: (
        <>
          <span className="tabular-nums">{formatDate(emp.joining_date)}</span>
          {since && <span className="font-normal text-muted-foreground"> · {since}</span>}
        </>
      ),
    },
    {
      icon: UserRound,
      label: "Reports to",
      value: managerName ? (
        managerHref ? (
          <Link to={managerHref} className="rounded-sm text-brand-subtle-foreground underline-offset-4 hover:underline">
            {managerName}
          </Link>
        ) : (
          managerName
        )
      ) : (
        <span className="text-muted-foreground">No manager</span>
      ),
    },
    {
      icon: Mail,
      label: "Work email",
      title: email ?? undefined,
      value: email ? (
        <a href={`mailto:${email}`} className="rounded-sm underline-offset-4 hover:underline">
          {email}
        </a>
      ) : (
        <span className="text-muted-foreground">No login account</span>
      ),
    },
  ];
  if (showSalary && emp.monthly_gross_salary != null) {
    facts.push({ icon: Wallet, label: "Monthly gross (confidential)", value: <span className="tabular-nums">{formatINR(emp.monthly_gross_salary)}</span> });
  }

  return (
    <Surface className="overflow-hidden">
      <div className="h-20 bg-brand-subtle sm:h-24" aria-hidden="true" />
      <div className="px-4 pb-5 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex min-w-0 items-end gap-4">
            <Avatar name={emp.name} size="xl" className="-mt-10 ring-4 ring-surface" />
            <div className="min-w-0 pb-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-xl leading-7 font-semibold tracking-tight text-foreground">{emp.name}</h2>
                <StatusBadge status={emp.status} />
                {role && <RoleBadge role={role} />}
              </div>
              <p className="line-clamp-2 text-sm text-muted-foreground sm:truncate">{[emp.designation, emp.department].filter(Boolean).join(" · ") || emp.employee_code}</p>
            </div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>

        <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-4 border-t border-border pt-5 min-[480px]:grid-cols-2 lg:grid-cols-3">
          {facts.map(({ icon: Icon, label, value, title }) => (
            // dt/dd must be direct children of the item div (axe dlitem), so the icon lives inside <dt>.
            <div key={label} className="relative min-h-8 min-w-0 pl-11">
              <dt className="text-xs font-medium text-muted-foreground">
                <span className="absolute top-0 left-0 flex size-8 items-center justify-center rounded-lg bg-surface-muted text-muted-foreground">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                {label}
              </dt>
              <dd className="truncate text-sm font-medium text-foreground" title={title}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </Surface>
  );
}

export function ProfileSkeleton() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-5">
      <span className="sr-only">Loading profile</span>
      <Surface className="overflow-hidden">
        <Skeleton className="h-20 rounded-none sm:h-24" />
        <div className="px-4 pb-5 sm:px-6">
          <div className="flex items-end gap-4">
            <Skeleton className="-mt-10 size-20 rounded-full ring-4 ring-surface" />
            <div className="flex flex-1 flex-col gap-2 pb-1">
              <Skeleton className="h-5 w-48 max-w-full" />
              <Skeleton className="h-3.5 w-64 max-w-full" />
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 border-t border-border pt-5 min-[480px]:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="size-8 shrink-0" />
                <div className="flex flex-1 flex-col gap-1.5">
                  <Skeleton className="h-3 w-1/3" />
                  <Skeleton className="h-3.5 w-2/3" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </Surface>
      <Skeleton className="h-10 w-full max-w-md" />
      <div className="grid gap-5 lg:grid-cols-3">
        <Skeleton className="h-64 lg:col-span-2" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
