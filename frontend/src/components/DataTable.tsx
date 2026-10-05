/** Simple responsive table: scrolls horizontally inside its container on narrow screens. */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { EmptyState } from "./States";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T, index: number) => ReactNode;
  className?: string;
  headerClassName?: string;
  align?: "left" | "right" | "center";
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty,
  onRowClick,
  className,
  dense,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  className?: string;
  dense?: boolean;
}) {
  if (rows.length === 0) {
    return <>{empty ?? <EmptyState title="No records found" />}</>;
  }
  const alignClass = (a?: "left" | "right" | "center") =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left";

  // `relative` makes the scroller the containing block for absolutely positioned children (e.g. sr-only
  // header labels), so they stay inside the scroll area instead of widening the page on phones.
  return (
    <div className={cn("relative w-full overflow-x-auto", className)}>
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-border bg-slate-50/80">
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cn(
                  "whitespace-nowrap px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-muted",
                  alignClass(c.align),
                  c.headerClassName,
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={rowKey(row, i)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                "border-b border-border last:border-0 transition-colors hover:bg-slate-50",
                onRowClick && "cursor-pointer",
              )}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={cn("whitespace-nowrap px-4 text-ink", dense ? "py-2" : "py-3", alignClass(c.align), c.className)}
                >
                  {c.render(row, i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
