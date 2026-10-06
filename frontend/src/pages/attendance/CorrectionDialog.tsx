/**
 * "Request correction" (regularization, D-033): POST /attendance/corrections {attendance_date, in_time, out_time, reason}.
 * Client checks mirror the backend (422: future date / before joining / out ≤ in / no reason; 409: pending request for
 * that date / salary of that month already paid) so the user sees the problem before submitting; server messages are
 * still shown inline if it refuses.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import { Field } from "@/components/Field";
import { Modal } from "@/components/Modal";
import { Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { formatDate, formatMinutes, formatTime } from "@/lib/format";
import type { AttendanceCorrection, AttendanceRecord } from "@/lib/types";
import { hhmm, monthName, monthOf, toMinutes, withSeconds } from "./shared";

export interface CorrectionContext {
  records: Map<string, AttendanceRecord>;
  pending: Map<string, AttendanceCorrection>;
  paidMonths: Set<string>;
  joiningDate: string | null;
  today: string;
}

/** Why a correction can't be requested for `iso` (null = allowed). Same rules the API enforces. */
export function correctionBlock(iso: string, ctx: CorrectionContext): string | null {
  if (!iso) return "Choose a date.";
  if (iso > ctx.today) return "You can't correct a future date.";
  if (ctx.joiningDate && iso < ctx.joiningDate) return `The date is before your joining date (${formatDate(ctx.joiningDate)}).`;
  if (ctx.paidMonths.has(monthOf(iso))) return `Salary for ${monthName(monthOf(iso))} is already paid — attendance for that month is locked.`;
  if (ctx.pending.has(iso)) return "You already have a pending correction request for this date.";
  return null;
}

type Errors = Partial<Record<"date" | "in" | "out" | "reason", string>>;

export function CorrectionDialog({
  open,
  initialDate,
  ctx,
  onClose,
  onCreated,
}: {
  open: boolean;
  initialDate: string | null;
  ctx: CorrectionContext;
  onClose: () => void;
  onCreated: (c: AttendanceCorrection) => void;
}) {
  const toast = useToast();
  const [date, setDate] = useState("");
  const [inTime, setInTime] = useState("09:00");
  const [outTime, setOutTime] = useState("18:00");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Prefill from the chosen day each time the dialog opens
  useEffect(() => {
    if (!open) return;
    const d = initialDate ?? ctx.today;
    const rec = ctx.records.get(d);
    setDate(d);
    setInTime(hhmm(rec?.in_time) || "09:00");
    setOutTime(hhmm(rec?.out_time) || "18:00");
    setReason("");
    setErrors({});
    setServerError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialDate]);

  const current = date ? ctx.records.get(date) : undefined;
  const a = toMinutes(inTime);
  const b = toMinutes(outTime);
  const span = a !== null && b !== null && b > a ? b - a : null;
  const block = date ? correctionBlock(date, ctx) : null;

  function validate(): Errors {
    const e: Errors = {};
    if (!date) e.date = "Choose the day to correct.";
    else if (block) e.date = block;
    if (!inTime) e.in = "Enter the in time.";
    if (!outTime) e.out = "Enter the out time.";
    else if (a !== null && b !== null && b <= a) e.out = "Out time must be after in time.";
    if (!reason.trim()) e.reason = "Tell your approver why this day needs correcting.";
    return e;
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    setSaving(true);
    try {
      const created = await api.post<AttendanceCorrection>("/attendance/corrections", {
        attendance_date: date,
        in_time: withSeconds(inTime),
        out_time: withSeconds(outTime),
        reason: reason.trim(),
      });
      toast.success(`Correction request sent for ${formatDate(date)}.`);
      onCreated(created);
    } catch (err) {
      const msg = errorMessage(err, "Failed to send the correction request.");
      setServerError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={saving ? () => undefined : onClose}
      title="Request attendance correction"
      description="Your manager or HR reviews it. Once approved, the day is recalculated automatically."
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="correction-form" loading={saving}>
            {!saving && <Send />} Send request
          </Button>
        </>
      }
    >
      <form id="correction-form" onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2" noValidate>
        <Field label="Date" htmlFor="cr-date" required error={errors.date} className="sm:col-span-2">
          <Input
            id="cr-date"
            type="date"
            value={date}
            max={ctx.today}
            min={ctx.joiningDate ?? undefined}
            aria-invalid={!!errors.date || undefined}
            onChange={(e) => {
              const d = e.target.value;
              setDate(d);
              const rec = ctx.records.get(d);
              if (rec?.in_time) setInTime(hhmm(rec.in_time));
              if (rec?.out_time) setOutTime(hhmm(rec.out_time));
              setErrors((x) => ({ ...x, date: undefined }));
            }}
          />
        </Field>

        <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5 text-sm sm:col-span-2">
          <p className="text-xs font-medium text-muted-foreground">Current record</p>
          {current ? (
            <p className="mt-1 flex flex-wrap items-center gap-2 text-foreground">
              <StatusBadge status={current.status === "present" && current.late_minutes > 0 ? "late" : current.status} />
              <span className="tabular-nums">
                {formatTime(current.in_time)} – {formatTime(current.out_time)}
              </span>
              {current.working_minutes ? <span className="text-muted-foreground tabular-nums">· {formatMinutes(current.working_minutes)} worked</span> : null}
            </p>
          ) : (
            <p className="mt-1 text-muted-foreground">No attendance recorded for this day.</p>
          )}
          {!errors.date && block && <p className="mt-1.5 text-xs font-medium text-status-late-fg">{block}</p>}
        </div>

        <Field label="In time" htmlFor="cr-in" required error={errors.in}>
          <Input id="cr-in" type="time" value={inTime} aria-invalid={!!errors.in || undefined} onChange={(e) => setInTime(e.target.value)} />
        </Field>
        <Field label="Out time" htmlFor="cr-out" required error={errors.out} hint={span !== null ? `${formatMinutes(span)} between in and out` : undefined}>
          <Input id="cr-out" type="time" value={outTime} aria-invalid={!!errors.out || undefined} onChange={(e) => setOutTime(e.target.value)} />
        </Field>
        <Field label="Reason" htmlFor="cr-reason" required error={errors.reason} className="sm:col-span-2" hint="e.g. Forgot to check out, client visit, biometric failure">
          <Textarea
            id="cr-reason"
            rows={3}
            maxLength={1000}
            value={reason}
            aria-invalid={!!errors.reason || undefined}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why does this day need correcting?"
          />
        </Field>
        <p className="text-xs text-muted-foreground sm:col-span-2">
          Status (present or half day), late and overtime minutes are calculated by the system from these times.
        </p>
        {serverError && (
          <Notice tone="danger" className="sm:col-span-2">
            {serverError}
          </Notice>
        )}
      </form>
    </Modal>
  );
}
