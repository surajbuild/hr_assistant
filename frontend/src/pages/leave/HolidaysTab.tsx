/**
 * Holiday calendar (D-034): GET /holidays?year — national (fixed, cannot be removed) + company holidays declared by HR.
 * HR/Admin: POST /holidays {holiday_date, name} (422 weekend/blank, 409 national/duplicate) and DELETE /holidays/{id}.
 */
import { useState, type FormEvent } from "react";
import { CalendarHeart, ChevronLeft, ChevronRight, Info, Plus, Trash2 } from "lucide-react";
import { Field } from "@/components/Field";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Hint } from "@/components/ui/tooltip";
import { api, errorMessage } from "@/lib/api";
import { formatDate, parseDate, toISODate } from "@/lib/format";
import type { Holiday } from "@/lib/types";
import { cn } from "@/lib/utils";
import { invalidateHolidays, isWeekend, useHolidays } from "./holidays";

export function HolidaysTab({ canManage }: { canManage: boolean }) {
  const toast = useToast();
  const thisYear = new Date().getFullYear();
  const today = toISODate(new Date());
  const [year, setYear] = useState(thisYear);
  const state = useHolidays([year]);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Holiday | null>(null);
  const [busy, setBusy] = useState(false);

  const items = [...state.items].sort((a, b) => a.date.localeCompare(b.date));
  const next = items.find((h) => h.date >= today);
  const weekdayCount = items.filter((h) => !isWeekend(h.date)).length;

  async function confirmRemove() {
    if (!removing?.id) return;
    setBusy(true);
    try {
      await api.del(`/holidays/${removing.id}`);
      toast.success(`${removing.name} removed from the holiday calendar.`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to remove the holiday."));
    } finally {
      setBusy(false);
      setRemoving(null);
      invalidateHolidays(year);
    }
  }

  // Group by month
  const groups = new Map<string, Holiday[]>();
  for (const h of items) {
    const k = parseDate(h.date)?.toLocaleDateString("en-GB", { month: "long" }) ?? "";
    groups.set(k, [...(groups.get(k) ?? []), h]);
  }

  return (
    <div className="flex flex-col gap-4">
      <Notice tone="info" icon={<Info />}>
        Holidays are paid days off: leave that spans a holiday isn't charged for it, and holidays are excluded from payroll working days.
        {canManage && " National holidays are fixed; company holidays you declare can be removed."}
      </Notice>
      <Panel
        title={`Holidays ${year}`}
        subtitle={state.loading && state.items.length === 0 ? undefined : `${items.length} holiday${items.length === 1 ? "" : "s"} · ${weekdayCount} on weekdays`}
        icon={<CalendarHeart />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1">
              <Button variant="outline" size="icon-sm" onClick={() => setYear((y) => y - 1)} disabled={year <= 2000} aria-label="Previous year">
                <ChevronLeft />
              </Button>
              <span className="min-w-12 text-center text-sm font-medium text-foreground tabular-nums" aria-live="polite">
                {year}
              </span>
              <Button variant="outline" size="icon-sm" onClick={() => setYear((y) => y + 1)} disabled={year >= 2100} aria-label="Next year">
                <ChevronRight />
              </Button>
              {year !== thisYear && (
                <Button variant="ghost" size="sm" onClick={() => setYear(thisYear)}>
                  This year
                </Button>
              )}
            </div>
            {canManage && (
              <Button size="sm" onClick={() => setAdding(true)}>
                <Plus /> Add holiday
              </Button>
            )}
          </div>
        }
      >
        <AsyncContent loading={state.loading && state.items.length === 0} error={state.error} onRetry={state.reload} loadingLabel="Loading holidays...">
          {items.length === 0 ? (
            <EmptyState
              icon={<CalendarHeart />}
              title={`No holidays in ${year}`}
              description={canManage ? "Declare company holidays such as Diwali or Holi." : "Nothing has been declared for this year."}
              action={
                canManage ? (
                  <Button size="sm" onClick={() => setAdding(true)}>
                    <Plus /> Add holiday
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="flex flex-col gap-5">
              {[...groups].map(([month, list]) => (
                <section key={month} aria-label={month}>
                  <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{month}</h3>
                  <ul className="flex flex-col gap-2">
                    {list.map((h) => {
                      const past = h.date < today;
                      const isNext = h === next;
                      const weekend = isWeekend(h.date);
                      const d = parseDate(h.date);
                      return (
                        <li
                          key={`${h.kind}-${h.date}`}
                          className={cn(
                            "flex items-center gap-3 rounded-xl border px-3 py-2.5 sm:px-4",
                            isNext ? "border-brand bg-brand-subtle" : "border-border bg-surface",
                          )}
                        >
                          <div className={cn("flex w-12 shrink-0 flex-col items-center rounded-lg py-1 text-center", isNext ? "bg-surface" : "bg-surface-muted")}>
                            <span className="text-[11px] font-medium text-muted-foreground uppercase">{formatDate(h.date).slice(3, 6)}</span>
                            <span className={cn("text-lg leading-6 font-semibold tabular-nums", past ? "text-muted-foreground" : "text-foreground")}>{d?.getDate()}</span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className={cn("truncate text-sm font-medium", past ? "text-muted-foreground" : "text-foreground")}>{h.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {h.weekday}
                              {weekend && " · falls on a weekend"}
                              {past && " · passed"}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-1.5">
                            {isNext && <Badge className="bg-brand text-brand-foreground">Next</Badge>}
                            <Badge tone={h.kind === "national" ? "leave" : "half"} className="hidden min-[420px]:inline-flex">
                              {h.kind === "national" ? "National" : "Company"}
                            </Badge>
                            {canManage &&
                              (h.id !== null ? (
                                <Hint label="Remove holiday">
                                  <Button variant="ghost" size="icon-sm" className="text-status-absent-fg hover:bg-status-absent-bg" aria-label={`Remove ${h.name}`} onClick={() => setRemoving(h)}>
                                    <Trash2 />
                                  </Button>
                                </Hint>
                              ) : (
                                <span className="size-8" aria-hidden="true" />
                              ))}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </AsyncContent>
      </Panel>

      {canManage && (
        <AddHolidayDialog
          open={adding}
          year={year}
          existing={state.byDate}
          onClose={() => setAdding(false)}
          onAdded={(h) => {
            setAdding(false);
            const y = Number(h.date.slice(0, 4));
            invalidateHolidays(y);
            if (y !== year) setYear(y);
          }}
        />
      )}
      <ConfirmDialog
        open={!!removing}
        title="Remove holiday?"
        message={
          removing && (
            <>
              <strong className="text-foreground">{removing.name}</strong> on {formatDate(removing.date)} becomes a working day again. Payroll already generated for that
              month isn't recalculated automatically — regenerate it for unpaid months.
            </>
          )
        }
        confirmLabel="Remove holiday"
        busy={busy}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(null)}
      />
    </div>
  );
}

function AddHolidayDialog({
  open,
  year,
  existing,
  onClose,
  onAdded,
}: {
  open: boolean;
  year: number;
  existing: Map<string, Holiday>;
  onClose: () => void;
  onAdded: (h: Holiday) => void;
}) {
  const toast = useToast();
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<{ date?: string; name?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function close() {
    setDate("");
    setName("");
    setErrors({});
    setServerError(null);
    onClose();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);
    const errs: typeof errors = {};
    if (!date) errs.date = "Choose a date.";
    else if (isWeekend(date)) errs.date = "This date is a weekend — it's already a non-working day.";
    else if (existing.get(date)) errs.date = `Already a holiday (${existing.get(date)!.name}).`;
    if (!name.trim()) errs.name = "Give the holiday a name.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      const h = await api.post<Holiday>("/holidays", { holiday_date: date, name: name.trim() });
      toast.success(`${h?.name ?? name.trim()} added on ${formatDate(date)}.`);
      setDate("");
      setName("");
      onAdded(h ?? { id: null, date, name: name.trim(), kind: "company", weekday: "" });
    } catch (err) {
      const msg = errorMessage(err, "Failed to add the holiday.");
      setServerError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={saving ? () => undefined : close}
      title="Add company holiday"
      description="Employees get the day off; it isn't charged as leave and doesn't count as a payroll working day."
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={close} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="holiday-form" loading={saving}>
            {!saving && <Plus />} Add holiday
          </Button>
        </>
      }
    >
      <form id="holiday-form" onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <Field label="Date" htmlFor="hd-date" required error={errors.date} hint="Weekdays only">
          <Input
            id="hd-date"
            type="date"
            value={date}
            min={`${year - 1}-01-01`}
            aria-invalid={!!errors.date || undefined}
            onChange={(e) => {
              setDate(e.target.value);
              setErrors((x) => ({ ...x, date: undefined }));
            }}
          />
        </Field>
        <Field label="Name" htmlFor="hd-name" required error={errors.name}>
          <Input id="hd-name" value={name} maxLength={255} placeholder="e.g. Diwali" aria-invalid={!!errors.name || undefined} onChange={(e) => setName(e.target.value)} />
        </Field>
        {serverError && <Notice tone="danger">{serverError}</Notice>}
      </form>
    </Modal>
  );
}
