/** Loading / empty / error state components used by every data view. */
import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden="true" />;
}

export function LoadingState({ label = "Loading...", className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn("flex flex-col items-center justify-center gap-3 py-14 text-ink-muted", className)}>
      <Spinner className="size-7 text-brand" />
      <p className="text-sm">{label}</p>
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
      <div className="mb-1 flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-400">
        {icon ?? <Inbox className="size-6" />}
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-center justify-center gap-3 px-4 py-12 text-center", className)}>
      <div className="flex size-12 items-center justify-center rounded-full bg-danger-light text-danger">
        <AlertTriangle className="size-6" />
      </div>
      <p className="max-w-md text-sm font-medium text-ink">{message}</p>
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
  children,
}: {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  loadingLabel?: string;
  children: ReactNode;
}) {
  if (loading) return <LoadingState label={loadingLabel} />;
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
    info: "bg-info-light text-blue-800 border-blue-200",
    warning: "bg-warning-light text-amber-800 border-amber-200",
    success: "bg-success-light text-emerald-800 border-emerald-200",
    danger: "bg-danger-light text-red-800 border-red-200",
  };
  return (
    <div className={cn("flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm", tones[tone], className)}>
      {icon && <span className="mt-0.5 shrink-0 [&_svg]:size-4">{icon}</span>}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
