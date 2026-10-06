/** Initials avatar with a deterministic colour from the person's name (or an explicit seed such as the user id). */
import { initials } from "@/lib/format";
import { cn } from "@/lib/utils";

const COUNT = 8;

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

const SIZES = {
  xs: "size-6 text-[10px]",
  sm: "size-7 text-[11px]",
  md: "size-9 text-xs",
  lg: "size-12 text-sm",
  xl: "size-20 text-2xl",
} as const;

export function Avatar({
  name,
  seed,
  size = "md",
  className,
}: {
  name: string | null | undefined;
  /** Optional stable seed (e.g. user id) for the colour; defaults to the name. */
  seed?: string | number | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const n = (hash(String(seed ?? name ?? "")) % COUNT) + 1;
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full font-semibold select-none", SIZES[size], className)}
      style={{ background: `var(--avatar-${n}-bg)`, color: `var(--avatar-${n}-fg)` }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
