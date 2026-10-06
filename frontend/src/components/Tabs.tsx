/** Underline tabs: role="tablist", roving tabindex, ←/→/Home/End keyboard navigation. */
import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TabItem<K extends string> {
  key: K;
  label: ReactNode;
  icon?: ReactNode;
  count?: number;
}

export function Tabs<K extends string>({
  tabs,
  value,
  onChange,
  className,
}: {
  tabs: TabItem<K>[];
  value: K;
  onChange: (key: K) => void;
  className?: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const idx = tabs.findIndex((t) => t.key === value);
    let next = -1;
    if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const target = tabs[next];
    if (!target) return;
    onChange(target.key);
    requestAnimationFrame(() => listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus());
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      onKeyDown={onKeyDown}
      className={cn("scrollbar-none relative flex gap-1 overflow-x-auto border-b border-border", className)}
    >
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.key)}
            className={cn(
              "-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-medium whitespace-nowrap transition-colors duration-150 focus-visible:outline-2 focus-visible:-outline-offset-2 [&_svg]:size-4",
              active ? "border-brand text-brand-subtle-foreground" : "border-transparent text-muted-foreground hover:border-border-strong hover:text-foreground",
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && (
              <span
                className={cn(
                  "rounded-full px-1.5 py-px text-[11px] font-semibold tabular-nums",
                  active ? "bg-brand-subtle text-brand-subtle-foreground" : "bg-surface-muted text-muted-foreground",
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
