/**
 * Excel reports (admin, hr): attendance, overtime, leave — GET /reports/{type}?month&year&department → .xlsx
 * (downloaded through `api.download`). The period defaults to the latest month with attendance (dashboard reference
 * date). There is no preview endpoint, so the cards describe each workbook's sheets instead of previewing data.
 */
import { useEffect, useState } from "react";
import { CalendarCheck, CalendarDays, CheckCircle2, Download, FileSpreadsheet, RefreshCw, Timer, type LucideIcon } from "lucide-react";
import { Field, MonthSelect, NativeSelect, YearSelect } from "@/components/Field";
import { PageHeader } from "@/components/PageHeader";
import { Notice } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage, qs } from "@/lib/api";
import { monthLabel } from "@/lib/format";
import type { DashboardSummary, Department } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

type ReportType = "attendance" | "overtime" | "leave";

interface ReportDef {
  type: ReportType;
  title: string;
  description: string;
  icon: LucideIcon;
  sheets: { name: string; detail: string }[];
}

/** Sheet contents mirror app/services/report_service.py. */
const REPORTS: ReportDef[] = [
  {
    type: "attendance",
    title: "Attendance report",
    description: "Per-employee attendance totals plus every daily record for the period.",
    icon: CalendarCheck,
    sheets: [
      { name: "Summary", detail: "Present, absent, half day, late count, working and OT minutes per employee" },
      { name: "Attendance Records", detail: "Date, check-in / out, working hours, late minutes, status" },
    ],
  },
  {
    type: "overtime",
    title: "Overtime report",
    description: "Overtime hours and the overtime pay they earn, using the payroll engine's rate.",
    icon: Timer,
    sheets: [
      { name: "Summary", detail: "OT hours and OT amount per employee, with totals" },
      { name: "Overtime Records", detail: "Each day with overtime, per employee" },
    ],
  },
  {
    type: "leave",
    title: "Leave report",
    description: "Leave requests that overlap the period, with working-day counts.",
    icon: CalendarDays,
    sheets: [{ name: "Leave Records", detail: "Leave type, from / to, leave days, status and reason" }],
  },
];

function isFuture(month: number, year: number): boolean {
  const now = new Date();
  return year > now.getFullYear() || (year === now.getFullYear() && month > now.getMonth() + 1);
}

export function ReportsPage() {
  const toast = useToast();
  const dash = useFetch<DashboardSummary>("/dashboard/summary");
  const depts = useFetch<Department[]>("/departments");
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const [touched, setTouched] = useState(false);
  const [department, setDepartment] = useState("");
  const [busy, setBusy] = useState<Partial<Record<ReportType, boolean>>>({});
  const [last, setLast] = useState<Partial<Record<ReportType, string>>>({});

  const refDate = dash.data?.reference_date;
  const ref = refDate ? refDate.split("-").map(Number) : null;
  const refMonth = ref?.[1];
  const refYear = ref?.[0];

  // Default to the latest month with data (dashboard reference date) until the user picks a period.
  useEffect(() => {
    if (touched || !refYear || !refMonth) return;
    setYear(refYear);
    setMonth(refMonth);
  }, [refYear, refMonth, touched]);

  const period = monthLabel(month, year);
  const atLatest = !!refYear && refYear === year && refMonth === month;

  async function download(type: ReportType) {
    setBusy((b) => ({ ...b, [type]: true }));
    try {
      const path = `/reports/${type}${qs({ month, year, department })}`;
      const fallback = `${type}_report_${year}_${String(month).padStart(2, "0")}.xlsx`;
      const filename = await api.download(path, fallback);
      setLast((l) => ({ ...l, [type]: filename }));
      toast.success(`Downloaded ${filename}`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to download report."));
    } finally {
      setBusy((b) => ({ ...b, [type]: false }));
    }
  }

  return (
    <>
      <PageHeader title="Reports" subtitle="Export HR data to Excel (.xlsx)" />

      <section className="hr-card mb-5 p-5" aria-labelledby="report-period">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 id="report-period" className="text-base font-semibold text-foreground">
              Report period
            </h2>
            <p className="text-xs font-medium text-muted-foreground" aria-live="polite">
              {dash.loading && !touched ? (
                "Finding the latest month with data…"
              ) : (
                <>
                  {period}
                  {department ? ` · ${department}` : " · All departments"}
                  {atLatest && " · latest month with data"}
                </>
              )}
            </p>
          </div>
          {refYear && refMonth && !atLatest && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setTouched(false);
                setYear(refYear);
                setMonth(refMonth);
              }}
            >
              Latest month with data
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Month">
            <MonthSelect
              value={month}
              onChange={(m) => {
                setTouched(true);
                setMonth(m);
              }}
              className="w-full"
            />
          </Field>
          <Field label="Year">
            <YearSelect
              value={year}
              onChange={(y) => {
                setTouched(true);
                setYear(y);
              }}
              className="w-full"
            />
          </Field>
          <Field
            label="Department"
            htmlFor="rep-dept"
            error={depts.error ? "Departments could not be loaded." : null}
            hint="Optional — limits every report to one department"
          >
            <div className="flex gap-2">
              <NativeSelect id="rep-dept" value={department} onChange={(e) => setDepartment(e.target.value)} className="w-full min-w-0" disabled={depts.loading}>
                <option value="">{depts.loading ? "Loading departments…" : "All departments"}</option>
                {(depts.data ?? []).map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.name}
                  </option>
                ))}
              </NativeSelect>
              {depts.error && (
                <Button variant="outline" size="icon" onClick={depts.reload} aria-label="Retry loading departments">
                  <RefreshCw />
                </Button>
              )}
            </div>
          </Field>
        </div>
        {isFuture(month, year) && (
          <Notice tone="warning" className="mt-4">
            {period} is in the future — the reports will be empty.
          </Notice>
        )}
      </section>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        {REPORTS.map(({ type, title, description, icon: Icon, sheets }) => {
          const isBusy = !!busy[type];
          return (
            <section key={type} className="hr-card flex flex-col p-5" aria-labelledby={`rep-${type}`} aria-busy={isBusy || undefined}>
              <div className="flex items-start gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-brand-subtle text-brand-subtle-foreground">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h2 id={`rep-${type}`} className="text-base font-semibold text-foreground">
                    {title}
                  </h2>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <FileSpreadsheet className="size-3.5" aria-hidden="true" /> Excel · {period}
                  </p>
                </div>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">{description}</p>
              <dl className="mt-4 flex flex-col gap-2 rounded-lg border border-border bg-surface-muted p-3">
                {sheets.map((s) => (
                  <div key={s.name}>
                    <dt className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                      <FileSpreadsheet className="size-3.5 text-muted-foreground" aria-hidden="true" /> {s.name}
                    </dt>
                    <dd className="pl-5 text-xs text-muted-foreground">{s.detail}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-auto pt-5">
                <Button className="w-full" onClick={() => download(type)} loading={isBusy} aria-label={`Download ${title.toLowerCase()} for ${period}`}>
                  {!isBusy && <Download />}
                  {isBusy ? "Preparing…" : "Download .xlsx"}
                </Button>
                {last[type] && (
                  <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
                    <CheckCircle2 className="size-3.5 shrink-0 text-status-present-fg" aria-hidden="true" />
                    <span className="truncate">Last downloaded: {last[type]}</span>
                  </p>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </>
  );
}
