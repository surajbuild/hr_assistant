import { cn } from "@/lib/utils";

/** Product mark: indigo rounded square with "HR". Decorative (the product name always sits next to it). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-brand text-[13px] font-bold tracking-tight text-brand-foreground", className)}
      aria-hidden="true"
    >
      HR
    </span>
  );
}
