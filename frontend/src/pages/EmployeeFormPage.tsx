/** Add / edit employee (admin, hr). POST /employees · PUT /employees/{id}. */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { ArrowLeft, KeyRound, Save } from "lucide-react";
import { Field, NativeSelect } from "@/components/Field";
import { PageHeader, Panel } from "@/components/PageHeader";
import { ErrorState, LoadingState, Notice, Spinner } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { humanize } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { Department, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const STATUSES = ["active", "inactive", "on_notice", "terminated"];
const ROLES = ["employee", "manager", "hr", "admin"];

interface FormState {
  employee_code: string;
  name: string;
  department: string;
  designation: string;
  joining_date: string;
  status: string;
  manager_id: string;
  monthly_gross_salary: string;
  create_login: boolean;
  email: string;
  password: string;
  role: string;
}

const EMPTY: FormState = {
  employee_code: "",
  name: "",
  department: "",
  designation: "",
  joining_date: "",
  status: "active",
  manager_id: "",
  monthly_gross_salary: "",
  create_login: false,
  email: "",
  password: "",
  role: "employee",
};

export function EmployeeFormPage({ id }: { id?: number }) {
  const isEdit = id !== undefined && !Number.isNaN(id);
  const toast = useToast();
  const existing = useFetch<Employee>(isEdit ? `/employees/${id}` : null);
  const employees = useFetch<Employee[]>("/employees");
  const departments = useFetch<Department[]>("/departments");

  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const e = existing.data;
    if (!e) return;
    setForm({
      ...EMPTY,
      employee_code: e.employee_code ?? "",
      name: e.name ?? "",
      department: e.department ?? "",
      designation: e.designation ?? "",
      joining_date: e.joining_date ?? "",
      status: e.status ?? "active",
      manager_id: e.manager_id ? String(e.manager_id) : "",
      monthly_gross_salary: e.monthly_gross_salary != null ? String(e.monthly_gross_salary) : "",
    });
  }, [existing.data]);

  const designations = useMemo(() => {
    const s = new Set<string>();
    (departments.data ?? []).forEach((d) => d.designations?.forEach((x) => s.add(x)));
    return [...s].sort();
  }, [departments.data]);

  const managerOptions = useMemo(
    () => (employees.data ?? []).filter((e) => e.id !== id && e.status !== "inactive").sort((a, b) => a.name.localeCompare(b.name)),
    [employees.data, id],
  );

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  }

  function validate(): boolean {
    const e: Partial<Record<keyof FormState, string>> = {};
    if (!form.employee_code.trim()) e.employee_code = "Employee code is required.";
    if (!form.name.trim()) e.name = "Name is required.";
    if (!form.department.trim()) e.department = "Department is required.";
    if (!form.designation.trim()) e.designation = "Designation is required.";
    if (!form.joining_date) e.joining_date = "Joining date is required.";
    if (form.monthly_gross_salary.trim() && !(Number(form.monthly_gross_salary) >= 0)) {
      e.monthly_gross_salary = "Enter a valid amount.";
    }
    if (!isEdit && form.create_login) {
      if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) e.email = "Enter a valid email address.";
      if (form.password.length < 8) e.password = "Password must be at least 8 characters.";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit(ev: FormEvent) {
    ev.preventDefault();
    setSubmitError(null);
    if (!validate()) return;
    const body: Record<string, unknown> = {
      employee_code: form.employee_code.trim(),
      name: form.name.trim(),
      department: form.department.trim(),
      designation: form.designation.trim(),
      joining_date: form.joining_date,
      status: form.status,
      manager_id: form.manager_id ? Number(form.manager_id) : null,
    };
    if (form.monthly_gross_salary.trim()) body.monthly_gross_salary = Number(form.monthly_gross_salary);
    if (!isEdit && form.create_login) {
      body.email = form.email.trim();
      body.password = form.password;
      body.role = form.role;
    }
    setSaving(true);
    try {
      const saved = isEdit ? await api.put<Employee>(`/employees/${id}`, body) : await api.post<Employee>("/employees", body);
      toast.success(isEdit ? "Employee updated." : "Employee created.");
      navigate(saved?.id ? `/employees/${saved.id}` : "/employees");
    } catch (err) {
      setSubmitError(errorMessage(err, "Failed to save employee."));
    } finally {
      setSaving(false);
    }
  }

  if (isEdit && existing.loading) return <LoadingState label="Loading employee..." />;
  if (isEdit && existing.error) return <ErrorState message={existing.error} onRetry={existing.reload} />;

  return (
    <>
      <PageHeader
        title={isEdit ? `Edit ${existing.data?.name ?? "Employee"}` : "Add Employee"}
        subtitle={isEdit ? "Update employee details" : "Create a new employee record"}
        actions={
          <Button variant="outline" className="bg-white" onClick={() => navigate(isEdit ? `/employees/${id}` : "/employees")}>
            <ArrowLeft className="size-4" /> Back
          </Button>
        }
      />

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <Panel title="Employee details">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Employee code" htmlFor="employee_code" required error={errors.employee_code}>
              <Input id="employee_code" value={form.employee_code} onChange={(e) => set("employee_code", e.target.value)} placeholder="EMP007" />
            </Field>
            <Field label="Full name" htmlFor="name" required error={errors.name}>
              <Input id="name" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Jane Doe" />
            </Field>
            <Field label="Department" htmlFor="department" required error={errors.department} hint="Pick an existing department or type a new one">
              <Input id="department" list="dept-list" value={form.department} onChange={(e) => set("department", e.target.value)} placeholder="Engineering" />
              <datalist id="dept-list">
                {(departments.data ?? []).map((d) => (
                  <option key={d.name} value={d.name} />
                ))}
              </datalist>
            </Field>
            <Field label="Designation" htmlFor="designation" required error={errors.designation}>
              <Input id="designation" list="desig-list" value={form.designation} onChange={(e) => set("designation", e.target.value)} placeholder="Software Engineer" />
              <datalist id="desig-list">
                {designations.map((d) => (
                  <option key={d} value={d} />
                ))}
              </datalist>
            </Field>
            <Field label="Joining date" htmlFor="joining_date" required error={errors.joining_date}>
              <Input id="joining_date" type="date" value={form.joining_date} onChange={(e) => set("joining_date", e.target.value)} />
            </Field>
            <Field label="Status" htmlFor="status">
              <NativeSelect id="status" value={form.status} onChange={(e) => set("status", e.target.value)} className="w-full">
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {humanize(s)}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field
              label="Monthly gross salary (₹)"
              htmlFor="monthly_gross_salary"
              error={errors.monthly_gross_salary}
              hint="Salary structure used by Generate payroll. Visible only to HR/Admin and the employee."
            >
              <Input
                id="monthly_gross_salary"
                type="number"
                min={0}
                step="100"
                inputMode="decimal"
                value={form.monthly_gross_salary}
                onChange={(e) => set("monthly_gross_salary", e.target.value)}
                placeholder="e.g. 60000"
              />
            </Field>
            <Field label="Reporting manager" htmlFor="manager_id">
              <NativeSelect id="manager_id" value={form.manager_id} onChange={(e) => set("manager_id", e.target.value)} className="w-full" disabled={employees.loading}>
                <option value="">— No manager —</option>
                {managerOptions.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.employee_code}){m.designation ? ` · ${m.designation}` : ""}
                  </option>
                ))}
              </NativeSelect>
            </Field>
          </div>
        </Panel>

        {!isEdit && (
          <Panel title="Login account" icon={<KeyRound />}>
            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                checked={form.create_login}
                onChange={(e) => set("create_login", e.target.checked)}
                className="size-4 rounded border-slate-300 accent-brand"
              />
              Create login account for this employee
            </label>
            {form.create_login && (
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
                <Field label="Email" htmlFor="email" required error={errors.email}>
                  <Input id="email" type="email" autoComplete="off" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="jane@company.com" />
                </Field>
                <Field label="Password" htmlFor="password" required error={errors.password} hint="Minimum 8 characters">
                  <Input id="password" type="password" autoComplete="new-password" value={form.password} onChange={(e) => set("password", e.target.value)} />
                </Field>
                <Field label="Role" htmlFor="role">
                  <NativeSelect id="role" value={form.role} onChange={(e) => set("role", e.target.value)} className="w-full">
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r === "hr" ? "HR" : humanize(r)}
                      </option>
                    ))}
                  </NativeSelect>
                </Field>
              </div>
            )}
          </Panel>
        )}

        {submitError && <Notice tone="danger">{submitError}</Notice>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" className="bg-white" onClick={() => navigate(isEdit ? `/employees/${id}` : "/employees")} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? <Spinner /> : <Save className="size-4" />}
            {isEdit ? "Save changes" : "Create employee"}
          </Button>
        </div>
      </form>
    </>
  );
}
