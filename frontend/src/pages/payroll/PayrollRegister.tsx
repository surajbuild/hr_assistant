/**
 * Payroll register (HR / Admin): GET /salary?month&year + /salary/summary, search, paid filter, CSV export,
 * payslip modal, "Generate payroll" (POST /salary/generate) and "Mark as paid" (POST /salary/mark-paid, D-036 —
 * irreversible, paid rows are locked). Selection only offers unpaid rows; paid rows show a lock.
 */
import { useEffect, useMemo, useState } from "react";
import { Banknote, BadgeCheck, Calculator, Download, Eye, Landmark, Lock, MinusCircle, MoreHorizontal, PiggyBank, RefreshCw, TrendingUp, Wallet } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { DataTable } from "@/components/DataTable";
import { MonthSelect, SearchInput, YearSelect } from "@/components/Field";
import { GeneratePayrollModal } from "@/components/GeneratePayrollModal";
import { ConfirmDialog } from "@/components/Modal";
import { PageHeader } from "@/components/PageHeader";
import { PayslipModal } from "@/components/PayslipModal";
import { Segmented } from "@/components/Segmented";
import { StatCard } from "@/components/StatCard";
import { AsyncContent, EmptyState, Notice } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { api, errorMessage, qs } from "@/lib/api";
import { downloadCSV, formatDate, formatINR, monthLabel } from "@/lib/format";
import type { MarkPaidResult, SalaryList, SalarySummary } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { isCurrentMonth, isFutureMonth, plural, SelectBox, type PayrollRow } from "./shared";

type PaidFilter = "all" | "unpaid" | "paid";

const PAID_OPTIONS: { value: PaidFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unpaid", label: "Unpaid" },
  { value: "paid", label: "Paid" },
];

const sum = (rows: PayrollRow[], pick: (r: PayrollRow) => number) => rows.reduce((t, r) => t + Number(pick(r) || 0), 0);

