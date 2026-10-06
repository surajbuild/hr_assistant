/**
 * Add / edit employee (admin, hr). POST /employees · PUT /employees/{id}.
 * Reads: /employees/{id} (edit), /employees (manager picker), /departments (department + designation suggestions).
 * Sections: Basic information · Job · Compensation (confidential, D-021) · Login account (create only).
 * HR cannot create admin accounts (backend 403) → the Admin role option is only offered to admins.
 * Login email/role cannot be changed through PUT /employees, so edit mode shows them read-only.
 */
import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { ArrowLeft, Briefcase, IdCard, KeyRound, Lock, RefreshCw, Save, ShieldCheck, UserPlus } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Field, NativeSelect } from "@/components/Field";
import { PageHeader, Panel } from "@/components/PageHeader";
import { ErrorState, Notice } from "@/components/States";
import { RoleBadge, StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatINR, humanize } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { Department, Employee } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { Surface } from "./people/profile";

const STATUSES = ["active", "inactive", "on_notice", "terminated"];
const ALL_ROLES = ["employee", "manager", "hr", "admin"];
const MAX_SALARY = 100_000_000;

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

type Errors = Partial<Record<keyof FormState, string>>;

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

/** Order in which fields appear — the first invalid one receives focus on submit. */
const FIELD_ORDER: (keyof FormState)[] = ["employee_code", "name", "department", "designation", "joining_date", "manager_id", "monthly_gross_salary", "email", "password"];

function validate(form: FormState, isEdit: boolean): Errors {
  const e: Errors = {};
  if (!form.employee_code.trim()) e.employee_code = "Employee code is required.";
  if (!form.name.trim()) e.name = "Name is required.";
  if (!form.department.trim()) e.department = "Department is required.";
  if (!form.designation.trim()) e.designation = "Designation is required.";
  if (!form.joining_date) e.joining_date = "Joining date is required.";
  const sal = form.monthly_gross_salary.trim();
  if (sal && !(Number(sal) >= 0 && Number(sal) <= MAX_SALARY)) e.monthly_gross_salary = "Enter an amount between 0 and 10,00,00,000.";
  if (!isEdit && form.create_login) {
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) e.email = "Enter a valid email address.";
    if (form.password.length < 8) e.password = "Password must be at least 8 characters.";
    else if (form.password.length > 128) e.password = "Password must be at most 128 characters.";
  }
  return e;
}

