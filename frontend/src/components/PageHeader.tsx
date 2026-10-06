import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Page title block: 24/600 title, 14 muted subtitle, actions on the right (wrap on phones). */
export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0">
        <h1 className="text-[22px] leading-8 font-semibold tracking-tight text-foreground sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Card with an optional header row (section title 16/600). */
export function Panel({
  title,
  subtitle,
  icon,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn("hr-card min-w-0", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 px-5 pt-4 pb-1">
          <div className="flex min-w-0 items-center gap-2.5">
            {icon && <span className="text-muted-foreground [&_svg]:size-4">{icon}</span>}
            <div className="min-w-0">
              {title && <h2 className="truncate text-base font-semibold text-foreground">{title}</h2>}
              {subtitle && <p className="truncate text-xs font-medium text-muted-foreground">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-5", title || actions ? "pt-3" : "", bodyClassName)}>{children}</div>
    </section>
  );
}
