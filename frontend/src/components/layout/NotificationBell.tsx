/**
 * Notification bell — only for approver roles (admin / hr / manager) and only backed by REAL data:
 * pending leave requests that THIS user may decide (GET /leaves?status=pending, own requests excluded,
 * matching the Leave page's approvals queue). Employees get no bell: there is no notification endpoint for them.
 */
import { useEffect } from "react";
import { Bell, CalendarClock } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useAuth } from "@/lib/auth";
import { formatDate, humanize } from "@/lib/format";
import { Link, useRoute } from "@/lib/router";
import type { LeaveListItem } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

function asList(data: LeaveListItem[] | { items: LeaveListItem[] } | null): LeaveListItem[] {
  if (!data) return [];
  return Array.isArray(data) ? data : (data.items ?? []);
}

export function NotificationBell() {
  const { role, user } = useAuth();
  const { pathname } = useRoute();
  const approver = role === "admin" || role === "hr" || role === "manager";
  const { data, reload } = useFetch<LeaveListItem[] | { items: LeaveListItem[] }>(approver ? "/leaves?status=pending" : null);

  // keep the badge fresh: after navigation and once a minute
  useEffect(() => {
    if (approver) reload();
  }, [pathname, approver, reload]);
  useEffect(() => {
    if (!approver) return;
    const t = setInterval(reload, 60_000);
    return () => clearInterval(t);
  }, [approver, reload]);

  if (!approver) return null;
  const myId = user?.employee?.id;
  const pending = asList(data).filter((l) => l.employee_id !== myId);

  return (
    <Popover onOpenChange={(o) => o && reload()}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={pending.length ? `Notifications: ${pending.length} pending leave requests` : "Notifications"}
          className="relative inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Bell className="size-[18px]" />
          {pending.length > 0 && (
            <span className="absolute top-1 right-1 flex min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[10px] leading-4 font-semibold text-brand-foreground tabular-nums">
              {pending.length > 9 ? "9+" : pending.length}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-semibold text-foreground">Pending approvals</p>
          <span className="text-xs text-muted-foreground tabular-nums">{pending.length}</span>
        </div>
        {pending.length === 0 ? (
          <div className="flex flex-col items-center gap-1.5 px-4 py-8 text-center">
            <span className="flex size-10 items-center justify-center rounded-xl bg-surface-muted text-muted-foreground">
              <CalendarClock className="size-5" />
            </span>
            <p className="text-sm font-medium text-foreground">All caught up</p>
            <p className="text-xs text-muted-foreground">No leave requests are waiting for you.</p>
          </div>
        ) : (
          <ul className="max-h-72 divide-y divide-border overflow-y-auto">
            {pending.slice(0, 6).map((l) => (
              <li key={l.id}>
                <Link to="/leave" className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-accent">
                  <Avatar name={l.employee_name} size="sm" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{l.employee_name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {humanize(l.leave_type)} · {formatDate(l.from_date)}
                      {l.to_date !== l.from_date ? ` – ${formatDate(l.to_date)}` : ""}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <div className="border-t border-border p-2">
          <Button asChild variant="ghost" size="sm" className="w-full justify-center">
            <Link to="/leave">Open leave approvals</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