export function EmployeeFormPage({ id }: { id?: number }) {
  const isEdit = id !== undefined && !Number.isNaN(id);
  const { role: myRole } = useAuth();
  const toast = useToast();
  const existing = useFetch<Employee>(isEdit ? `/employees/${id}` : null);
  const employees = useFetch<Employee[]>("/employees");
  const departments = useFetch<Department[]>("/departments");

  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});
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

  const roles = myRole === "admin" ? ALL_ROLES : ALL_ROLES.filter((r) => r !== "admin");

  // Designations of the chosen department first, then every other known designation.
  const designations = useMemo(() => {
    const list = departments.data ?? [];
    const own = list.find((d) => d.name.toLowerCase() === form.department.trim().toLowerCase())?.designations ?? [];
    const rest = new Set<string>();
    list.forEach((d) => d.designations?.forEach((x) => !own.includes(x) && rest.add(x)));
    return [...own.slice().sort(), ...[...rest].sort()];
  }, [departments.data, form.department]);

  const managerOptions = useMemo(
    () => (employees.data ?? []).filter((e) => e.id !== id && e.status !== "inactive").sort((a, b) => a.name.localeCompare(b.name)),
    [employees.data, id],
  );
  const manager = managerOptions.find((m) => String(m.id) === form.manager_id) ?? (employees.data ?? []).find((m) => String(m.id) === form.manager_id);
  const isNewDepartment =
    !!form.department.trim() && !!departments.data && !departments.data.some((d) => d.name.toLowerCase() === form.department.trim().toLowerCase());

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => (e[key] ? { ...e, [key]: undefined } : e));
  }

  /** Re-check a single field when it loses focus (only once the user has typed something or a submit failed). */
  function blurCheck(key: keyof FormState) {
    const all = validate(form, isEdit);
    setErrors((e) => ({ ...e, [key]: (form[key] !== "" || e[key]) ? all[key] : undefined }));
  }

  const backTo = isEdit ? `/employees/${id}` : "/employees";

  async function handleSubmit(ev: FormEvent) {
    ev.preventDefault();
    setSubmitError(null);
    const found = validate(form, isEdit);
    setErrors(found);
    const first = FIELD_ORDER.find((k) => found[k]);
    if (first) {
      requestAnimationFrame(() => document.getElementById(first)?.focus());
      return;
    }
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
      toast.success(isEdit ? `${form.name.trim()} has been updated.` : `${form.name.trim()} has been added.`);
      navigate(saved?.id ? `/employees/${saved.id}` : "/employees");
    } catch (err) {
      const msg = errorMessage(err, "Failed to save employee.");
      // Map known conflicts onto their field so the message sits where the fix is.
      if (/employee code/i.test(msg)) {
        setErrors((e) => ({ ...e, employee_code: msg }));
        requestAnimationFrame(() => document.getElementById("employee_code")?.focus());
      } else if (/email/i.test(msg) && form.create_login) {
        setErrors((e) => ({ ...e, email: msg }));
        requestAnimationFrame(() => document.getElementById("email")?.focus());
      } else {
        setSubmitError(msg);
      }
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const header = (
    <PageHeader
      title={isEdit ? `Edit ${existing.data?.name ?? "employee"}` : "Add employee"}
      subtitle={isEdit ? "Update employment details. Changes apply immediately." : "Create an employee record and, optionally, a login account."}
      actions={
        <Button variant="outline" onClick={() => navigate(backTo)}>
          <ArrowLeft /> {isEdit ? "Back to profile" : "Employees"}
        </Button>
      }
    />
  );

  if (isEdit && existing.loading) {
    return (
      <>
        {header}
        <FormSkeleton />
      </>
    );
  }
  if (isEdit && (existing.error || !existing.data)) {
    return (
      <>
        {header}
        <Surface>
          <ErrorState message={existing.error ?? "Employee not found."} onRetry={existing.reload} />
        </Surface>
      </>
    );
  }

  const inv = (k: keyof FormState) => (errors[k] ? true : undefined);

  return (
    <>
      {header}
      <form onSubmit={handleSubmit} noValidate aria-busy={saving || undefined} className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-5">
          <Panel title="Basic information" icon={<IdCard />}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field label="Employee code" htmlFor="employee_code" required error={errors.employee_code} hint="Unique, e.g. EMP007">
                <Input
                  id="employee_code"
                  value={form.employee_code}
                  maxLength={50}
                  autoComplete="off"
                  aria-invalid={inv("employee_code")}
                  onChange={(e) => set("employee_code", e.target.value)}
                  onBlur={() => blurCheck("employee_code")}
                  placeholder="EMP007"
                />
              </Field>
              <Field label="Full name" htmlFor="name" required error={errors.name}>
                <Input
                  id="name"
                  value={form.name}
                  maxLength={255}
                  autoComplete="off"
                  aria-invalid={inv("name")}
                  onChange={(e) => set("name", e.target.value)}
                  onBlur={() => blurCheck("name")}
                  placeholder="Jane Doe"
                />
              </Field>
            </div>
          </Panel>

          <Panel title="Job" icon={<Briefcase />}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field
                label="Department"
                htmlFor="department"
                required
                error={errors.department}
                hint={isNewDepartment ? `“${form.department.trim()}” will be created as a new department.` : "Pick an existing department or type a new one"}
              >
                <Input
                  id="department"
                  list="dept-list"
                  value={form.department}
                  maxLength={100}
                  autoComplete="off"
                  aria-invalid={inv("department")}
                  onChange={(e) => set("department", e.target.value)}
                  onBlur={() => blurCheck("department")}
                  placeholder="Engineering"
                />
                <datalist id="dept-list">
                  {(departments.data ?? []).map((d) => (
                    <option key={d.name} value={d.name} />
                  ))}
                </datalist>
              </Field>
              <Field label="Designation" htmlFor="designation" required error={errors.designation}>
                <Input
                  id="designation"
                  list="desig-list"
                  value={form.designation}
                  maxLength={100}
                  autoComplete="off"
                  aria-invalid={inv("designation")}
                  onChange={(e) => set("designation", e.target.value)}
                  onBlur={() => blurCheck("designation")}
                  placeholder="Software Engineer"
                />
                <datalist id="desig-list">
                  {designations.map((d) => (
                    <option key={d} value={d} />
                  ))}
                </datalist>
              </Field>
              <Field label="Joining date" htmlFor="joining_date" required error={errors.joining_date}>
                <Input
                  id="joining_date"
                  type="date"
                  value={form.joining_date}
                  aria-invalid={inv("joining_date")}
                  onChange={(e) => set("joining_date", e.target.value)}
                  onBlur={() => blurCheck("joining_date")}
                />
              </Field>
              <Field label="Status" htmlFor="status" hint={form.status === "inactive" ? "Inactive employees cannot sign in." : undefined}>
                <NativeSelect id="status" value={form.status} onChange={(e) => set("status", e.target.value)} className="w-full">
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {humanize(s)}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field
                label="Reporting manager"
                htmlFor="manager_id"
                className="md:col-span-2"
                error={errors.manager_id}
                hint={
                  employees.error ? (
                    <span className="inline-flex flex-wrap items-center gap-1.5">
                      Couldn't load the employee list.
                      <button type="button" onClick={employees.reload} className="inline-flex items-center gap-1 rounded-sm font-medium text-brand-subtle-foreground underline-offset-4 hover:underline">
                        <RefreshCw className="size-3" aria-hidden="true" /> Retry
                      </button>
                    </span>
                  ) : (
                    "Managers can see and approve requests of their direct reports."
                  )
                }
              >
                <NativeSelect id="manager_id" value={form.manager_id} onChange={(e) => set("manager_id", e.target.value)} className="w-full" disabled={employees.loading}>
                  <option value="">{employees.loading ? "Loading employees…" : "— No manager —"}</option>
                  {managerOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.employee_code}){m.designation ? ` · ${m.designation}` : ""}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
            </div>
          </Panel>

          <Panel title="Compensation" icon={<Lock />} subtitle="Confidential — visible only to HR, Admin and the employee">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field
                label="Monthly gross salary (₹)"
                htmlFor="monthly_gross_salary"
                error={errors.monthly_gross_salary}
                hint={
                  form.monthly_gross_salary.trim() && Number(form.monthly_gross_salary) >= 0
                    ? `${formatINR(Number(form.monthly_gross_salary))} per month · used by Generate payroll`
                    : "Salary structure used by Generate payroll"
                }
              >
                <div className="relative">
                  <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted-foreground" aria-hidden="true">
                    ₹
                  </span>
                  <Input
                    id="monthly_gross_salary"
                    type="number"
                    min={0}
                    max={MAX_SALARY}
                    step="100"
                    inputMode="decimal"
                    className="pl-7 tabular-nums"
                    aria-invalid={inv("monthly_gross_salary")}
                    value={form.monthly_gross_salary}
                    onChange={(e) => set("monthly_gross_salary", e.target.value)}
                    onBlur={() => blurCheck("monthly_gross_salary")}
                    placeholder="60000"
                  />
                </div>
              </Field>
              {isEdit && existing.data?.monthly_gross_salary != null && (
                <div className="self-start rounded-lg bg-surface-muted px-3 py-2.5 text-sm md:mt-6">
                  <p className="text-xs font-medium text-muted-foreground">Current structure</p>
                  <p className="font-semibold text-foreground tabular-nums">{formatINR(existing.data.monthly_gross_salary)}</p>
                </div>
              )}
            </div>
          </Panel>

          {!isEdit ? (
            <Panel title="Login account" icon={<KeyRound />} subtitle="Optional — lets the employee sign in">
              <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
                <label htmlFor="create_login" className="min-w-0 cursor-pointer">
                  <span className="block text-sm font-medium text-foreground">Create login account</span>
                  <span className="block text-xs text-muted-foreground">Email + password sign-in with the chosen role.</span>
                </label>
                <Switch id="create_login" checked={form.create_login} onCheckedChange={(v) => set("create_login", v)} />
              </div>
              {form.create_login && (
                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3 animate-page-in">
                  <Field label="Email" htmlFor="email" required error={errors.email}>
                    <Input
                      id="email"
                      type="email"
                      autoComplete="off"
                      aria-invalid={inv("email")}
                      value={form.email}
                      onChange={(e) => set("email", e.target.value)}
                      onBlur={() => blurCheck("email")}
                      placeholder="jane@company.com"
                    />
                  </Field>
                  <Field label="Password" htmlFor="password" required error={errors.password} hint="Minimum 8 characters">
                    <Input
                      id="password"
                      type="password"
                      autoComplete="new-password"
                      maxLength={128}
                      aria-invalid={inv("password")}
                      value={form.password}
                      onChange={(e) => set("password", e.target.value)}
                      onBlur={() => blurCheck("password")}
                    />
                  </Field>
                  <Field label="Role" htmlFor="role" hint={myRole !== "admin" ? "Only admins can create admin accounts." : undefined}>
                    <NativeSelect id="role" value={form.role} onChange={(e) => set("role", e.target.value)} className="w-full">
                      {roles.map((r) => (
                        <option key={r} value={r}>
                          {r === "hr" ? "HR" : humanize(r)}
                        </option>
                      ))}
                    </NativeSelect>
                  </Field>
                </div>
              )}
            </Panel>
          ) : (
            <Panel title="Login account" icon={<ShieldCheck />}>
              {existing.data?.email ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{existing.data.email}</p>
                    <p className="text-xs text-muted-foreground">
                      {myRole === "admin" ? "Change roles or disable sign-in under Settings → Users & Roles." : "Only an admin can change roles or sign-in access."}
                    </p>
                  </div>
                  {existing.data.role && <RoleBadge role={existing.data.role} />}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">This employee has no login account.</p>
              )}
            </Panel>
          )}

          {submitError && (
            <Notice tone="danger" className="animate-page-in">
              <span role="alert">{submitError}</span>
            </Notice>
          )}

          <div className="sticky bottom-0 z-10 -mx-4 flex flex-col-reverse gap-2 border-t border-border bg-background px-4 py-3 sm:mx-0 sm:flex-row sm:justify-end sm:rounded-xl sm:border sm:bg-surface">
            <Button type="button" variant="outline" onClick={() => navigate(backTo)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              {!saving && (isEdit ? <Save /> : <UserPlus />)}
              {isEdit ? "Save changes" : "Create employee"}
            </Button>
          </div>
        </div>

        <PreviewCard form={form} managerName={manager?.name ?? null} isEdit={isEdit} />
      </form>
    </>
  );
}

