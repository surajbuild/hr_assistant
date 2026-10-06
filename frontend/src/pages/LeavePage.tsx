/**
 * Leave: balance rings · apply (right drawer) · my leaves (timeline, cancel pending) · approvals & all/team requests for
 * admin / hr / manager (never their own — D-022) · holiday calendar (everyone; HR/Admin manage company holidays, D-034).
 * Tabs are deep-linkable: /leave?tab=approvals|mine|all|holidays.
 */
import { useEffect, useState } from "react";
import { CalendarDays, CalendarHeart, CalendarPlus, ClipboardCheck, ListChecks, Palmtree } from "lucide-react";
import { LeaveBalanceGrid } from "@/components/LeaveBalanceGrid";
import { PageHeader, Panel } from "@/components/PageHeader";
import { AsyncContent, CardSkeletons, EmptyState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { navigate, useRoute } from "@/lib/router";
import type { Leave, LeaveBalance, LeaveListItem } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { ApplyLeaveDrawer } from "./leave/ApplyLeaveDrawer";
import { HolidaysTab } from "./leave/HolidaysTab";
import { AllRequests, ApprovalQueue } from "./leave/LeaveApprovals";
import { LeaveTimeline } from "./leave/LeaveTimeline";

type TabKey = "approvals" | "mine" | "all" | "holidays";

export function LeavePage() {
  const { role, user } = useAuth();
  const { query } = useRoute();
  const ownEmployeeId = user?.employee?.id;
  const hasProfile = !!user?.employee;
  const isApprover = role === "admin" || role === "hr" || role === "manager";
  const isManager = role === "manager";
  const canManageHolidays = role === "admin" || role === "hr";

  const allowed: TabKey[] = isApprover ? ["approvals", "mine", "all", "holidays"] : ["mine", "holidays"];
  const requested = query.get("tab") as TabKey | null;
  const tab: TabKey = requested && allowed.includes(requested) ? requested : isApprover ? "approvals" : "mine";
  const setTab = (t: TabKey) => navigate(`/leave?tab=${t}`, { replace: true });
  useEffect(() => {
    if (requested && !allowed.includes(requested)) navigate("/leave", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requested]);

  const [applyOpen, setApplyOpen] = useState(false);
  const balance = useFetch<LeaveBalance[]>(hasProfile ? "/leaves/balance/me" : null);
  const mine = useFetch<Leave[]>(hasProfile ? "/leaves/me" : null);
  const pending = useFetch<LeaveListItem[]>(isApprover ? "/leaves?status=pending" : null);
  // Nobody approves their own request (the API refuses it too) — keep it out of the queue
  const allPending = pending.data ?? [];
  const queue = allPending.filter((l) => l.employee_id !== ownEmployeeId);
  const ownPendingCount = allPending.length - queue.length;

  const tabs = [
    ...(isApprover ? [{ key: "approvals" as const, label: isManager ? "Team approvals" : "Approvals", icon: <ClipboardCheck />, count: pending.data ? queue.length : undefined }] : []),
    { key: "mine" as const, label: "My leaves", icon: <CalendarDays /> },
    ...(isApprover ? [{ key: "all" as const, label: isManager ? "Team leaves" : "All requests", icon: <ListChecks /> }] : []),
    { key: "holidays" as const, label: "Holidays", icon: <CalendarHeart /> },
  ];

  const year = balance.data?.[0]?.year;

  return (
    <>
      <PageHeader
        title="Leave"
        subtitle={isApprover ? "Balances, requests, approvals and the holiday calendar" : "Your balances, requests and the holiday calendar"}
        actions={
          hasProfile && (
            <Button onClick={() => setApplyOpen(true)}>
              <CalendarPlus /> Apply for leave
            </Button>
          )
        }
      />

      {hasProfile && (
        <Panel title="My balance" subtitle={year ? `Calendar year ${year} · working days` : "Current calendar year"} icon={<Palmtree />} className="mb-5">
          <AsyncContent
            loading={balance.loading && !balance.data}
            error={balance.error}
            onRetry={balance.reload}
            skeleton={<CardSkeletons count={6} className="grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6" itemClassName="h-[86px] p-3.5" />}
          >
            {(balance.data ?? []).length === 0 ? (
              <EmptyState className="py-6" icon={<Palmtree />} title="No leave balance available" description="Entitlements appear here once HR sets them up." />
            ) : (
              <LeaveBalanceGrid balances={balance.data ?? []} />
            )}
          </AsyncContent>
        </Panel>
      )}

      <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5" />

      {tab === "mine" &&
        (hasProfile ? (
          <LeaveTimeline
            state={mine}
            onApply={() => setApplyOpen(true)}
            onChanged={() => {
              mine.reload();
              balance.reload();
              if (isApprover) pending.reload();
            }}
          />
        ) : (
          <div className="rounded-xl border border-border bg-surface">
            <EmptyState icon={<CalendarDays />} title="No employee profile" description="Your login isn't linked to an employee record, so you can't apply for leave. Ask HR to link it." />
          </div>
        ))}
      {tab === "approvals" && isApprover && (
        <ApprovalQueue
          rows={queue}
          ownPendingCount={ownPendingCount}
          loading={pending.loading}
          error={pending.error}
          reload={pending.reload}
          isManager={isManager}
          onChanged={() => {
            pending.reload();
          }}
        />
      )}
      {tab === "all" && isApprover && <AllRequests ownEmployeeId={ownEmployeeId} isManager={isManager} onChanged={pending.reload} />}
      {tab === "holidays" && <HolidaysTab canManage={canManageHolidays} />}

      {hasProfile && (
        <ApplyLeaveDrawer
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
      )}
    </>
  );
}
