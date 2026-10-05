/** Today's attendance card with Check In / Check Out (GET /attendance/today, POST /attendance/check-in|check-out). */
import { useEffect, useState } from "react";
import { Clock, LogIn, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatMinutes, formatTime, toISODate } from "@/lib/format";
import type { AttendanceRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { ErrorState, Spinner } from "./States";
import { StatusBadge } from "./StatusBadge";
import { useToast } from "./Toast";

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function TodayAttendanceCard({ onChange, className }: { onChange?: (rec: AttendanceRecord) => void; className?: string }) {
  const toast = useToast();
  const now = useClock();
  const { data, loading, error, reload, setData } = useFetch<AttendanceRecord | null>("/attendance/today");
  const [busy, setBusy] = useState<"in" | "out" | null>(null);

  const record = data ?? null;
  const checkedIn = !!record?.in_time;
  const checkedOut = !!record?.out_time;

  async function act(kind: "in" | "out") {
    setBusy(kind);
    try {
      const rec = await api.post<AttendanceRecord>(kind === "in" ? "/attendance/check-in" : "/attendance/check-out");
      setData(rec);
      onChange?.(rec);
      toast.success(kind === "in" ? `Checked in at ${formatTime(rec?.in_time)}` : `Checked out at ${formatTime(rec?.out_time)}`);
    } catch (err) {
      toast.error(errorMessage(err, kind === "in" ? "Check-in failed." : "Check-out failed."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={`hr-card flex flex-col p-5 ${className ?? ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">Today</p>
          <p className="mt-0.5 text-sm font-semibold text-ink">{formatDate(toISODate(now))}</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-1.5 text-lg font-bold tabular-nums text-navy">
          <Clock className="size-4 text-ink-muted" />
          {String(now.getHours()).padStart(2, "0")}:{String(now.getMinutes()).padStart(2, "0")}
        </div>
      </div>

      {loading ? (
        <div className="flex flex-1 items-center justify-center py-8">
          <Spinner className="size-6 text-brand" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={reload} className="py-6" />
      ) : (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-slate-50 px-2 py-2.5">
              <p className="text-[11px] text-ink-muted">Check in</p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums text-ink">{formatTime(record?.in_time)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 px-2 py-2.5">
              <p className="text-[11px] text-ink-muted">Check out</p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums text-ink">{formatTime(record?.out_time)}</p>
            </div>
            <div className="rounded-lg bg-slate-50 px-2 py-2.5">
              <p className="text-[11px] text-ink-muted">Worked</p>
              <p className="mt-0.5 text-sm font-semibold tabular-nums text-ink">
                {record?.working_minutes ? formatMinutes(record.working_minutes) : "—"}
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-ink-muted">
            Status:{" "}
            {record ? <StatusBadge status={record.late_minutes > 0 && record.status === "present" ? "late" : record.status} /> : <StatusBadge status="not_marked" />}
            {record && record.late_minutes > 0 && <span>· {formatMinutes(record.late_minutes)} late</span>}
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button onClick={() => act("in")} disabled={checkedIn || busy !== null} className="bg-success hover:bg-success/90">
              {busy === "in" ? <Spinner /> : <LogIn className="size-4" />} Check In
            </Button>
            <Button onClick={() => act("out")} disabled={!checkedIn || checkedOut || busy !== null} variant="outline">
              {busy === "out" ? <Spinner /> : <LogOut className="size-4" />} Check Out
            </Button>
          </div>
          {checkedOut && <p className="mt-2 text-center text-xs text-success">You have completed today's attendance.</p>}
        </>
      )}
    </section>
  );
}
