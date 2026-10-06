/**
 * Attendance
 * - My attendance (everyone): check-in hero, month summary, calendar with holidays, correction requests (D-033).
 * - Daily view & Records (admin / hr / manager-team); Records are server-paginated (D-035), HR/Admin can edit a record.
 * - Corrections (admin / hr / manager): approve or reject correction requests (own requests never listed).
 * - Mark attendance (admin / hr).
 * Tabs are deep-linkable: /attendance?tab=my|daily|records|corrections.
 */
import { useEffect, useMemo, useState } from "react";
import { CalendarCheck, CalendarClock, ClipboardCheck, FilePenLine, ListChecks, Plus, UserX } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/States";
import { Tabs } from "@/components/Tabs";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { toISODate } from "@/lib/format";
import { navigate, useRoute } from "@/lib/router";
import type { AttendanceCorrection, AttendanceRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { CorrectionDialog, type CorrectionContext } from "./attendance/CorrectionDialog";
import { CorrectionsQueue } from "./attendance/CorrectionsQueue";
import { DailyView } from "./attendance/DailyView";
import { MarkAttendanceDialog } from "./attendance/MarkAttendanceDialog";
import { MyAttendance } from "./attendance/MyAttendance";
import { RecordsView } from "./attendance/RecordsView";
import { pendingByDate, useMyPaidMonths } from "./attendance/shared";

type TabKey = "my" | "daily" | "records" | "corrections";

export function AttendancePage() {
  const { role, user } = useAuth();
  const { query } = useRoute();
  const isStaff = role === "admin" || role === "hr" || role === "manager";
  const canMark = role === "admin" || role === "hr";
  const employee = user?.employee ?? null;
  const ownEmployeeId = employee?.id;

  const allowed: TabKey[] = isStaff ? ["daily", "my", "records", "corrections"] : ["my"];
  const requested = query.get("tab") as TabKey | null;
  const tab: TabKey = requested && allowed.includes(requested) ? requested : isStaff ? "daily" : "my";
  function setTab(t: TabKey) {
    navigate(`/attendance?tab=${t}`, { replace: true });
  }

  const [markOpen, setMarkOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [requestFor, setRequestFor] = useState<string | null | undefined>(undefined); // undefined = closed

  // Own data (needed by My attendance and the correction dialog)
  const records = useFetch<AttendanceRecord[]>(employee ? "/attendance/me" : null);
  const myCorrections = useFetch<AttendanceCorrection[]>(employee ? "/attendance/corrections/me" : null);
  const paidMonths = useMyPaidMonths(!!employee);
  const pendingQueue = useFetch<AttendanceCorrection[]>(isStaff ? "/attendance/corrections?status=pending" : null);
  const pendingCount = (pendingQueue.data ?? []).filter((c) => c.employee_id !== ownEmployeeId).length;

  const today = toISODate(new Date());
  const recordMap = useMemo(() => new Map((records.data ?? []).map((r) => [r.attendance_date, r])), [records.data]);
  const pendingMap = useMemo(() => pendingByDate(myCorrections.data), [myCorrections.data]);
  const ctx: CorrectionContext = useMemo(
    () => ({ records: recordMap, pending: pendingMap, paidMonths, joiningDate: employee?.joining_date ?? null, today }),
    [recordMap, pendingMap, paidMonths, employee?.joining_date, today],
  );

  // Keep the URL canonical when an unknown/forbidden tab was requested
  useEffect(() => {
    if (requested && !allowed.includes(requested)) navigate("/attendance", { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requested]);

  const tabs = [
    ...(isStaff ? [{ key: "daily" as const, label: "Daily view", icon: <CalendarClock /> }] : []),
    { key: "my" as const, label: "My attendance", icon: <CalendarCheck /> },
    ...(isStaff
      ? [
          { key: "records" as const, label: "Records", icon: <ListChecks /> },
          { key: "corrections" as const, label: "Corrections", icon: <ClipboardCheck />, count: pendingQueue.data ? pendingCount : undefined },
        ]
      : []),
  ];

  return (
    <>
      <PageHeader
        title="Attendance"
        subtitle={
          role === "manager"
            ? "Your attendance and your team's check-ins, records and correction requests"
            : isStaff
              ? "Check-ins, working hours, records and correction requests"
              : "Your check-ins, working hours and correction requests"
        }
        actions={
          <>
            {employee && (
              <Button variant="outline" onClick={() => setRequestFor(null)}>
                <FilePenLine /> Request correction
              </Button>
            )}
            {canMark && (
              <Button onClick={() => setMarkOpen(true)}>
                <Plus /> Mark attendance
              </Button>
            )}
          </>
        }
      />
      {tabs.length > 1 && <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5" />}

      <div key={refreshKey}>
        {tab === "my" &&
          (employee ? (
            <MyAttendance records={records} corrections={myCorrections} ctx={ctx} onRequest={(iso) => setRequestFor(iso)} />
          ) : (
            <div className="rounded-xl border border-border bg-surface">
              <EmptyState icon={<UserX />} title="No employee profile" description="Your login isn't linked to an employee record, so there is no personal attendance to show. Ask HR to link it." />
            </div>
          ))}
        {tab === "daily" && isStaff && <DailyView role={role} />}
        {tab === "records" && isStaff && <RecordsView canEdit={canMark} ownEmployeeId={ownEmployeeId} />}
        {tab === "corrections" && isStaff && <CorrectionsQueue role={role} ownEmployeeId={ownEmployeeId} onChanged={pendingQueue.reload} />}
      </div>

      {employee && (
        <CorrectionDialog
          open={requestFor !== undefined}
          initialDate={requestFor ?? null}
          ctx={ctx}
          onClose={() => setRequestFor(undefined)}
          onCreated={() => {
            setRequestFor(undefined);
            myCorrections.reload();
            if (tab !== "my") setTab("my");
          }}
        />
      )}
      {canMark && (
        <MarkAttendanceDialog
          open={markOpen}
          onClose={() => setMarkOpen(false)}
          onSaved={() => {
            setMarkOpen(false);
            records.reload();
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
