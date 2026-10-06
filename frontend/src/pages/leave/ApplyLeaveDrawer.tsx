/**
 * Apply for leave — right-side drawer (Radix Dialog → focus trap, Escape, focus returns to the opener).
 * POST /leaves {leave_type, start_date, end_date, reason?}. Shows the remaining balance per type and the working days
 * the request would charge (weekends and holidays excluded — same rule as the backend's count_leave_days).
 */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { CalendarRange, Send } from "lucide-react";
import { Field } from "@/components/Field";
import { Notice } from "@/components/States";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter, DialogHeader, DrawerContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatNumber, humanize, toISODate } from "@/lib/format";
import type { LeaveBalance, LeaveType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { leaveTypeColor } from "@/components/LeaveBalanceGrid";
import { useHolidays, workingDaysBetween, yearsBetween } from "./holidays";

export const LEAVE_TYPES: LeaveType[] = ["casual", "sick", "earned", "unpaid", "maternity", "paternity"];

type Errors = Partial<Record<"start" | "end", string>>;

export function ApplyLeaveDrawer({
  open,
  balances,
  onClose,
  onApplied,
}: {
  open: boolean;
  balances: LeaveBalance[];
  onClose: () => void;
  onApplied: () => void;
}) {
  const toast = useToast();
  const today = toISODate(new Date());
  const [type, setType] = useState<LeaveType>("casual");
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(today);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setServerError(null);
  }, [open]);

  const validRange = !!start && !!end && end >= start;
  const holidays = useHolidays(open && validRange ? yearsBetween(start, end) : []);
  const count = useMemo(() => (validRange ? workingDaysBetween(start, end, holidays.byDate) : { days: 0, holidays: [] }), [validRange, start, end, holidays.byDate]);
  const bal = balances.find((b) => b.leave_type.toLowerCase() === type);
  const balanceByType = new Map(balances.map((b) => [b.leave_type.toLowerCase(), b]));
  const over = bal && validRange && count.days > bal.remaining;

  function reset() {
    setType("casual");
    setStart(today);
    setEnd(today);
    setReason("");
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);
    const errs: Errors = {};
    if (!start) errs.start = "Choose the first day.";
    if (!end) errs.end = "Choose the last day.";
    else if (start && end < start) errs.end = "The last day can't be before the first day.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      await api.post("/leaves", { leave_type: type, start_date: start, end_date: end, reason: reason.trim() || null });
      toast.success(`${humanize(type)} leave requested for ${formatDate(start)}${end !== start ? ` – ${formatDate(end)}` : ""}.`);
      reset();
      onApplied();
    } catch (error) {
      const msg = errorMessage(error, "Failed to submit the leave request.");
      setServerError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !saving && onClose()}>
      <DrawerContent side="right" aria-describedby={undefined}>
        <DialogHeader title="Apply for leave" description="Your manager or HR will review the request." />
        <form id="apply-leave-form" onSubmit={submit} noValidate className="flex flex-1 flex-col gap-5 overflow-y-auto px-5 py-4">
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-foreground">Leave type</legend>
            <div className="grid grid-cols-2 gap-2">
              {LEAVE_TYPES.map((t) => {
                const b = balanceByType.get(t);
                const active = type === t;
                return (
                  <label
                    key={t}
                    className={cn(
                      "relative flex cursor-pointer flex-col gap-0.5 rounded-lg border px-3 py-2.5 transition-colors duration-150 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                      active ? "border-brand bg-brand-subtle" : "border-border hover:border-border-strong hover:bg-accent",
                    )}
                  >
                    <input type="radio" name="leave-type" value={t} checked={active} onChange={() => setType(t)} className="sr-only" />
                    <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <span className="size-2 rounded-full" style={{ background: leaveTypeColor(t) }} aria-hidden="true" />
                      {humanize(t)}
                    </span>
                    <span className="text-xs text-muted-foreground tabular-nums">{b ? `${formatNumber(b.remaining, 1)} of ${formatNumber(b.entitled, 1)} left` : "No fixed balance"}</span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="grid grid-cols-2 gap-3">
            <Field label="From" htmlFor="lv-from" required error={errors.start}>
              <Input
                id="lv-from"
                type="date"
                value={start}
                aria-invalid={!!errors.start || undefined}
                onChange={(e) => {
                  const v = e.target.value;
                  setStart(v);
                  if (v && (!end || end < v)) setEnd(v);
                }}
              />
            </Field>
            <Field label="To" htmlFor="lv-to" required error={errors.end}>
              <Input id="lv-to" type="date" min={start || undefined} value={end} aria-invalid={!!errors.end || undefined} onChange={(e) => setEnd(e.target.value)} />
            </Field>
          </div>

          <div className="rounded-xl border border-border bg-surface-muted p-4" aria-live="polite">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-lg bg-brand-subtle text-brand-subtle-foreground">
                <CalendarRange className="size-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-2xl leading-7 font-semibold text-foreground tabular-nums">
                  {validRange ? count.days : 0} <span className="text-sm font-medium text-muted-foreground">working day{count.days === 1 ? "" : "s"}</span>
                </p>
                <p className="text-xs text-muted-foreground">Weekends and holidays are not charged</p>
              </div>
            </div>
            {count.holidays.length > 0 && (
              <p className="mt-3 text-xs text-muted-foreground">
                Includes {count.holidays.length === 1 ? "a holiday" : `${count.holidays.length} holidays`}: {count.holidays.map((h) => `${h.name} (${formatDate(h.date)})`).join(", ")}.
              </p>
            )}
            {bal && validRange && (
              <p className={cn("mt-3 text-xs tabular-nums", over ? "font-medium text-status-late-fg" : "text-muted-foreground")}>
                {over
                  ? `This is more than your remaining ${humanize(type).toLowerCase()} balance (${formatNumber(bal.remaining, 1)} days).`
                  : `${formatNumber(bal.remaining - count.days, 1)} ${humanize(type).toLowerCase()} days left after this request${bal.pending > 0 ? ` (plus ${formatNumber(bal.pending, 1)} already pending)` : ""}.`}
              </p>
            )}
            {validRange && count.days === 0 && !holidays.loading && <p className="mt-3 text-xs font-medium text-status-late-fg">The selected dates are all weekends or holidays.</p>}
          </div>

          <Field label="Reason" htmlFor="lv-reason" hint="Optional, visible to your approver">
            <Textarea id="lv-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Briefly describe the reason" />
          </Field>
          {serverError && <Notice tone="danger">{serverError}</Notice>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="apply-leave-form" loading={saving}>
            {!saving && <Send />} Submit request
          </Button>
        </DialogFooter>
      </DrawerContent>
    </Dialog>
  );
}
