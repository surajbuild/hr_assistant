/**
 * Notification bell — only for approver roles (admin / hr / manager) and only backed by REAL data:
 * - pending leave requests THIS user may decide (GET /leaves?status=pending, own requests excluded,
 *   matching the Leave page's approvals queue), and
 * - pending attendance correction requests (GET /attendance/corrections?status=pending — the backend
 *   already limits it to the caller's team / everyone and excludes the caller's own requests, D-033).
 * Employees get no bell: there is no notification endpoint for them.
 */
import { useEffect } from "react";
import { Bell, CalendarClock } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useAuth } from "@/lib/auth";
import { formatDate, humanize } from "@/lib/format";
import { Link, useRoute } from "@/lib/router";
import type { AttendanceCorrection, LeaveListItem } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

function asList<T>(data: T[] | { items: T[] } | null): T[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.items ?? []);
}

interface PendingItem {
  key: string;
  name: string;
  detail: string;
  to: string;
  sortDate: string;
}

export function NotificationBell() {
  const { role, user } = useAuth();
  const { pathname } = useRoute();
  const approver = role === "admin" || role === "hr" || role === "manager";
  const leaves = useFetch<LeaveListItem[] | { items: LeaveListItem[] }>(approver ? "/leaves?status=pending" : null);
  const corrections = useFetch<AttendanceCorrection[]>(approver ? "/attendance/corrections?status=pending" : null);
  const reloadLeaves = leaves.reload;
  const reloadCorrections = corrections.reload;

  // keep the badge fresh: after navigation and once a minute
  useEffect(() => {
    if (!approver) return;
    reloadLeaves();
    reloadCorrections();
  }, [pathname, approver, reloadLeaves, reloadCorrections]);
  useEffect(() => {
    if (!approver) return;
    const t = setInterval(() => {
      reloadLeaves();
      reloadCorrections();
    }, 60_000);
    return () => clearInterval(t);
  }, [approver, reloadLeaves, reloadCorrections]);

  if (!approver) return null;
  const myId = user?.employee?.id;
  const pendingLeaves = asList(leaves.data).filter((l) => l.employee_id !== myId);
  const pendingCorrections = asList(corrections.data).filter((c) => c.employee_id !== myId);
  const items: PendingItem[] = [
    ...pendingLeaves.map((l) => ({
      key: `leave-${l.id}`,
      name: l.employee_name,
      detail: `${humanize(l.leave_type)} leave · ${formatDate(l.from_date)}${l.to_date !== l.from_date ? ` – ${formatDate(l.to_date)}` : ""}`,
      to: "/leave",
      sortDate: l.applied_at ?? l.from_date,
    })),
    ...pendingCorrections.map((c) => ({
      key: `correction-${c.id}`,
      name: c.employee_name,
      detail: `Attendance correction · ${formatDate(c.attendance_date)}`,
      to: "/attendance",
      sortDate: c.requested_at,
    })),
  ].sort((a, b) => (a.sortDate < b.sortDate ? 1 : -1));
  const count = items.length;

  return (
    <Popover
      onOpenChange={(o) => {
        if (o) {
          reloadLeaves();
          reloadCorrections();
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={count ? `Notifications: ${count} pending requests` : "Notifications"}
          className="relative inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Bell className="size-[18px]" />
          {count > 0 && (
            <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] leading-4 font-semibold text-brand-foreground tabular-nums">
              {count > 9 ? "9+" : count}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-semibold text-foreground">Pending approvals</p>
          <span className="text-xs text-muted-foreground tabular-nums">{count}</span>
        </div>
        {count === 0 ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <span className="flex size-10 items-center justify-center rounded-xl bg-surface-muted text-muted-foreground">
              <CalendarClock className="size-5" />
            </span>
            <p className="text-sm font-medium text-foreground">All caught up</p>
            <p className="text-xs text-muted-foreground">No leave or attendance requests are waiting for you.</p>
          </div>
        ) : (
          <ul className="max-h-72 divide-y divide-border overflow-y-auto">
            {items.slice(0, 8).map((item) => (
              <li key={item.key}>
                <Link to={item.to} className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-accent">
                  <Avatar name={item.name} size="sm" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{item.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{item.detail}</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <div className="grid grid-cols-2 gap-1 border-t border-border p-2">
          <Button asChild variant="ghost" size="sm" className="justify-center">
            <Link to="/leave">Leave ({pendingLeaves.length})</Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="justify-center">
            <Link to="/attendance">Attendance ({pendingCorrections.length})</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
