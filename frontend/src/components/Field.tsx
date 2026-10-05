/** Form helpers: labelled field wrapper, native select, search input, month/year pickers. */
import type { ComponentProps, ReactNode } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MONTHS_LONG } from "@/lib/format";
import { cn } from "@/lib/utils";

export function Field({
  label,
  htmlFor,
  hint,
  error,
  required,
  children,
  className,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={htmlFor} className="text-[13px] text-ink">
        {label}
        {required && <span className="text-danger">*</span>}
      </Label>
      {children}
      {error ? <p className="text-xs text-danger">{error}</p> : hint ? <p className="text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}

export function NativeSelect({ className, children, ...props }: ComponentProps<"select">) {
  return (
    <select className={cn("hr-select", className)} {...props}>
      {children}
    </select>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-muted" />
      <Input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="bg-white pl-8"
      />
    </div>
  );
}

export function MonthSelect({
  value,
  onChange,
  className,
  allowAll,
}: {
  value: number;
  onChange: (m: number) => void;
  className?: string;
  allowAll?: boolean;
}) {
  return (
    <NativeSelect value={value} onChange={(e) => onChange(Number(e.target.value))} className={className} aria-label="Month">
      {allowAll && <option value={0}>All months</option>}
      {MONTHS_LONG.map((m, i) => (
        <option key={m} value={i + 1}>
          {m}
        </option>
      ))}
    </NativeSelect>
  );
}

export function YearSelect({
  value,
  onChange,
  className,
  years,
}: {
  value: number;
  onChange: (y: number) => void;
  className?: string;
  years?: number[];
}) {
  const now = new Date().getFullYear();
  const list = years ?? Array.from({ length: now - 2021 + 2 }, (_, i) => now + 1 - i);
  if (!list.includes(value)) list.push(value);
  list.sort((a, b) => b - a);
  return (
    <NativeSelect value={value} onChange={(e) => onChange(Number(e.target.value))} className={className} aria-label="Year">
      {list.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </NativeSelect>
  );
}
