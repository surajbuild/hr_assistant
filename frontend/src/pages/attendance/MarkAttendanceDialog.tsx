/** Mark attendance (HR / Admin): POST /attendance — creates a record for an employee and day (409 if one exists). */
import { useEffect, useState, type FormEvent } from "react";
import { Save } from "lucide-react";
import { Field, NativeSelect } from "@/components/Field";
import { Modal } from "@/components/Modal";
import { Notice } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { formatMinutes, humanize, toISODate } from "@/lib/format";
import type { Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { ATTENDANCE_STATUSES, toMinutes } from "./shared";

const initial = () => ({
  employee_id: "",
  attendance_date: toISODate(new Date()),
  status: "present",
  in_time: "09:00",
  out_time: "18:00",
  working_minutes: "",
  late_minutes: "0",
  overtime_minutes: "0",
});

type Errors = Partial<Record<"employee_id" | "attendance_date" | "out_time", string>>;

export function MarkAttendanceDialog({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const employees = useFetch<Employee[]>(open ? "/employees?status=active" : null);
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<Errors>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(initial());
      setErrors({});
      setErr(null);
    }
  }, [open]);

  const needsTimes = form.status === "present" || form.status === "half_day";
  const a = toMinutes(form.in_time);
  const b = toMinutes(form.out_time);
  const autoWorking = a !== null && b !== null && b > a ? b - a : 0;

  function set(key: keyof ReturnType<typeof initial>, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    const errs: Errors = {};
    if (!form.employee_id) errs.employee_id = "Select an employee.";
    if (!form.attendance_date) errs.attendance_date = "Choose a date.";
    if (needsTimes && a !== null && b !== null && b <= a) errs.out_time = "Out time must be after in time.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
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
      const msg = errorMessage(error, "Failed to save attendance.");
      setErr(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={saving ? () => undefined : onClose}
      title="Mark attendance"
      description="Create a record for a day that has none. To change an existing day, use Edit in Records."
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="mark-attendance-form" loading={saving}>
            {!saving && <Save />} Save
          </Button>
        </>
      }
    >
      <form id="mark-attendance-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
        <Field label="Employee" htmlFor="ma-emp" required error={errors.employee_id} className="sm:col-span-2">
          <NativeSelect id="ma-emp" value={form.employee_id} aria-invalid={!!errors.employee_id || undefined} onChange={(e) => set("employee_id", e.target.value)} className="w-full">
            <option value="">{employees.loading ? "Loading..." : "Select employee"}</option>
            {(employees.data ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} ({e.employee_code})
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Date" htmlFor="ma-date" required error={errors.attendance_date}>
          <Input id="ma-date" type="date" value={form.attendance_date} aria-invalid={!!errors.attendance_date || undefined} onChange={(e) => set("attendance_date", e.target.value)} />
        </Field>
        <Field label="Status" htmlFor="ma-status" required>
          <NativeSelect id="ma-status" value={form.status} onChange={(e) => set("status", e.target.value)} className="w-full">
            {ATTENDANCE_STATUSES.map((s) => (
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
            <Field label="Out time" htmlFor="ma-out" error={errors.out_time}>
              <Input id="ma-out" type="time" value={form.out_time} aria-invalid={!!errors.out_time || undefined} onChange={(e) => set("out_time", e.target.value)} />
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
