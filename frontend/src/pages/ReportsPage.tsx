/** Excel reports (admin, hr): attendance, overtime, leave — GET /reports/{type}?month&year&department → xlsx. */
import { useEffect, useState } from "react";
import { CalendarCheck, CalendarDays, Download, FileSpreadsheet, Filter, Timer } from "lucide-react";
import { Field, MonthSelect, NativeSelect, YearSelect } from "@/components/Field";
import { PageHeader, Panel } from "@/components/PageHeader";
import { Spinner } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { api, errorMessage, qs } from "@/lib/api";
import { monthLabel, monthRange } from "@/lib/format";
import type { DashboardSummary, Department } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

type ReportType = "attendance" | "overtime" | "leave";

const REPORTS: { type: ReportType; title: string; description: string; icon: typeof CalendarCheck; tone: string; columns: string[] }[] = [
  {
    type: "attendance",
    title: "Attendance Report",
    description: "Daily attendance with check-in/out, working hours, late minutes and status per employee.",
    icon: CalendarCheck,
    tone: "bg-emerald-50 text-emerald-600",
    columns: ["Employee", "Date", "In / Out", "Working hours", "Late", "Status"],
  },
  {
    type: "overtime",
    title: "Overtime Report",
    description: "Overtime minutes and hours per employee and day, with monthly totals.",
    icon: Timer,
    tone: "bg-blue-50 text-blue-600",
    columns: ["Employee", "Department", "Date", "Overtime", "Totals"],
  },
  {
    type: "leave",
    title: "Leave Report",
    description: "Leave requests by type and status with dates, duration and reasons.",
    icon: CalendarDays,
    tone: "bg-violet-50 text-violet-600",
    columns: ["Employee", "Type", "From / To", "Days", "Status", "Reason"],
  },
];

export function ReportsPage() {
  const toast = useToast();
  const dash = useFetch<DashboardSummary>("/dashboard/summary");
  const depts = useFetch<Department[]>("/departments");
  const [month, setMonth] = useState(9);
  const [year, setYear] = useState(2024);
  const [touched, setTouched] = useState(false);
  const [department, setDepartment] = useState("");
  const [busy, setBusy] = useState<ReportType | null>(null);

  // Default to the latest month with data (dashboard reference date), else Sep 2024 (seed range).
  useEffect(() => {
    if (touched || !dash.data?.reference_date) return;
    const [y, m] = dash.data.reference_date.split("-").map(Number);
    if (y && m) {
      setYear(y);
      setMonth(m);
    }
  }, [dash.data, touched]);

  async function download(type: ReportType) {
    setBusy(type);
    try {
      const { from, to } = monthRange(month, year);
      const path = `/reports/${type}${qs({ month, year, department, date_from: from, date_to: to })}`;
      const fallback = `${type}_report_${year}_${String(month).padStart(2, "0")}.xlsx`;
      const filename = await api.download(path, fallback);
      toast.success(`Downloaded ${filename}`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to download report."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <PageHeader title="Reports" subtitle="Export HR data to Excel (.xlsx)" />

      <Panel title="Report period" icon={<Filter />} className="mb-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Month" htmlFor="rep-month">
            <MonthSelect
              value={month}
              onChange={(m) => {
                setTouched(true);
                setMonth(m);
              }}
              className="w-full"
            />
          </Field>
          <Field label="Year" htmlFor="rep-year">
            <YearSelect
              value={year}
              onChange={(y) => {
                setTouched(true);
                setYear(y);
              }}
              className="w-full"
            />
          </Field>
          <Field label="Department" htmlFor="rep-dept" hint="Optional">
            <NativeSelect id="rep-dept" value={department} onChange={(e) => setDepartment(e.target.value)} className="w-full">
              <option value="">All departments</option>
              {(depts.data ?? []).map((d) => (
                <option key={d.name} value={d.name}>
                  {d.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
        </div>
        <p className="mt-3 text-xs text-ink-muted">
          Selected: <strong className="text-ink">{monthLabel(month, year)}</strong>
          {department && (
            <>
              {" "}
              · <strong className="text-ink">{department}</strong>
            </>
          )}
          {dash.data?.reference_date && !touched && " (latest month with data)"}
        </p>
      </Panel>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {REPORTS.map(({ type, title, description, icon: Icon, tone, columns }) => (
          <section key={type} className="hr-card flex flex-col p-5">
            <div className="flex items-center gap-3">
              <span className={`flex size-10 items-center justify-center rounded-lg ${tone}`}>
                <Icon className="size-5" />
              </span>
              <div>
                <h2 className="font-semibold text-ink">{title}</h2>
                <p className="flex items-center gap-1 text-xs text-ink-muted">
                  <FileSpreadsheet className="size-3.5" /> Excel · {monthLabel(month, year)}
                </p>
              </div>
            </div>
            <p className="mt-3 text-sm text-ink-muted">{description}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {columns.map((c) => (
                <span key={c} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-ink-muted">
                  {c}
                </span>
              ))}
            </div>
            <Button className="mt-5 w-full" onClick={() => download(type)} disabled={busy !== null}>
              {busy === type ? <Spinner /> : <Download className="size-4" />}
              {busy === type ? "Preparing..." : "Download .xlsx"}
            </Button>
          </section>
        ))}
      </div>
    </>
  );
}
