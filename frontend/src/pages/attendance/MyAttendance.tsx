/**
 * "My attendance" tab (every role with an employee profile):
 * check-in hero · month summary (GET /attendance/summary) · interactive calendar (GET /attendance/me + /holidays) with a
 * day detail card and "Request correction" · own correction requests (GET /attendance/corrections/me, cancel pending) ·
 * the month's records table.
 */
import { useEffect, useMemo, useState } from "react";
import {
  AlarmClock,
  CalendarCheck,
  CalendarDays,
  CalendarOff,
  ChevronLeft,
  ChevronRight,
  Clock,
  FilePenLine,
  Hourglass,
  ListChecks,
  Palmtree,
  TimerReset,
  UserX,
} from "lucide-react";
import { AttendanceTable } from "@/components/AttendanceTable";
import { Panel } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState, ErrorState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { TodayAttendanceCard } from "@/components/TodayAttendanceCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Hint } from "@/components/ui/tooltip";
import { qs } from "@/lib/api";
import { formatDate, formatMinutes, formatNumber, formatTime, monthRange } from "@/lib/format";
import type { AttendanceCorrection, AttendanceRecord, AttendanceSummary } from "@/lib/types";
import { useFetch, type FetchState } from "@/lib/useFetch";
import { useHolidays } from "../leave/holidays";
import { AttendanceCalendar, dayKind, kindLabel } from "./AttendanceCalendar";
import { correctionBlock, type CorrectionContext } from "./CorrectionDialog";
import { MyCorrections } from "./MyCorrections";
import { monthName, monthOf, shiftMonth, weekdayName } from "./shared";

