/**
 * Check-in / check-out hero (GET /attendance/today, POST /attendance/check-in|check-out) with a live clock.
 * "Working for …" is derived client-side from the real check-in time; nothing here is invented.
 */
import { useEffect, useState } from "react";
import { LogIn, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatMinutes, formatTime, toISODate } from "@/lib/format";
import type { AttendanceRecord } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";
import { ErrorState } from "./States";
import { StatusBadge } from "./StatusBadge";
import { useToast } from "./Toast";

function useClock(ms: number) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Minutes since "HH:MM[:SS]" today, or null. */
function minutesSince(inTime: string | null | undefined, now: Date): number | null {
  const m = inTime ? /^(\d{1,2}):(\d{2})/.exec(inTime) : null;
  if (!m) return null;
  return Math.max(0, now.getHours() * 60 + now.getMinutes() - (Number(m[1]) * 60 + Number(m[2])));
}

export function TodayAttendanceCard({ onChange, className }: { onChange?: (rec: AttendanceRecord) => void; className?: string }) {
  const toast = useToast();
  const now = useClock(1000);
  const { data, loading, error, reload, setData } = useFetch<AttendanceRecord | null>("/attendance/today");
  const [busy, setBusy] = useState<"in" | "out" | null>(null);

  const record = data ?? null;
  const checkedIn = !!record?.in_time;
  const checkedOut = !!record?.out_time;
  const live = checkedIn && !checkedOut ? minutesSince(record?.in_time, now) : null;

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

  const state = checkedOut ? "Day complete" : checkedIn ? "Checked in" : "Not checked in";

  return (
    <section className={cn("hr-card flex flex-col p-5", className)} aria-label="Today's attendance">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{formatDate(toISODate(now))}</p>
        {record ? <StatusBadge status={record.late_minutes > 0 && record.status === "present" ? "late" : record.status} /> : <StatusBadge status="not_marked" />}
      </div>

      <p className="mt-2 text-[40px] leading-none font-semibold tracking-tight text-foreground tabular-nums" aria-label="Current time">
        {pad(now.getHours())}:{pad(now.getMinutes())}
        <span className="ml-1 text-xl font-medium text-muted-foreground">{pad(now.getSeconds())}</span>
      </p>
      <p className="mt-1.5 text-sm text-muted-foreground">
        {state}
        {live !== null && <> · working for {formatMinutes(live)}</>}
        {record && record.late_minutes > 0 && <> · {formatMinutes(record.late_minutes)} late</>}
      </p>

      {loading ? (
        <div className="mt-5 flex flex-col gap-3" role="status">
          <span className="sr-only">Loading today's attendance</span>
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-9 w-full" />
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={reload} className="py-6" />
      ) : (
        <>
          <dl className="mt-5 grid grid-cols-3 gap-2 text-center">
            {[
              ["Check in", formatTime(record?.in_time)],
              ["Check out", formatTime(record?.out_time)],
              ["Worked", record?.working_minutes ? formatMinutes(record.working_minutes) : "—"],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg bg-surface-muted px-2 py-2.5">
                <dt className="text-[11px] font-medium text-muted-foreground">{k}</dt>
                <dd className="mt-0.5 text-sm font-semibold text-foreground tabular-nums">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Button variant="success" onClick={() => act("in")} disabled={checkedIn || busy !== null} loading={busy === "in"}>
              {busy !== "in" && <LogIn />} Check in
            </Button>
            <Button variant="outline" onClick={() => act("out")} disabled={!checkedIn || checkedOut || busy !== null} loading={busy === "out"}>
              {busy !== "out" && <LogOut />} Check out
            </Button>
          </div>
          {checkedOut && <p className="mt-2.5 text-center text-xs text-status-present-fg">You have completed today's attendance.</p>}
        </>
      )}
    </section>
  );
}
