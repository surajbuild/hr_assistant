/** Loading / empty / error state components used by every data view. */
import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden="true" />;
}

/** Skeleton loading state: rows of shimmering bars (announced to screen readers as one status). */
export function LoadingState({ label = "Loading...", className, rows = 4 }: { label?: string; className?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className={cn("flex flex-col gap-3 p-5", className)}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-9 shrink-0 rounded-full" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3 w-2/5" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Full-width block skeletons for card grids (stat cards, panels). */
export function CardSkeletons({ count = 4, className, itemClassName }: { count?: number; className?: string; itemClassName?: string }) {
  return (
    <div role="status" aria-live="polite" className={cn("grid gap-4", className)}>
      <span className="sr-only">Loading...</span>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={cn("hr-card flex flex-col gap-3 p-5", itemClassName)}>
          <Skeleton className="h-3 w-1/3" />
          <Skeleton className="h-7 w-1/2" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title = "Nothing here yet",
  description,
  icon,
  action,
  className,
}: {
  title?: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-4 py-12 text-center", className)}>
      <div className="mb-1 flex size-12 items-center justify-center rounded-xl bg-surface-muted text-muted-foreground [&_svg]:size-6">
        {icon ?? <Inbox />}
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center gap-3 px-4 py-12 text-center", className)}>
      <div className="flex size-12 items-center justify-center rounded-xl bg-status-absent-bg text-status-absent-fg">
        <AlertTriangle className="size-6" />
      </div>
      <p className="max-w-md text-sm font-medium text-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" /> Try again
        </Button>
      )}
    </div>
  );
}

/** Renders loading / error / children for a fetch result. */
export function AsyncContent({
  loading,
  error,
  onRetry,
  loadingLabel,
  skeleton,
  children,
}: {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  loadingLabel?: string;
  /** Custom skeleton; defaults to row skeletons. */
  skeleton?: ReactNode;
  children: ReactNode;
}) {
  if (loading) return <>{skeleton ?? <LoadingState label={loadingLabel} />}</>;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  return <>{children}</>;
}

export function Notice({
  tone = "info",
  icon,
  children,
  className,
}: {
  tone?: "info" | "warning" | "success" | "danger";
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const tones = {
    info: "bg-status-half-bg text-status-half-fg border-status-half/25",
    warning: "bg-status-late-bg text-status-late-fg border-status-late/25",
    success: "bg-status-present-bg text-status-present-fg border-status-present/25",
    danger: "bg-status-absent-bg text-status-absent-fg border-status-absent/25",
  };
  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm", tones[tone], className)}>
      {icon && <span className="mt-0.5 shrink-0 [&_svg]:size-4">{icon}</span>}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