/** Live preview of how the record will read in the directory (desktop only). */
function PreviewCard({ form, managerName, isEdit }: { form: FormState; managerName: string | null; isEdit: boolean }) {
  const name = form.name.trim();
  const rows: [string, ReactNode][] = [
    ["Code", form.employee_code.trim() || "—"],
    ["Department", form.department.trim() || "—"],
    ["Reports to", managerName ?? "—"],
    ["Joined", form.joining_date ? formatDate(form.joining_date) : "—"],
  ];
  if (!isEdit) rows.push(["Login", form.create_login ? (form.email.trim() || "Email not set") : "No login"]);
  return (
    <aside className="sticky top-20 hidden lg:block" aria-label="Preview">
      <Surface className="overflow-hidden">
        <div className="h-14 bg-brand-subtle" aria-hidden="true" />
        <div className="px-5 pb-5">
          <Avatar name={name || "?"} size="lg" className="-mt-6 ring-4 ring-surface" />
          <p className="mt-2 truncate text-base font-semibold text-foreground">{name || "New employee"}</p>
          <p className="truncate text-sm text-muted-foreground">{form.designation.trim() || "Designation"}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <StatusBadge status={form.status} />
            {!isEdit && form.create_login && <RoleBadge role={form.role} />}
          </div>
          <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 border-t border-border pt-4 text-xs">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="truncate text-right font-medium text-foreground">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </Surface>
      <p className="mt-3 px-1 text-xs text-muted-foreground">Fields marked * are required. Deactivating keeps attendance, leave and salary history.</p>
    </aside>
  );
}

function FormSkeleton() {
  return (
    <div role="status" aria-live="polite" className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
      <span className="sr-only">Loading employee</span>
      <div className="flex flex-col gap-5">
        {[2, 6, 1].map((n, i) => (
          <Surface key={i} className="p-5">
            <Skeleton className="mb-4 h-4 w-40" />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {Array.from({ length: n }, (_, j) => (
                <div key={j} className="flex flex-col gap-2">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-9 w-full" />
                </div>
              ))}
            </div>
          </Surface>
        ))}
      </div>
      <Skeleton className="hidden h-72 lg:block" />
    </div>
  );
}
