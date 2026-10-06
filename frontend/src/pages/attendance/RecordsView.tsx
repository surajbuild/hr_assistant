/**
 * Records (admin / hr / manager-team): GET /attendance/records?employee_id&from_date&to_date&status&limit&offset with
 * server-side pagination (X-Total-Count, D-035). CSV export fetches every matching page. HR/Admin can edit a record
 * (PUT /attendance/records/{id}, D-033) — never their own row and never in a month whose salary is paid.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Download, ListChecks, Lock, Pencil, SearchX } from "lucide-react";
import { AttendanceTable } from "@/components/AttendanceTable";
import { Pagination } from "@/components/DataTable";
import { Field, NativeSelect } from "@/components/Field";
import { Modal } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Hint } from "@/components/ui/tooltip";
import { api, errorMessage, qs } from "@/lib/api";
import { downloadCSV, formatDate, formatMinutes, formatTime, humanize } from "@/lib/format";
import type { AttendanceRecord, AttendanceRecordRow, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { ATTENDANCE_STATUSES, hhmm, monthName, monthOf, toMinutes, usePaidKeys, withSeconds } from "./shared";

const PAGE = 25;

function usePage(path: string) {
  const [state, setState] = useState<{ items: AttendanceRecordRow[]; total: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .getPage<AttendanceRecordRow>(path)
      .then((p) => alive && setState(p))
      .catch((e: unknown) => alive && setError(errorMessage(e, "Failed to load records.")))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [path, tick]);
  return { data: state, loading, error, reload: () => setTick((t) => t + 1) };
}

export function RecordsView({ canEdit, ownEmployeeId }: { canEdit: boolean; ownEmployeeId?: number }) {
  const toast = useToast();
  const employees = useFetch<Employee[]>("/employees");
  const [employeeId, setEmployeeId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [editing, setEditing] = useState<AttendanceRecordRow | null>(null);

  const filters = { employee_id: employeeId, from_date: fromDate, to_date: toDate, status };
  const filterKey = JSON.stringify(filters);
  useEffect(() => setPage(0), [filterKey]);
  const rangeError = fromDate && toDate && toDate < fromDate ? "“To” must be on or after “From”." : null;

  const effective = { ...filters, from_date: rangeError ? "" : fromDate, to_date: rangeError ? "" : toDate };
  const { data, loading, error, reload } = usePage(`/attendance/records${qs({ ...effective, limit: PAGE, offset: page * PAGE })}`);
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const paid = usePaidKeys(rows.map((r) => monthOf(r.attendance_date)), canEdit);
  const hasFilters = !!(employeeId || fromDate || toDate || status);

  async function exportCSV() {
    setExporting(true);
    try {
      const all: AttendanceRecordRow[] = [];
      for (let offset = 0; offset < Math.max(total, 1) && offset < 20000; offset += 1000) {
        const p = await api.getPage<AttendanceRecordRow>(`/attendance/records${qs({ ...effective, limit: 1000, offset })}`);
        all.push(...p.items);
        if (p.items.length < 1000) break;
      }
      downloadCSV(
        "attendance_records.csv",
        ["Date", "Employee Code", "Employee", "Department", "Status", "In", "Out", "Working Minutes", "Late Minutes", "Overtime Minutes"],
        all.map((r) => [r.attendance_date, r.employee_code, r.employee_name, r.department, r.status, r.in_time, r.out_time, r.working_minutes, r.late_minutes, r.overtime_minutes]),
      );
      toast.success(`Exported ${all.length} record${all.length === 1 ? "" : "s"}.`);
    } catch (err) {
      toast.error(errorMessage(err, "Export failed."));
    } finally {
      setExporting(false);
    }
  }

  function clear() {
    setEmployeeId("");
    setFromDate("");
    setToDate("");
    setStatus("");
  }

  return (
    <Panel
      title="Attendance records"
      subtitle={loading && !data ? undefined : `${total.toLocaleString("en-IN")} record${total === 1 ? "" : "s"}`}
      icon={<ListChecks />}
      bodyClassName="p-0"
      actions={
        <Button variant="outline" size="sm" onClick={exportCSV} disabled={total === 0 || loading} loading={exporting}>
          {!exporting && <Download />} Export CSV
        </Button>
      }
    >
      <div className="grid grid-cols-1 gap-3 border-b border-border p-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]">
        <Field label="Employee" htmlFor="rec-emp">
          <NativeSelect id="rec-emp" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} className="w-full">
            <option value="">{employees.loading ? "Loading employees..." : "All employees"}</option>
            {(employees.data ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.employee_code})
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="From" htmlFor="rec-from">
          <Input id="rec-from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </Field>
        <Field label="To" htmlFor="rec-to">
          <Input id="rec-to" type="date" value={toDate} min={fromDate || undefined} onChange={(e) => setToDate(e.target.value)} aria-invalid={!!rangeError || undefined} />
        </Field>
        <Field label="Status" htmlFor="rec-status">
          <NativeSelect id="rec-status" value={status} onChange={(e) => setStatus(e.target.value)} className="w-full">
            <option value="">All statuses</option>
            {ATTENDANCE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Button variant="ghost" onClick={clear} disabled={!hasFilters} className="self-end">

          Clear
        </Button>
        {rangeError && (
          <p role="alert" className="text-xs text-status-absent-fg sm:col-span-2 lg:col-span-5">
            {rangeError} Showing all dates until fixed.
          </p>
        )}
      </div>
      <AsyncContent loading={loading && !data} error={error} onRetry={reload} loadingLabel="Loading records...">
        <div className={loading ? "opacity-60 transition-opacity" : undefined} aria-busy={loading || undefined}>
          <AttendanceTable
            records={rows}
            showEmployee
            presorted
            mobileCards
            empty={
              <EmptyState
                icon={<SearchX />}
                title={hasFilters ? "No records match your filters" : "No attendance records yet"}
                description={hasFilters ? "Try a wider date range or another status." : "Records appear as employees check in or HR marks attendance."}
                action={
                  hasFilters ? (
                    <Button size="sm" variant="outline" onClick={clear}>
                      Clear filters
                    </Button>
                  ) : undefined
                }
              />
            }
            actions={
              canEdit
                ? (r) => {
                    const row = r as AttendanceRecordRow;
                    if (row.employee_id === ownEmployeeId) {
                      return (
                        <Hint label="You can't edit your own attendance — request a correction instead">
                          <span tabIndex={0} className="inline-flex size-8 items-center justify-center text-muted-foreground" aria-label="Your own record — not editable">
                            <Lock className="size-3.5" />
                          </span>
                        </Hint>
                      );
                    }
                    if (paid.has(`${row.employee_id}:${monthOf(row.attendance_date)}`)) {
                      return (
                        <Hint label={`Salary for ${monthName(monthOf(row.attendance_date))} is paid — locked`}>
                          <span tabIndex={0} className="inline-flex size-8 items-center justify-center text-muted-foreground" aria-label="Locked: salary paid">
                            <Lock className="size-3.5" />
                          </span>
                        </Hint>
                      );
                    }
                    return (
                      <Hint label="Edit record">
                        <Button variant="ghost" size="icon-sm" aria-label={`Edit ${row.employee_name}, ${formatDate(row.attendance_date)}`} onClick={() => setEditing(row)}>
                          <Pencil />
                        </Button>
                      </Hint>
                    );
                  }
                : undefined
            }
          />
        </div>
        <Pagination page={page} pageSize={PAGE} total={total} onPage={setPage} />
      </AsyncContent>
      {canEdit && (
        <EditRecordDialog
          record={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </Panel>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Edit record (HR / Admin)
// ─────────────────────────────────────────────────────────────────────────────

function EditRecordDialog({ record, onClose, onSaved }: { record: AttendanceRecordRow | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [status, setStatus] = useState("present");
  const [inTime, setInTime] = useState("09:00");
  const [outTime, setOutTime] = useState("18:00");
  const [errors, setErrors] = useState<{ in?: string; out?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!record) return;
    setStatus(record.status);
    setInTime(hhmm(record.in_time) || "09:00");
    setOutTime(hhmm(record.out_time) || "18:00");
    setErrors({});
    setServerError(null);
  }, [record]);

  const worked = status === "present" || status === "half_day";
  const a = toMinutes(inTime);
  const b = toMinutes(outTime);
  const span = a !== null && b !== null && b > a ? b - a : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!record) return;
    setServerError(null);
    const errs: typeof errors = {};
    if (worked) {
      if (!inTime) errs.in = "In time is required for a worked day.";
      if (!outTime) errs.out = "Out time is required for a worked day.";
      else if (a !== null && b !== null && b <= a) errs.out = "Out time must be after in time.";
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      const saved = await api.put<AttendanceRecord>(`/attendance/records/${record.id}`, {
        status,
        in_time: worked ? withSeconds(inTime) : null,
        out_time: worked ? withSeconds(outTime) : null,
      });
      toast.success(`${record.employee_name} · ${formatDate(record.attendance_date)} saved as ${humanize(saved?.status ?? status).toLowerCase()}.`);
      onSaved();
    } catch (err) {
      const msg = errorMessage(err, "Failed to save the record.");
      setServerError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={!!record}
      onClose={saving ? () => undefined : onClose}
      title="Edit attendance record"
      description={record ? `${record.employee_name} · ${formatDate(record.attendance_date)}` : undefined}
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="edit-record-form" loading={saving}>
            Save changes
          </Button>
        </>
      }
    >
      {record && (
        <form id="edit-record-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
          <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5 text-sm sm:col-span-2">
            <p className="text-xs font-medium text-muted-foreground">Currently</p>
            <p className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={record.status} />
              <span className="tabular-nums">
                {formatTime(record.in_time)} – {formatTime(record.out_time)}
              </span>
              {record.working_minutes ? <span className="text-muted-foreground tabular-nums">· {formatMinutes(record.working_minutes)}</span> : null}
            </p>
          </div>
          <Field label="Status" htmlFor="er-status" required className="sm:col-span-2">
            <NativeSelect id="er-status" value={status} onChange={(e) => setStatus(e.target.value)} className="w-full">
              {ATTENDANCE_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </NativeSelect>
          </Field>
          {worked ? (
            <>
              <Field label="In time" htmlFor="er-in" required error={errors.in}>
                <Input id="er-in" type="time" value={inTime} aria-invalid={!!errors.in || undefined} onChange={(e) => setInTime(e.target.value)} />
              </Field>
              <Field label="Out time" htmlFor="er-out" required error={errors.out} hint={span !== null ? `${formatMinutes(span)} between in and out` : undefined}>
                <Input id="er-out" type="time" value={outTime} aria-invalid={!!errors.out || undefined} onChange={(e) => setOutTime(e.target.value)} />
              </Field>
              <p className="text-xs text-muted-foreground sm:col-span-2">
                The system decides present vs half day and calculates late and overtime minutes from these times.
              </p>
            </>
          ) : (
            <p className="text-xs text-muted-foreground sm:col-span-2">In/out times and minutes are cleared for a {humanize(status).toLowerCase()} day.</p>
          )}
          {serverError && (
            <Notice tone="danger" className="sm:col-span-2">
              {serverError}
            </Notice>
          )}
        </form>
      )}
    </Modal>
  );
}
