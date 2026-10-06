/**
 * Settings → Company policy (admin). Replaces the old hard-coded copy (KI-013) with real data only:
 *  - Policy documents the AI assistant answers from (GET /documents) — managed on the Documents page.
 *  - Holiday calendar (GET /holidays?year=) — national + HR-declared company holidays (D-034).
 *  - Annual leave entitlements as the leave system applies them (GET /leaves/balance/me → `entitled`).
 * Working-hour / late / overtime rules are not exposed by any endpoint, so they are not shown here.
 */
import { useMemo, useState } from "react";
import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, FileText, Palmtree, Upload } from "lucide-react";
import { leaveTypeColor } from "@/components/LeaveBalanceGrid";
import { Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, humanize, parseDate, toISODate } from "@/lib/format";
import { Link, navigate } from "@/lib/router";
import type { HolidayList, HrDocument, LeaveBalance } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function PolicyTab() {
  return (
    <div className="flex flex-col gap-5">
      <Notice tone="info" icon={<FileText />}>
        Policy text is not edited here. The AI assistant answers policy questions from the documents uploaded on the{" "}
        <Link to="/documents" className="font-semibold underline underline-offset-2">
          Documents
        </Link>{" "}
        page and cites the page it used; when no document matches, it falls back to the built-in policy reference.
      </Notice>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col gap-5 lg:col-span-3">
          <DocumentsPanel />
          <EntitlementsPanel />
        </div>
        <HolidaysPanel className="lg:col-span-2" />
      </div>
    </div>
  );
}

// ── Policy documents ─────────────────────────────────────────────────────────