export function MyAttendance({
  records,
  corrections,
  ctx,
  onRequest,
}: {
  records: FetchState<AttendanceRecord[]>;
  corrections: FetchState<AttendanceCorrection[]>;
  ctx: CorrectionContext;
  onRequest: (iso: string | null) => void;
}) {
  const all = records.data ?? [];
  const currentMonth = ctx.today.slice(0, 7);
  const [month, setMonth] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  // Default to the latest month with records (or the current month)
  useEffect(() => {
    if (month !== null || records.loading) return;
    const latest = all.reduce<string | null>((acc, r) => (!acc || r.attendance_date > acc ? r.attendance_date : acc), null);
    const m = latest ? monthOf(latest) : currentMonth;
    setMonth(m);
    setSelected(ctx.today.startsWith(m) ? ctx.today : latest);
  }, [records.loading, all, month, currentMonth, ctx.today]);

  const shown = month ?? currentMonth;
  const [y, m] = shown.split("-").map(Number) as [number, number];
  const range = monthRange(m, y);
  const summary = useFetch<AttendanceSummary>(month ? `/attendance/summary${qs({ from_date: range.from, to_date: range.to })}` : null);
  const holidays = useHolidays([y]);
  const monthRecords = useMemo(() => all.filter((r) => r.attendance_date.startsWith(shown)), [all, shown]);
  const holidayNames = useMemo(() => new Map([...holidays.byDate].map(([d, h]) => [d, h.name])), [holidays.byDate]);

  const minMonth = ctx.joiningDate ? monthOf(ctx.joiningDate) : null;
  const canPrev = !minMonth || shown > minMonth;
  const canNext = shown < currentMonth;
  function go(delta: number) {
    const next = shiftMonth(shown, delta);
    setMonth(next);
    setSelected(null);
  }

  const s = summary.data;
  const reload = () => {
    records.reload();
    summary.reload();
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Hero: today + month summary */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <TodayAttendanceCard onChange={reload} />
        <div className="flex min-w-0 flex-col gap-3 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-foreground">Summary · {monthName(shown)}</h2>
            {summary.data && <span className="text-xs text-muted-foreground tabular-nums">{s?.total_days ?? 0} days recorded</span>}
          </div>
          {summary.error ? (
            <div className="rounded-xl border border-border bg-surface">
              <ErrorState message={summary.error} onRetry={summary.reload} className="py-8" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {(
                [
                  ["Present", s?.present_days, "present", <CalendarCheck key="i" />, `${s?.half_day_days ?? 0} half day${s?.half_day_days === 1 ? "" : "s"}`],
                  ["Late arrivals", s?.late_days, "late", <AlarmClock key="i" />, "Checked in after 09:15"],
                  ["Absent", s?.absent_days, "absent", <UserX key="i" />, undefined],
                  ["On leave", s?.leave_days, "leave", <Palmtree key="i" />, `${s?.holiday_days ?? 0} holiday${s?.holiday_days === 1 ? "" : "s"} · ${s?.weekend_days ?? 0} weekend days`],
                ] as const
              ).map(([label, v, tone, icon, hint]) => (
                <StatCard key={label} label={label} numeric={v ?? 0} tone={tone} icon={icon} hint={hint} loading={summary.loading || !month} />
              ))}
              <StatCard label="Worked" value={formatMinutes(s?.total_working_minutes ?? 0)} tone="brand" icon={<Clock />} loading={summary.loading || !month} hint="Total working time" />
              <StatCard
                label="Overtime"
                value={formatMinutes(s?.total_overtime_minutes ?? 0)}
                tone="half"
                icon={<TimerReset />}
                loading={summary.loading || !month}
                hint={`${formatNumber(s?.overtime_days ?? 0)} overtime day${s?.overtime_days === 1 ? "" : "s"}`}
              />
            </div>
          )}
        </div>
      </div>

      {/* Calendar + day detail + my requests */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Panel
          className="xl:col-span-2 xl:self-start"
          title="Calendar"
          subtitle="Select a day to see details or request a correction"
          icon={<CalendarDays />}
          actions={
            <div className="flex items-center gap-1">
              <Button variant="outline" size="icon-sm" onClick={() => go(-1)} disabled={!canPrev} aria-label="Previous month">
                <ChevronLeft />
              </Button>
              <span className="min-w-32 text-center text-sm font-medium text-foreground tabular-nums" aria-live="polite">
                {monthName(shown)}
              </span>
              <Button variant="outline" size="icon-sm" onClick={() => go(1)} disabled={!canNext} aria-label="Next month">
                <ChevronRight />
              </Button>
              {shown !== currentMonth && (
                <Button variant="ghost" size="sm" onClick={() => (setMonth(currentMonth), setSelected(ctx.today))}>
                  Today
                </Button>
              )}
            </div>
          }
        >
          {records.loading && !records.data ? (
            <div role="status" className="grid grid-cols-7 gap-1.5">
              <span className="sr-only">Loading calendar</span>
              {Array.from({ length: 35 }, (_, i) => (
                <Skeleton key={i} className="h-11 sm:h-16 lg:h-[4.5rem]" />
              ))}
            </div>
          ) : records.error ? (
            <ErrorState message={records.error} onRetry={records.reload} />
          ) : (
            <>
              {holidays.error && (
                <Notice tone="warning" className="mb-3">
                  Holidays couldn't be loaded ({holidays.error}).{" "}
                  <button type="button" className="font-medium underline underline-offset-2" onClick={holidays.reload}>
                    Retry
                  </button>
                </Notice>
              )}
              {ctx.paidMonths.has(shown) && (
                <Notice tone="info" icon={<CalendarOff />} className="mb-3">
                  Salary for {monthName(shown)} is paid, so this month's attendance is locked and can't be corrected.
                </Notice>
              )}
              <AttendanceCalendar
                month={shown}
                records={ctx.records}
                holidays={holidays.byDate}
                pending={ctx.pending}
                selected={selected}
                onSelect={setSelected}
                today={ctx.today}
              />
            </>
          )}
        </Panel>

        <div className="flex min-w-0 flex-col gap-5">
          <DayDetail iso={selected} ctx={ctx} holidayName={selected ? holidayNames.get(selected) : undefined} corrections={corrections.data ?? []} onRequest={onRequest} />
          <MyCorrections state={corrections} onRequest={() => onRequest(selected)} />
        </div>
      </div>

      <Panel title="Records" subtitle={monthName(shown)} icon={<ListChecks />} bodyClassName="p-0">
        <AsyncContent loading={records.loading && !records.data} error={records.error} onRetry={records.reload} loadingLabel="Loading records...">
          <AttendanceTable
            records={monthRecords}
            holidays={holidayNames}
            mobileCards
            empty={
              <EmptyState
                icon={<CalendarDays />}
                title={`No attendance in ${monthName(shown)}`}
                description="Days appear here once you check in or HR marks them. Missed a day?"
                action={
                  !correctionBlock(shown === currentMonth ? ctx.today : `${shown}-01`, ctx) ? (
                    <Button size="sm" variant="outline" onClick={() => onRequest(shown === currentMonth ? ctx.today : `${shown}-01`)}>
                      <FilePenLine /> Request correction
                    </Button>
                  ) : undefined
                }
              />
            }
            actions={(r) => {
              const block = correctionBlock(r.attendance_date, ctx);
              if (block) {
                return ctx.pending.has(r.attendance_date) ? (
                  <Hint label="Correction pending">
                    <span className="inline-flex size-8 items-center justify-center text-status-late-fg" tabIndex={0} aria-label="Correction pending">
                      <Hourglass className="size-4" />
                    </span>
                  </Hint>
                ) : null;
              }
              return (
                <Hint label="Request correction">
                  <Button variant="ghost" size="icon-sm" aria-label={`Request correction for ${formatDate(r.attendance_date)}`} onClick={() => onRequest(r.attendance_date)}>
                    <FilePenLine />
                  </Button>
                </Hint>
              );
            }}
          />
        </AsyncContent>
      </Panel>
    </div>
  );
}

function DayDetail({
  iso,
  ctx,
  holidayName,
  corrections,
  onRequest,
}: {
  iso: string | null;
  ctx: CorrectionContext;
  holidayName?: string;
  corrections: AttendanceCorrection[];
  onRequest: (iso: string | null) => void;
}) {
  if (!iso) {
    return (
      <Panel title="Day details" icon={<CalendarDays />}>
        <EmptyState className="py-6" icon={<CalendarDays />} title="Pick a day" description="Select a day in the calendar to see its times or request a correction." />
      </Panel>
    );
  }
  const rec = ctx.records.get(iso);
  const dow = new Date(`${iso}T00:00:00`).getDay();
  const kind = dayKind(rec, holidayName ? { id: null, date: iso, name: holidayName, kind: "", weekday: "" } : undefined, dow === 0 || dow === 6);
  const block = correctionBlock(iso, ctx);
  const latest = corrections.find((c) => c.attendance_date === iso);
  const future = iso > ctx.today;

  return (
    <Panel title={formatDate(iso)} subtitle={weekdayName(iso)} icon={<CalendarDays />} actions={!future ? <StatusBadge status={kind === "none" ? "not_marked" : kind} label={kindLabel(kind)} /> : undefined}>
      {holidayName && <p className="mb-3 text-sm font-medium text-foreground">{holidayName} · holiday</p>}
      {future ? (
        <p className="text-sm text-muted-foreground">This day is in the future.</p>
      ) : (
        <dl className="grid grid-cols-3 gap-2 text-center">
          {[
            ["In", formatTime(rec?.in_time)],
            ["Out", formatTime(rec?.out_time)],
            ["Worked", rec?.working_minutes ? formatMinutes(rec.working_minutes) : "—"],
            ["Late", rec && rec.late_minutes > 0 ? formatMinutes(rec.late_minutes) : "—"],
            ["Overtime", rec && rec.overtime_minutes > 0 ? formatMinutes(rec.overtime_minutes) : "—"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-surface-muted px-2 py-2">
              <dt className="text-[11px] font-medium text-muted-foreground">{k}</dt>
              <dd className="mt-0.5 text-sm font-semibold text-foreground tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {latest && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          Correction request <StatusBadge status={latest.status} />
          <span className="tabular-nums">
            {formatTime(latest.requested_in_time)}–{formatTime(latest.requested_out_time)}
          </span>
        </p>
      )}
      {!future &&
        (block ? (
          <p className="mt-3 text-xs text-muted-foreground">{block}</p>
        ) : (
          <Button variant="outline" size="sm" className="mt-3 w-full" onClick={() => onRequest(iso)}>
            <FilePenLine /> Request correction for this day
          </Button>
        ))}
    </Panel>
  );
}
