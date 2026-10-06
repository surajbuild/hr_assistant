/**
 * DataTable — sticky header, hover rows, click-to-sort headers, client-side pagination, keyboard-focusable rows
 * (Enter/Space activates `onRowClick`), and a phone fallback.
 *
 * Backwards compatible with the original Column API (key/header/render/className/headerClassName/align). New, all optional:
 *  - Column.sortValue    → makes the header sortable (return a string | number | null for the row)
 *  - Column.hideOnMobile → column hidden in the phone card layout
 *  - pageSize            → paginate (footer with range + prev/next)
 *  - mobileCard          → render each row as a card below `md` instead of a scrolling table
 *  - maxHeight           → scroll the body inside the card so the header stays sticky
 * Tables always scroll horizontally INSIDE their card on narrow screens (never the page).
 */
import { useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { EmptyState } from "./States";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T, index: number) => ReactNode;
  className?: string;
  headerClassName?: string;
  align?: "left" | "right" | "center";
  sortValue?: (row: T) => string | number | null | undefined;
  hideOnMobile?: boolean;
  /** Plain-text name for the sort button's accessible label (when `header` isn't a string). */
  label?: string;
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty,
  onRowClick,
  className,
  dense,
  pageSize,
  mobileCard,
  maxHeight,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  className?: string;
  dense?: boolean;
  pageSize?: number;
  mobileCard?: (row: T, index: number) => ReactNode;
  maxHeight?: string;
}) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    const get = col?.sortValue;
    if (!get) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = get(a);
      const bv = get(b);
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * factor;
      return String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" }) * factor;
    });
  }, [rows, sort, columns]);

  const pageCount = pageSize ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1;
  useEffect(() => {
    if (page > pageCount - 1) setPage(pageCount - 1);
  }, [page, pageCount]);
  const visible = pageSize ? sorted.slice(page * pageSize, page * pageSize + pageSize) : sorted;

  if (rows.length === 0) {
    return <>{empty ?? <EmptyState title="No records found" />}</>;
  }

  const alignClass = (a?: "left" | "right" | "center") => (a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left");

  function toggleSort(key: string) {
    setPage(0);
    setSort((s) => (s?.key !== key ? { key, dir: "asc" } : s.dir === "asc" ? { key, dir: "desc" } : null));
  }

  function onRowKey(e: KeyboardEvent<HTMLTableRowElement>, row: T) {
    if (e.target !== e.currentTarget) return; // let inner buttons handle their own keys
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick?.(row);
    }
  }

  const table = (
    // `relative` makes the scroller the containing block for absolutely positioned children (e.g. sr-only header
    // labels) so they stay inside the scroll area instead of widening the page on phones.
    <div className={cn("relative w-full overflow-x-auto", maxHeight && "overflow-y-auto", mobileCard && "hidden md:block", className)} style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full min-w-max border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-border bg-surface-muted">
            {columns.map((c) => {
              const active = sort?.key === c.key;
              const sortable = !!c.sortValue;
              const name = c.label ?? (typeof c.header === "string" ? c.header : c.key);
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort?.dir === "asc" ? "ascending" : "descending") : sortable ? "none" : undefined}
                  className={cn("px-3 py-2.5 text-xs font-medium whitespace-nowrap text-muted-foreground first:pl-5 last:pr-5", alignClass(c.align), c.headerClassName)}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(c.key)}
                      aria-label={`Sort by ${name}`}
                      className={cn(
                        "-mx-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors hover:bg-accent hover:text-foreground",
                        c.align === "right" && "flex-row-reverse",
                        active && "text-foreground",
                      )}
                    >
                      {c.header}
                      {active ? sort?.dir === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" /> : <ChevronsUpDown className="size-3 opacity-50" />}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => (
            <tr
              key={rowKey(row, i)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (e) => onRowKey(e, row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              className={cn(
                "border-b border-border transition-colors duration-150 last:border-0 hover:bg-accent/60",
                onRowClick && "cursor-pointer focus-visible:bg-accent focus-visible:outline-2 focus-visible:-outline-offset-2",
              )}
            >
              {columns.map((c) => (
                <td key={c.key} className={cn("px-3 whitespace-nowrap text-foreground first:pl-5 last:pr-5", dense ? "py-2" : "py-3", alignClass(c.align), c.className)}>
                  {c.render(row, i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const cards = mobileCard && (
    <ul className="divide-y divide-border md:hidden">
      {visible.map((row, i) => (
        <li key={rowKey(row, i)}>{mobileCard(row, i)}</li>
      ))}
    </ul>
  );

  return (
    <>
      {table}
      {cards}
      {pageSize && <Pagination page={page} pageSize={pageSize} total={sorted.length} onPage={setPage} />}
    </>
  );
}

/** Footer with "a–b of n" and prev/next. Renders nothing when everything fits on one page. */
export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  if (total <= pageSize) return null;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
      <span className="tabular-nums">
        {page * pageSize + 1}–{Math.min(total, page * pageSize + pageSize)} of {total}
      </span>
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="icon-sm" onClick={() => onPage(Math.max(0, page - 1))} disabled={page === 0} aria-label="Previous page">
          <ChevronLeft />
        </Button>
        <span className="min-w-14 text-center tabular-nums">
          {page + 1} / {pageCount}
        </span>
        <Button variant="outline" size="icon-sm" onClick={() => onPage(Math.min(pageCount - 1, page + 1))} disabled={page >= pageCount - 1} aria-label="Next page">
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
