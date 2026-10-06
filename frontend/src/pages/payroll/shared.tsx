/** Small helpers shared by the payroll views (register + my payslips). */
import { useEffect, useRef } from "react";
import type { SalaryRecord } from "@/lib/types";
import { cn } from "@/lib/utils";

/** `GET /salary` rows also carry the designation (PayrollItem). */
export type PayrollRow = SalaryRecord & { designation?: string | null };

export function isCurrentMonth(month: number, year: number): boolean {
  const now = new Date();
  return year === now.getFullYear() && month === now.getMonth() + 1;
}

export function isFutureMonth(month: number, year: number): boolean {
  const now = new Date();
  return year > now.getFullYear() || (year === now.getFullYear() && month > now.getMonth() + 1);
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** Native checkbox styled with the brand accent; clicks/keys never reach the row underneath. */
export function SelectBox({
  checked,
  indeterminate,
  onChange,
  label,
  disabled,
  className,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = !!indeterminate && !checked;
  }, [indeterminate, checked]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      disabled={disabled}
      aria-label={label}
      onChange={(e) => onChange(e.target.checked)}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
      className={cn("size-4 shrink-0 cursor-pointer align-middle accent-brand disabled:cursor-not-allowed disabled:opacity-40", className)}
    />
  );
}
