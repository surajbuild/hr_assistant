/**
 * Attendance: My Attendance (everyone) · Daily View & Records (admin/hr/manager) · Mark Attendance (admin/hr).
 */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CalendarCheck, CalendarClock, CalendarDays, Download, Info, ListChecks, Plus, Save } from "lucide-react";
import { AttendanceTable, MonthKeySelect, monthsInRecords } from "@/components/AttendanceTable";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { Field, NativeSelect, SearchInput } from "@/components/Field";
import { Modal } from "@/components/Modal";
import { PageHeader, Panel } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState, LoadingState, Notice, Spinner } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Tabs } from "@/components/Tabs";
import { TodayAttendanceCard } from "@/components/TodayAttendanceCard";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCSV, formatDate, formatMinutes, formatTime, humanize, monthKey, monthRange, monthShortLabel, toISODate } from "@/lib/format";
import type { AttendanceRecord, AttendanceSummary, DailyAttendance, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";

type TabKey = "my" | "daily" | "records";
const STATUSES = ["present", "absent", "half_day", "leave", "holiday", "weekend"];

export function AttendancePage() {
  const { role } = useAuth();
  const isStaff = role === "admin" || role === "hr" || role === "manager";
  const canMark = role === "admin" || role === "hr";
  const [tab, setTab] = useState<TabKey>(isStaff ? "daily" : "my");
  const [markOpen, setMarkOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const tabs = [
    ...(isStaff ? [{ key: "daily" as const, label: "Daily View", icon: <CalendarClock /> }] : []),
    { key: "my" as const, label: "My Attendance", icon: <CalendarCheck /> },
    ...(isStaff ? [{ key: "records" as const, label: "Records", icon: <ListChecks /> }] : []),
  ];

  return (
    <>
      <PageHeader
        title="Attendance"
        subtitle="Track check-ins, working hours, late arrivals and overtime"
        actions={
          canMark && (
            <Button onClick={() => setMarkOpen(true)}>
              <Plus className="size-4" /> Mark Attendance
            </Button>
          )
        }
      />
      {tabs.length > 1 && <Tabs tabs={tabs} value={tab} onChange={setTab} className="mb-5" />}

      <div key={refreshKey}>
        {tab === "my" && <MyAttendance />}
        {tab === "daily" && isStaff && <DailyView />}
        {tab === "records" && isStaff && <RecordsView />}
      </div>

      {canMark && (
        <MarkAttendanceModal
          open={markOpen}
          onClose={() => setMarkOpen(false)}
          onSaved={() => {
            setMarkOpen(false);
            setRefreshKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// My Attendance
// ─────────────────────────────────────────────────────────────────────────────

function MyAttendance() {
  const records = useFetch<AttendanceRecord[]>("/attendance/me");
  const all = records.data ?? [];
  const months = useMemo(() => {
    const now = new Date();
    const cur = monthKey(now.getMonth() + 1, now.getFullYear());
    const set = new Set([cur, ...monthsInRecords(all)]);
    return [...set].sort().reverse();
  }, [all]);

  const [month, setMonth] = useState<string | null>(null);
  useEffect(() => {
    if (month !== null || records.loading) return;
    const withData = monthsInRecords(all);
    const now = new Date();
    setMonth(withData[0] ?? monthKey(now.getMonth() + 1, now.getFullYear()));
  }, [records.loading, all, month]);

  const [y, m] = (month ?? "").split("-").map(Number);
  const range = month && y && m ? monthRange(m, y) : null;
  const summary = useFetch<AttendanceSummary>(range ? `/attendance/summary${qs({ from_date: range.from, to_date: range.to })}` : null);
  const filtered = month ? all.filter((r) => r.attendance_date.startsWith(month)) : all;
  const s = summary.data;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <TodayAttendanceCard
          onChange={() => {
            records.reload();
            summary.reload();
          }}
        />
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-ink">
              Summary {month && y && m ? `· ${monthShortLabel(m, y)}` : ""}
            </h2>
            <MonthKeySelect months={months} value={month ?? ""} onChange={(v) => setMonth(v)} allowAll={false} />
          </div>
          {summary.loading || records.loading ? (
            <div className="hr-card">
              <LoadingState label="Loading summary..." />
            </div>
          ) : summary.error ? (
            <Notice tone="danger">{summary.error}</Notice>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
              <StatCard label="Present" value={s?.present_days ?? 0} tone="green" hint={`${s?.half_day_days ?? 0} half days`} />
              <StatCard label="Absent" value={s?.absent_days ?? 0} tone="red" hint={`${s?.leave_days ?? 0} on leave`} />
              <StatCard label="Late days" value={s?.late_days ?? 0} tone="amber" />
              <StatCard label="Worked" value={formatMinutes(s?.total_working_minutes ?? 0)} tone="blue" hint={`${s?.total_days ?? 0} days recorded`} />
              <StatCard label="Overtime" value={formatMinutes(s?.total_overtime_minutes ?? 0)} tone="violet" hint={`${s?.overtime_days ?? 0} OT days`} />
              <StatCard label="Holidays / Weekends" value={`${s?.holiday_days ?? 0} / ${s?.weekend_days ?? 0}`} tone="slate" />
            </div>
          )}
        </div>
      </div>

      <Panel title="My Records" subtitle={month ? monthShortLabel(m!, y!) : "All"} icon={<CalendarDays />} bodyClassName="p-0">
        <AsyncContent loading={records.loading} error={records.error} onRetry={records.reload} loadingLabel="Loading records...">
          <AttendanceTable records={filtered} />
        </AsyncContent>
      </Panel>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Daily View
// ─────────────────────────────────────────────────────────────────────────────

const COUNT_KEYS: { key: keyof DailyAttendance["counts"]; label: string }[] = [
  { key: "total", label: "All" },
  { key: "present", label: "Present" },
  { key: "late", label: "Late" },
  { key: "absent", label: "Absent" },
  { key: "half_day", label: "Half day" },
  { key: "leave", label: "Leave" },
  { key: "holiday", label: "Holiday" },
  { key: "weekend", label: "Weekend" },
  { key: "not_marked", label: "Not marked" },
];

function DailyView() {
  const [date, setDate] = useState("");
  const [status, setStatus] = useState<string>("total");
  const [search, setSearch] = useState("");
  const { data, loading, error, reload } = useFetch<DailyAttendance>(`/attendance/daily${qs({ date })}`);

  const rows = (data?.rows ?? []).filter((r) => {
    if (status === "late" ? !(r.late_minutes && r.late_minutes > 0) : status !== "total" && r.status !== status) return false;
    if (search) {
      const q = search.toLowerCase();
      return r.name.toLowerCase().includes(q) || r.employee_code.toLowerCase().includes(q) || (r.department ?? "").toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="hr-card flex flex-col gap-3 p-4 md:flex-row md:items-center">
        <div className="flex items-center gap-2">
          <label htmlFor="daily-date" className="text-sm font-medium text-ink">
            Date
          </label>
          <Input id="daily-date" type="date" value={date || data?.date || ""} onChange={(e) => setDate(e.target.value)} className="w-44 bg-white" />
          <Button variant="outline" size="sm" className="bg-white" onClick={() => setDate(toISODate(new Date()))}>
            Today
          </Button>
        </div>
        <SearchInput value={search} onChange={setSearch} placeholder="Search employee..." className="md:ml-auto md:w-64" />
      </div>

      {data?.is_fallback_date && (
        <Notice tone="info" icon={<Info />}>
          No attendance for the requested day — showing <strong>{formatDate(data.date)}</strong>, the latest date with data.
        </Notice>
      )}

      {data && (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
          {COUNT_KEYS.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => setStatus(c.key)}
              aria-pressed={status === c.key}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-brand",
                status === c.key ? "border-brand bg-brand text-white" : "border-border bg-white text-ink-muted hover:border-slate-300 hover:text-ink",
              )}
            >
              {c.label} <span className="ml-1 tabular-nums">{data.counts?.[c.key] ?? 0}</span>
            </button>
          ))}
        </div>
      )}

      <Panel
        title={data ? `Attendance · ${formatDate(data.date)}` : "Attendance"}
        icon={<CalendarClock />}
        bodyClassName="p-0"
      >
        <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading daily attendance...">
          <DataTable
            rows={rows}
            rowKey={(r) => r.employee_id}
            dense
            empty={<EmptyState title="No employees match" description="Try another status or search." />}
            columns={[
              {
                key: "emp",
                header: "Employee",
                render: (r) => (
                  <div className="flex items-center gap-2.5">
                    <Avatar name={r.name} size="sm" />
                    <div>
                      <p className="font-medium">{r.name}</p>
                      <p className="text-xs text-ink-muted">{r.employee_code}</p>
                    </div>
                  </div>
                ),
              },
              { key: "dept", header: "Department", render: (r) => r.department ?? "—" },
              { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
              { key: "in", header: "In", render: (r) => formatTime(r.in_time) },
              { key: "out", header: "Out", render: (r) => formatTime(r.out_time) },
              { key: "work", header: "Worked", render: (r) => (r.working_minutes ? formatMinutes(r.working_minutes) : "—") },
              {
                key: "late",
                header: "Late",
                render: (r) => (r.late_minutes && r.late_minutes > 0 ? <span className="font-medium text-warning">{formatMinutes(r.late_minutes)}</span> : "—"),
              },
              {
                key: "ot",
                header: "Overtime",
                render: (r) => (r.overtime_minutes && r.overtime_minutes > 0 ? <span className="font-medium text-brand">{formatMinutes(r.overtime_minutes)}</span> : "—"),
              },
            ]}
          />
        </AsyncContent>
      </Panel>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Records
// ─────────────────────────────────────────────────────────────────────────────

function RecordsView() {
  const employees = useFetch<Employee[]>("/employees");
  const [employeeId, setEmployeeId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [status, setStatus] = useState("");
  const { data, loading, error, reload } = useFetch<AttendanceRecord[]>(
    `/attendance/records${qs({ employee_id: employeeId, from_date: fromDate, to_date: toDate, status })}`,
  );
  const rows = data ?? [];

  function exportCSV() {
    downloadCSV(
      "attendance_records.csv",
      ["Date", "Employee", "Department", "Status", "In", "Out", "Working Minutes", "Late Minutes", "Overtime Minutes"],
      rows.map((r) => [r.attendance_date, r.employee_name, r.department, r.status, r.in_time, r.out_time, r.working_minutes, r.late_minutes, r.overtime_minutes]),
    );
  }

  return (
    <Panel
      title="Attendance Records"
      subtitle={loading ? undefined : `${rows.length} record${rows.length === 1 ? "" : "s"}`}
      icon={<ListChecks />}
      bodyClassName="p-0"
      actions={
        <Button variant="outline" size="sm" onClick={exportCSV} disabled={rows.length === 0}>
          <Download className="size-3.5" /> Export CSV
        </Button>
      }
    >
      <div className="grid grid-cols-1 gap-3 border-b border-border p-4 sm:grid-cols-2 lg:grid-cols-5">
        <NativeSelect value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} aria-label="Employee" className="lg:col-span-2">
          <option value="">All employees</option>
          {(employees.data ?? []).map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} ({e.employee_code})
            </option>
          ))}
        </NativeSelect>
        <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} aria-label="From date" className="bg-white" />
        <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} aria-label="To date" className="bg-white" />
        <NativeSelect value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </NativeSelect>
      </div>
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading records...">
        <AttendanceTable records={rows} showEmployee />
      </AsyncContent>
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mark Attendance (admin / hr)
// ─────────────────────────────────────────────────────────────────────────────

function toMinutes(t: string): number | null {
  const m = /^(\d{2}):(\d{2})/.exec(t);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

function MarkAttendanceModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const employees = useFetch<Employee[]>(open ? "/employees?status=active" : null);
  const [form, setForm] = useState({
    employee_id: "",
    attendance_date: toISODate(new Date()),
    status: "present",
    in_time: "09:00",
    out_time: "18:00",
    working_minutes: "",
    late_minutes: "0",
    overtime_minutes: "0",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const needsTimes = form.status === "present" || form.status === "half_day";
  const autoWorking = (() => {
    const a = toMinutes(form.in_time);
    const b = toMinutes(form.out_time);
    return a !== null && b !== null && b > a ? b - a : 0;
  })();

  function set(key: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!form.employee_id) {
      setErr("Please select an employee.");
      return;
    }
    setSaving(true);
    try {
      await api.post("/attendance", {
        employee_id: Number(form.employee_id),
        attendance_date: form.attendance_date,
        in_time: needsTimes && form.in_time ? `${form.in_time}:00` : null,
        out_time: needsTimes && form.out_time ? `${form.out_time}:00` : null,
        status: form.status,
        working_minutes: needsTimes ? (form.working_minutes ? Number(form.working_minutes) : autoWorking) : 0,
        late_minutes: needsTimes ? Number(form.late_minutes) || 0 : 0,
        overtime_minutes: needsTimes ? Number(form.overtime_minutes) || 0 : 0,
      });
      toast.success("Attendance saved.");
      onSaved();
    } catch (error) {
      setErr(errorMessage(error, "Failed to save attendance."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Mark Attendance"
      description="Create an attendance record for an employee"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="mark-attendance-form" disabled={saving}>
            {saving ? <Spinner /> : <Save className="size-4" />} Save
          </Button>
        </>
      }
    >
      <form id="mark-attendance-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
        <Field label="Employee" htmlFor="ma-emp" required className="sm:col-span-2">
          <NativeSelect id="ma-emp" value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)} className="w-full">
            <option value="">{employees.loading ? "Loading..." : "Select employee"}</option>
            {(employees.data ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.employee_code})
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Date" htmlFor="ma-date" required>
          <Input id="ma-date" type="date" value={form.attendance_date} onChange={(e) => set("attendance_date", e.target.value)} />
        </Field>
        <Field label="Status" htmlFor="ma-status" required>
          <NativeSelect id="ma-status" value={form.status} onChange={(e) => set("status", e.target.value)} className="w-full">
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </NativeSelect>
        </Field>
        {needsTimes && (
          <>
            <Field label="In time" htmlFor="ma-in">
              <Input id="ma-in" type="time" value={form.in_time} onChange={(e) => set("in_time", e.target.value)} />
            </Field>
            <Field label="Out time" htmlFor="ma-out">
              <Input id="ma-out" type="time" value={form.out_time} onChange={(e) => set("out_time", e.target.value)} />
            </Field>
            <Field label="Working minutes" htmlFor="ma-work" hint={`Auto: ${autoWorking} (${formatMinutes(autoWorking)})`}>
              <Input id="ma-work" type="number" min={0} placeholder={String(autoWorking)} value={form.working_minutes} onChange={(e) => set("working_minutes", e.target.value)} />
            </Field>
            <Field label="Late minutes" htmlFor="ma-late">
              <Input id="ma-late" type="number" min={0} value={form.late_minutes} onChange={(e) => set("late_minutes", e.target.value)} />
            </Field>
            <Field label="Overtime minutes" htmlFor="ma-ot">
              <Input id="ma-ot" type="number" min={0} value={form.overtime_minutes} onChange={(e) => set("overtime_minutes", e.target.value)} />
            </Field>
          </>
        )}
        {err && (
          <Notice tone="danger" className="sm:col-span-2">
            {err}
          </Notice>
        )}
      </form>
    </Modal>
  );
}