function DocumentsPanel() {
  const { data, loading, error, reload } = useFetch<HrDocument[]>("/documents");
  const docs = data ?? [];
  const passages = docs.reduce((n, d) => n + (d.status === "active" ? (d.chunk_count ?? 0) : 0), 0);
  return (
    <Panel
      title="Policy documents"
      subtitle={!loading && !error && docs.length > 0 ? `${docs.length} document${docs.length === 1 ? "" : "s"} · ${passages} passages searchable by the assistant` : "What the assistant answers policy questions from"}
      icon={<FileText />}
      bodyClassName="p-0 pt-2"
      actions={
        <Button variant="outline" size="sm" onClick={() => navigate("/documents")}>
          Manage <ArrowRight />
        </Button>
      }
    >
      <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading documents..." skeleton={<RowsSkeleton rows={3} />}>
        {docs.length === 0 ? (
          <EmptyState
            icon={<FileText />}
            title="No policy documents yet"
            description="Upload the employee handbook or policy PDFs so the assistant can answer with page citations."
            action={
              <Button size="sm" onClick={() => navigate("/documents")}>
                <Upload /> Upload a document
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-border">
            {docs.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-5 py-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-[10px] font-semibold text-muted-foreground uppercase">
                  {d.file_type}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{d.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    v{d.version ?? 1} · {d.chunk_count ?? 0} passages · uploaded {formatDate(d.upload_date)}
                    {d.uploaded_by_name ? ` by ${d.uploaded_by_name}` : ""}
                  </p>
                </div>
                <StatusBadge status={d.status} />
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ── Leave entitlements ───────────────────────────────────────────────────────

function EntitlementsPanel() {
  const { data, loading, error, reload } = useFetch<LeaveBalance[]>("/leaves/balance/me");
  const items = (data ?? []).filter((b) => b.entitled > 0);
  return (
    <Panel title="Annual leave entitlements" subtitle="Days per calendar year, as applied by the leave system to every employee" icon={<Palmtree />}>
      <AsyncContent
        loading={loading}
        error={error}
        onRetry={reload}
        skeleton={
          <div className="grid grid-cols-3 gap-3" role="status">
            <span className="sr-only">Loading entitlements</span>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        }
      >
        {items.length === 0 ? (
          <EmptyState icon={<Palmtree />} title="No entitlements configured" description="The leave system reports no annual allowances." className="py-6" />
        ) : (
          <>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {items.map((b) => (
                <li key={b.leave_type} className="rounded-lg border border-border p-3.5">
                  <p className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    <span className="size-2 rounded-full" style={{ background: leaveTypeColor(b.leave_type) }} aria-hidden="true" />
                    {humanize(b.leave_type)} leave
                  </p>
                  <p className="mt-1 text-[28px] leading-9 font-semibold tracking-tight text-foreground tabular-nums">
                    {b.entitled}
                    <span className="ml-1 text-sm font-normal text-muted-foreground">days</span>
                  </p>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-muted-foreground">
              Leave days are counted on working days only — weekends and the holidays in the calendar are not deducted. Other leave types (for example
              unpaid) have no fixed allowance and need approval.
            </p>
          </>
        )}
      </AsyncContent>
    </Panel>
  );
}

// ── Holiday calendar ─────────────────────────────────────────────────────────

function HolidaysPanel({ className }: { className?: string }) {
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const { data, loading, error, reload } = useFetch<HolidayList>(`/holidays?year=${year}`);
  const items = data?.year === year ? data.items : [];
  const today = toISODate(new Date());
  const nextId = useMemo(() => items.find((h) => h.date >= today)?.date ?? null, [items, today]);
  const company = items.filter((h) => h.kind === "company").length;

  return (
    <Panel
      title="Holiday calendar"
      subtitle={!loading && !error ? `${items.length} holiday${items.length === 1 ? "" : "s"} in ${year}${company ? ` · ${company} declared by HR` : ""}` : `Holidays in ${year}`}
      icon={<CalendarDays />}
      className={className}
      bodyClassName="p-0 pt-2"
      actions={
        <div className="flex items-center gap-1" role="group" aria-label="Year">
          <Button variant="ghost" size="icon-sm" onClick={() => setYear((y) => y - 1)} disabled={year <= 2000} aria-label="Previous year">
            <ChevronLeft />
          </Button>
          <span className="min-w-12 text-center text-sm font-semibold text-foreground tabular-nums" aria-live="polite">
            {year}
          </span>
          <Button variant="ghost" size="icon-sm" onClick={() => setYear((y) => y + 1)} disabled={year >= 2100} aria-label="Next year">
            <ChevronRight />
          </Button>
        </div>
      }
    >
      <AsyncContent loading={loading} error={error} onRetry={reload} skeleton={<RowsSkeleton rows={6} />}>
        {items.length === 0 ? (
          <EmptyState
            icon={<CalendarDays />}
            title={`No holidays in ${year}`}
            description="Neither national holidays nor company holidays are recorded for this year."
            action={
              year !== thisYear ? (
                <Button variant="outline" size="sm" onClick={() => setYear(thisYear)}>
                  Back to {thisYear}
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y divide-border">
            {items.map((h) => {
              const d = parseDate(h.date);
              const past = h.date < today;
              const isNext = h.date === nextId;
              return (
                <li key={`${h.date}-${h.name}`} className="flex items-center gap-3 px-5 py-2.5">
                  <span
                    className={
                      isNext
                        ? "flex w-11 shrink-0 flex-col items-center rounded-lg bg-brand-subtle py-1 text-brand-subtle-foreground"
                        : "flex w-11 shrink-0 flex-col items-center rounded-lg bg-surface-muted py-1 text-foreground"
                    }
                  >
                    <span className="text-[10px] font-semibold uppercase">{d ? MONTHS[d.getMonth()] : ""}</span>
                    <span className="text-base leading-5 font-semibold tabular-nums">{d ? d.getDate() : "—"}</span>
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className={past ? "truncate text-sm text-muted-foreground" : "truncate text-sm font-medium text-foreground"}>{h.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {h.weekday}
                      {isNext && <span className="font-medium text-brand-subtle-foreground"> · Next holiday</span>}
                    </p>
                  </div>
                  <Badge tone={h.kind === "company" ? "brand" : "neutral"}>{h.kind === "company" ? "Company" : humanize(h.kind)}</Badge>
                </li>
              );
            })}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

function RowsSkeleton({ rows }: { rows: number }) {
  return (
    <div className="flex flex-col gap-3 px-5 py-3" role="status">
      <span className="sr-only">Loading...</span>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-9 shrink-0" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}