export function PayrollRegister() {
  const toast = useToast();
  const [sel, setSel] = useState<{ month: number; year: number } | null>(null);
  const list = useFetch<SalaryList>(`/salary${qs({ month: sel?.month, year: sel?.year })}`);
  const now = new Date();
  const month = sel?.month ?? list.data?.month ?? now.getMonth() + 1;
  const year = sel?.year ?? list.data?.year ?? now.getFullYear();
  const summary = useFetch<SalarySummary>(list.data || sel ? `/salary/summary${qs({ month, year })}` : null);
  const period = monthLabel(month, year);
  const isFuture = isFutureMonth(month, year);
  const isCurrent = isCurrentMonth(month, year);

  const [search, setSearch] = useState("");
  const [paidFilter, setPaidFilter] = useState<PaidFilter>("all");
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [slip, setSlip] = useState<PayrollRow | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [confirmIds, setConfirmIds] = useState<number[] | null>(null);
  const [marking, setMarking] = useState(false);

  // A new period starts with an empty selection.
  useEffect(() => setSelected(new Set()), [month, year]);

  const items: PayrollRow[] = list.data?.items ?? [];
  const q = search.trim().toLowerCase();
  const rows = items.filter((r) => {
    if (paidFilter === "paid" && !r.paid_at) return false;
    if (paidFilter === "unpaid" && r.paid_at) return false;
    return !q || [r.employee_name, r.employee_code, r.department].some((v) => (v ?? "").toLowerCase().includes(q));
  });

  const paidCount = items.filter((r) => r.paid_at).length;
  const unpaidItems = items.filter((r) => !r.paid_at);
  const outstanding = sum(unpaidItems, (r) => r.net_salary);
  const selectedRows = useMemo(() => items.filter((r) => !r.paid_at && selected.has(r.id)), [items, selected]);
  const selectedNet = sum(selectedRows, (r) => r.net_salary);
  const visibleUnpaid = rows.filter((r) => !r.paid_at);
  const allVisibleSelected = visibleUnpaid.length > 0 && visibleUnpaid.every((r) => selected.has(r.id));
  const someVisibleSelected = visibleUnpaid.some((r) => selected.has(r.id));
  const confirmRows = confirmIds ? items.filter((r) => confirmIds.includes(r.id)) : [];
  const confirmNet = sum(confirmRows, (r) => r.net_salary);

  function toggle(id: number, on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleAllVisible(on: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const r of visibleUnpaid) {
        if (on) next.add(r.id);
        else next.delete(r.id);
      }
      return next;
    });
  }

  function exportCSV() {
    downloadCSV(
      `payroll_${year}_${String(month).padStart(2, "0")}.csv`,
      ["Code", "Employee", "Department", "Month", "Year", "Gross", "Overtime", "PF", "Deductions", "Net", "Status", "Paid At"],
      rows.map((r) => [r.employee_code, r.employee_name, r.department, r.month, r.year, r.gross_salary, r.overtime_amount, r.pf, r.deductions, r.net_salary, r.paid_at ? "Paid" : "Unpaid", r.paid_at]),
    );
  }

  async function markPaid() {
    if (!confirmIds?.length) return;
    setMarking(true);
    try {
      const res = await api.post<MarkPaidResult>("/salary/mark-paid", { salary_ids: confirmIds });
      if (res.marked.length) toast.success(`${plural(res.marked.length, "salary", "salaries")} for ${period} marked as paid on ${formatDate(res.paid_at)}.`);
      if (res.already_paid.length) toast.info(`${plural(res.already_paid.length, "salary was", "salaries were")} already paid and left unchanged.`);
      if (res.not_found.length) toast.error(`${plural(res.not_found.length, "salary row")} no longer exist${res.not_found.length === 1 ? "s" : ""} — the register was refreshed.`);
      const marked = new Set(res.marked);
      list.setData((prev) => (prev ? { ...prev, items: prev.items.map((r) => (marked.has(r.id) ? { ...r, paid_at: res.paid_at } : r)) } : prev));
      if (res.already_paid.length || res.not_found.length) list.reload();
      setSelected(new Set());
      setConfirmIds(null);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to mark salaries as paid."));
    } finally {
      setMarking(false);
    }
  }

  /** Row menu (plain render function — not a component, so open menus survive re-renders). */
  function rowMenu(r: PayrollRow) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${r.employee_name ?? "employee"}`} onClick={(e) => e.stopPropagation()}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onSelect={() => setSlip(r)}>
            <Eye /> View payslip
          </DropdownMenuItem>
          {!r.paid_at && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => setConfirmIds([r.id])}>
                <BadgeCheck /> Mark as paid
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  function statusBadge(r: PayrollRow) {
    return (
      <span className="inline-flex flex-col items-start gap-0.5">
        <StatusBadge status={r.paid_at ? "paid" : "unpaid"} label={r.paid_at ? "Paid" : "Unpaid"} />
        {r.paid_at && <span className="text-xs text-muted-foreground tabular-nums">{formatDate(r.paid_at)}</span>}
      </span>
    );
  }

  function selectCell(r: PayrollRow) {
    return r.paid_at ? (
      <span className="inline-flex size-4 items-center justify-center text-muted-foreground" title="Paid — locked">
        <Lock className="size-3.5" aria-hidden="true" />
        <span className="sr-only">Paid, locked</span>
      </span>
    ) : (
      <SelectBox checked={selected.has(r.id)} onChange={(on) => toggle(r.id, on)} label={`Select ${r.employee_name ?? "row"}`} />
    );
  }

  const hasFilters = !!(q || paidFilter !== "all");
  const loadingKpis = list.loading || (summary.loading && !summary.data);
  const s = summary.data;

  const empty = hasFilters ? (
    <EmptyState
      icon={<Wallet />}
      title="No salary rows match"
      description="Try a different search or show all statuses."
      action={
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setSearch("");
            setPaidFilter("all");
          }}
        >
          Clear filters
        </Button>
      }
    />
  ) : (
    <EmptyState
      icon={<Wallet />}
      title={`No payroll for ${period}`}
      description={isFuture ? "Payroll can't be generated for a future month. Pick an earlier month." : "Generate payroll to calculate this month's salaries from attendance and leave."}
      action={
        !isFuture ? (
          <Button size="sm" onClick={() => setGenerateOpen(true)}>
            <Calculator /> Generate payroll
          </Button>
        ) : undefined
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Payroll"
        subtitle={`Salary register · ${period}`}
        actions={
          <>
            <MonthSelect value={month} onChange={(m) => setSel({ month: m, year })} className="w-[8.5rem]" />
            <YearSelect value={year} onChange={(y) => setSel({ month, year: y })} className="w-24" />
            <Button variant="outline" onClick={exportCSV} disabled={rows.length === 0}>
              <Download /> Export CSV
            </Button>
            <Button onClick={() => setGenerateOpen(true)} disabled={isFuture} title={isFuture ? "Payroll cannot be generated for a future month" : undefined}>
              <Calculator /> Generate payroll
            </Button>
          </>
        }
      />

      {isFuture && (
        <Notice tone="warning" className="mb-5">
          {period} is in the future — payroll can only be generated for the current month or earlier.
        </Notice>
      )}
      {isCurrent && items.length > 0 && (
        <Notice tone="info" className="mb-5">
          {period} is still in progress — these figures are provisional until the month ends. Re-run Generate payroll to refresh unpaid rows.
        </Notice>
      )}
      {summary.error && !list.loading && items.length > 0 && (
        <Notice tone="danger" className="mb-5">
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            Totals could not be loaded: {summary.error}
            <Button variant="outline" size="sm" onClick={summary.reload}>
              <RefreshCw /> Retry
            </Button>
          </span>
        </Notice>
      )}

      {(loadingKpis || items.length > 0) && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-6">
          <StatCard
            loading={loadingKpis}
            label="Net payout"
            numeric={Number(s?.total_net_salary ?? sum(items, (r) => r.net_salary))}
            format={(n) => formatINR(n)}
            hint={plural(s?.employee_count ?? items.length, "employee")}
            icon={<Landmark />}
            tone="brand"
          />
          <StatCard loading={loadingKpis} label="Gross" numeric={Number(s?.total_gross_salary ?? sum(items, (r) => r.gross_salary))} format={(n) => formatINR(n)} icon={<Banknote />} tone="brand" />
          <StatCard loading={loadingKpis} label="Overtime" numeric={Number(s?.total_overtime_amount ?? sum(items, (r) => r.overtime_amount))} format={(n) => formatINR(n)} icon={<TrendingUp />} tone="brand" />
          <StatCard loading={loadingKpis} label="PF" numeric={Number(s?.total_pf ?? sum(items, (r) => r.pf))} format={(n) => formatINR(n)} icon={<PiggyBank />} tone="neutral" />
          <StatCard loading={loadingKpis} label="Other deductions" numeric={Number(s?.total_deductions ?? sum(items, (r) => r.deductions))} format={(n) => formatINR(n)} icon={<MinusCircle />} tone="neutral" />
          <StatCard
            loading={loadingKpis}
            label="Paid"
            value={`${paidCount} / ${items.length}`}
            hint={unpaidItems.length ? `${formatINR(outstanding)} unpaid` : "All salaries paid"}
            icon={<BadgeCheck />}
            tone={unpaidItems.length ? "late" : "present"}
          />
        </div>
      )}

      <section className="hr-card min-w-0">
        <header className="flex flex-col gap-3 border-b border-border px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-2.5">
            <Wallet className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-foreground">Salary register</h2>
              <p className="truncate text-xs font-medium text-muted-foreground tabular-nums" aria-live="polite">
                {list.loading ? "Loading…" : `${rows.length} of ${plural(items.length, "record")} · ${paidCount} paid`}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Segmented label="Payment status" value={paidFilter} onChange={setPaidFilter} options={PAID_OPTIONS} />
            <SearchInput value={search} onChange={setSearch} placeholder="Search employees..." className="w-full sm:w-64" />
          </div>
        </header>

        {selectedRows.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-brand-subtle px-5 py-2.5 text-sm text-brand-subtle-foreground" role="region" aria-label="Selection">
            <p className="font-medium tabular-nums" aria-live="polite">
              {plural(selectedRows.length, "row")} selected · {formatINR(selectedNet)} net
            </p>
            <div className="flex items-center gap-2 sm:ml-auto">
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
              <Button size="sm" onClick={() => setConfirmIds(selectedRows.map((r) => r.id))}>
                <BadgeCheck /> Mark as paid
              </Button>
            </div>
          </div>
        )}

        <AsyncContent loading={list.loading} error={list.error} onRetry={list.reload} loadingLabel="Loading payroll...">
          {rows.length > 0 && visibleUnpaid.length > 0 && (
            <div className="flex items-center gap-3 border-b border-border px-4 py-2.5 md:hidden">
              <SelectBox checked={allVisibleSelected} indeterminate={someVisibleSelected} onChange={toggleAllVisible} label="Select all unpaid rows" />
              <span className="text-xs text-muted-foreground">Select all unpaid ({visibleUnpaid.length})</span>
            </div>
          )}
          <DataTable
            rows={rows}
            rowKey={(r) => r.id}
            onRowClick={setSlip}
            pageSize={25}
            empty={empty}
            mobileCard={(r) => (
              <div className="flex items-center gap-3 px-4 py-3">
                {selectCell(r)}
                <button type="button" onClick={() => setSlip(r)} className="flex min-w-0 flex-1 items-center gap-3 rounded-md text-left" aria-label={`View payslip of ${r.employee_name ?? "employee"}`}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{r.employee_name ?? `#${r.employee_id}`}</p>
                    <p className="truncate text-xs text-muted-foreground">{[r.employee_code, r.department].filter(Boolean).join(" · ")}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="text-sm font-semibold text-foreground tabular-nums">{formatINR(r.net_salary)}</span>
                    <StatusBadge status={r.paid_at ? "paid" : "unpaid"} />
                  </div>
                </button>
              </div>
            )}
            columns={[
              {
                key: "select",
                header:
                  visibleUnpaid.length > 0 ? (
                    <SelectBox checked={allVisibleSelected} indeterminate={someVisibleSelected} onChange={toggleAllVisible} label="Select all unpaid rows" />
                  ) : (
                    <span className="sr-only">Selection</span>
                  ),
                headerClassName: "w-8",
                render: (r) => selectCell(r),
              },
              {
                key: "emp",
                header: "Employee",
                label: "employee",
                sortValue: (r) => r.employee_name,
                render: (r) => (
                  <div className="flex items-center gap-3">
                    <Avatar name={r.employee_name} size="sm" />
                    <div>
                      <p className="font-medium text-foreground">{r.employee_name ?? `#${r.employee_id}`}</p>
                      <p className="text-xs text-muted-foreground">{[r.employee_code, r.department].filter(Boolean).join(" · ")}</p>
                    </div>
                  </div>
                ),
              },
              { key: "gross", header: "Gross", align: "right", sortValue: (r) => Number(r.gross_salary), render: (r) => <span className="tabular-nums">{formatINR(r.gross_salary)}</span> },
              { key: "ot", header: "Overtime", align: "right", sortValue: (r) => Number(r.overtime_amount), render: (r) => <span className="tabular-nums">{formatINR(r.overtime_amount)}</span> },
              { key: "pf", header: "PF", align: "right", sortValue: (r) => Number(r.pf), render: (r) => <span className="tabular-nums">{formatINR(r.pf)}</span> },
              { key: "ded", header: "Deductions", align: "right", sortValue: (r) => Number(r.deductions), render: (r) => <span className="tabular-nums">{formatINR(r.deductions)}</span> },
              {
                key: "net",
                header: "Net pay",
                align: "right",
                sortValue: (r) => Number(r.net_salary),
                render: (r) => <span className="font-semibold text-foreground tabular-nums">{formatINR(r.net_salary)}</span>,
              },
              { key: "paid", header: "Status", sortValue: (r) => r.paid_at ?? "", render: (r) => statusBadge(r) },
              {
                key: "actions",
                header: <span className="sr-only">Actions</span>,
                align: "right",
                render: (r) => (
                  <div className="flex justify-end" onClick={(e) => e.stopPropagation()}>
                    {rowMenu(r)}
                  </div>
                ),
              },
            ]}
          />
        </AsyncContent>
      </section>

      <PayslipModal
        slip={slip}
        onClose={() => setSlip(null)}
        actions={
          slip && !slip.paid_at ? (
            <Button
              onClick={() => {
                const id = slip.id;
                setSlip(null);
                setConfirmIds([id]);
              }}
            >
              <BadgeCheck /> Mark as paid
            </Button>
          ) : undefined
        }
      />

      <ConfirmDialog
        open={confirmIds !== null}
        tone="default"
        title={confirmRows.length === 1 ? "Mark salary as paid?" : "Mark salaries as paid?"}
        confirmLabel={confirmRows.length === 1 ? "Mark as paid" : `Mark ${confirmRows.length} as paid`}
        busy={marking}
        onCancel={() => setConfirmIds(null)}
        onConfirm={markPaid}
        message={
          <div className="flex flex-col gap-3">
            <p>
              {confirmRows.length === 1 ? (
                <>
                  <strong className="text-foreground">{confirmRows[0]?.employee_name}</strong>'s salary for <strong className="text-foreground">{period}</strong> will be marked as paid
                </>
              ) : (
                <>
                  <strong className="text-foreground">{plural(confirmRows.length, "salary", "salaries")}</strong> for <strong className="text-foreground">{period}</strong> will be marked as paid
                </>
              )}
              , totalling <strong className="text-foreground tabular-nums">{formatINR(confirmNet, true)}</strong> net.
            </p>
            {confirmRows.length > 1 && confirmRows.length <= 6 && (
              <ul className="flex flex-col gap-1 rounded-lg border border-border bg-surface-muted px-3 py-2 text-xs">
                {confirmRows.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3">
                    <span className="truncate text-foreground">{r.employee_name}</span>
                    <span className="tabular-nums">{formatINR(r.net_salary)}</span>
                  </li>
                ))}
              </ul>
            )}
            <Notice tone="warning" icon={<Lock />}>
              This can't be undone. Paid rows are locked: payroll re-generation skips them and attendance for {period} can no longer be corrected.
            </Notice>
            {isCurrent && <Notice tone="info">{period} isn't over yet — you would be locking provisional figures.</Notice>}
          </div>
        }
      />

      <GeneratePayrollModal
        open={generateOpen}
        month={month}
        year={year}
        onClose={() => setGenerateOpen(false)}
        onGenerated={() => {
          setSel({ month, year });
          list.reload();
          summary.reload();
        }}
      />
    </>
  );
}
