/**
 * Settings → AI Chat Audit Log (admin). Server-paginated (D-035):
 * GET /chat/logs?limit=&offset=&search= → rows + X-Total-Count (search matches the question or the user's email).
 * Rows expand to show the full question, the answer (markdown) and the error code. No client-side intent/result
 * filters: with server paging they would only filter the visible page and look like a complete result.
 */
import { Fragment, useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, ChevronRight, RefreshCw, ScrollText } from "lucide-react";
import { Pagination } from "@/components/DataTable";
import { SearchInput } from "@/components/Field";
import { Markdown } from "@/components/Markdown";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, errorMessage, qs } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { ChatLog } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

type Outcome = { label: string; tone: "present" | "late" | "absent" };

/** chat_logs.error codes written by POST /chat (app/api/chat.py). */
function outcome(l: ChatLog): Outcome {
  if (!l.error) return { label: "Answered", tone: "present" };
  if (l.error === "PROMPT_INJECTION_BLOCKED") return { label: "Blocked", tone: "late" };
  if (l.error === "RBAC_ACCESS_DENIED") return { label: "Access denied", tone: "late" };
  return { label: "Error", tone: "absent" };
}

function errorExplanation(code: string): string {
  if (code === "PROMPT_INJECTION_BLOCKED") return "Prompt-injection guardrail refused the question before any data was read.";
  if (code === "RBAC_ACCESS_DENIED") return "The user's role may not see this data; nothing was retrieved and the AI was not called.";
  return code;
}

function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function intentText(i: string | null | undefined): string {
  if (!i) return "—";
  return i.charAt(0) + i.slice(1).toLowerCase();
}

function latency(ms: number | null | undefined): string {
  return ms === null || ms === undefined ? "—" : `${formatNumber(ms)} ms`;
}

export function AuditLogTab() {
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search.trim());
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState<ChatLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const req = useRef(0);

  useEffect(() => setPage(0), [debounced]);

  useEffect(() => {
    const id = ++req.current;
    setLoading(true);
    setError(null);
    api
      .getPage<ChatLog>(`/chat/logs${qs({ limit: PAGE_SIZE, offset: page * PAGE_SIZE, search: debounced })}`)
      .then((res) => {
        if (id !== req.current) return;
        setRows(res.items ?? []);
        setTotal(res.total);
        setExpanded(null);
      })
      .catch((err: unknown) => {
        if (id === req.current) setError(errorMessage(err, "Could not load the audit log."));
      })
      .finally(() => {
        if (id === req.current) setLoading(false);
      });
  }, [debounced, page, tick]);

  const reload = () => setTick((t) => t + 1);
  const toggle = (id: number) => setExpanded((e) => (e === id ? null : id));

  let body;
  if (loading && rows.length === 0) body = <LoadingState label="Loading audit log..." rows={6} />;
  else if (error) body = <ErrorState message={error} onRetry={reload} />;
  else if (rows.length === 0)
    body = debounced ? (
      <EmptyState
        icon={<ScrollText />}
        title="No interactions match your search"
        description="Search looks at the question text and the user's email."
        action={
          <Button variant="outline" size="sm" onClick={() => setSearch("")}>
            Clear search
          </Button>
        }
      />
    ) : (
      <EmptyState
        icon={<Bot />}
        title="No chat interactions yet"
        description="Every question asked to the AI assistant is logged here with its intent, source and latency."
        action={
          <Button size="sm" onClick={() => navigate("/assistant")}>
            <Bot /> Open AI Assistant
          </Button>
        }
      />
    );
  else
    body = (
      <div className={cn("transition-opacity", loading && "opacity-60")} aria-busy={loading}>
        {/* ≥768px: table with expandable rows */}
        <div className="relative hidden w-full overflow-x-auto md:block">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-border bg-surface-muted text-left text-xs font-medium text-muted-foreground">
                <th scope="col" className="w-10 py-2.5 pl-4">
                  <span className="sr-only">Details</span>
                </th>
                <th scope="col" className="px-3 py-2.5 whitespace-nowrap">Time</th>
                <th scope="col" className="px-3 py-2.5">User</th>
                <th scope="col" className="px-3 py-2.5">Question</th>
                <th scope="col" className="px-3 py-2.5">Intent</th>
                <th scope="col" className="hidden px-3 py-2.5 xl:table-cell">Source</th>
                <th scope="col" className="px-3 py-2.5 text-right">Latency</th>
                <th scope="col" className="py-2.5 pr-5 pl-3">Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l) => {
                const open = expanded === l.id;
                const o = outcome(l);
                return (
                  <Fragment key={l.id}>
                    <tr
                      className={cn("cursor-pointer border-b border-border transition-colors hover:bg-accent/60", open && "bg-accent/60")}
                      onClick={() => toggle(l.id)}
                    >
                      <td className="py-2.5 pl-4">
                        <button
                          type="button"
                          aria-expanded={open}
                          aria-controls={`log-${l.id}`}
                          aria-label={`${open ? "Hide" : "Show"} details for "${l.question.slice(0, 60)}"`}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggle(l.id);
                          }}
                          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                        >
                          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 whitespace-nowrap text-muted-foreground tabular-nums">{formatDateTime(l.timestamp)}</td>
                      <td className="px-3 py-2.5 text-foreground">
                        <div className="max-w-[13rem] truncate">{l.user_email ?? (l.user_id ? `User #${l.user_id}` : "—")}</div>
                      </td>
                      {/* takes the remaining width and truncates (max-w-0 trick for auto-layout tables) */}
                      <td className="w-full max-w-0 px-3 py-2.5 text-foreground" title={l.question}>
                        <div className="min-w-40 truncate">{l.question}</div>
                      </td>
                      <td className="px-3 py-2.5">{l.detected_intent ? <Badge tone="neutral">{intentText(l.detected_intent)}</Badge> : "—"}</td>
                      <td className="hidden px-3 py-2.5 text-muted-foreground xl:table-cell" title={l.data_source ?? undefined}>
                        <div className="max-w-[10rem] truncate">{l.data_source ?? "—"}</div>
                      </td>
                      <td className="px-3 py-2.5 text-right whitespace-nowrap text-muted-foreground tabular-nums">{latency(l.response_time_ms)}</td>
                      <td className="py-2.5 pr-5 pl-3">
                        <Badge tone={o.tone}>{o.label}</Badge>
                      </td>
                    </tr>
                    {open && (
                      <tr className="border-b border-border bg-accent/30">
                        <td />
                        <td colSpan={7} id={`log-${l.id}`} className="px-3 pt-2 pb-5">
                          <LogDetails l={l} compact />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* <768px: expandable cards */}
        <ul className="divide-y divide-border md:hidden">
          {rows.map((l) => {
            const open = expanded === l.id;
            const o = outcome(l);
            return (
              <li key={l.id}>
                <button
                  type="button"
                  aria-expanded={open}
                  aria-controls={`log-m-${l.id}`}
                  onClick={() => toggle(l.id)}
                  className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/60"
                >
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-sm font-medium text-foreground">{l.question}</span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">
                      {l.user_email ?? "—"} · <span className="tabular-nums">{formatDateTime(l.timestamp)}</span>
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5">
                    <Badge tone={o.tone}>{o.label}</Badge>
                    {open ? <ChevronDown className="size-4 text-muted-foreground" aria-hidden="true" /> : <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />}
                  </span>
                </button>
                {open && (
                  <div id={`log-m-${l.id}`} className="bg-accent/30 px-4 pt-1 pb-4">
                    <LogDetails l={l} compact />
                  </div>
                )}
              </li>
            );
          })}
        </ul>

        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
      </div>
    );

  return (
    <section className="rounded-xl border border-border bg-surface" aria-labelledby="audit-title">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-1">
        <div className="flex min-w-0 items-center gap-2.5">
          <ScrollText className="size-4 text-muted-foreground" aria-hidden="true" />
          <div className="min-w-0">
            <h2 id="audit-title" className="text-base font-semibold text-foreground">
              AI chat audit log
            </h2>
            <p className="text-xs font-medium text-muted-foreground">
              Every question is logged with its intent, source, latency and outcome
              {!error && total > 0 && (
                <>
                  {" "}
                  · <span className="tabular-nums">{formatNumber(total)}</span> {debounced ? "matching" : "in total"}
                </>
              )}
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={reload} disabled={loading}>
          <RefreshCw className={cn(loading && "animate-spin")} /> Refresh
        </Button>
      </header>
      <div className="border-b border-border p-4">
        <SearchInput value={search} onChange={setSearch} placeholder="Search question or user email..." className="md:w-80" />
      </div>
      {body}
    </section>
  );
}

function LogDetails({ l, compact }: { l: ChatLog; compact?: boolean }) {
  return (
    <div className="flex max-w-4xl flex-col gap-3">
      {compact && (
        <dl className="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted-foreground">Intent</dt>
          <dd className="text-foreground">{intentText(l.detected_intent)}</dd>
          <dt className="text-muted-foreground">Source</dt>
          <dd className="truncate text-foreground">{l.data_source ?? "—"}</dd>
          <dt className="text-muted-foreground">Latency</dt>
          <dd className="text-foreground tabular-nums">{latency(l.response_time_ms)}</dd>
        </dl>
      )}
      <div>
        <p className="text-xs font-medium text-muted-foreground">Question</p>
        <p className="mt-1 text-sm whitespace-pre-wrap text-foreground [overflow-wrap:anywhere]">{l.question}</p>
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">Answer</p>
        {l.response ? (
          <div className="mt-1 rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-foreground">
            <Markdown text={l.response} />
          </div>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">No answer recorded.</p>
        )}
      </div>
      {l.error && (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Error / guardrail</p>
          {errorExplanation(l.error) !== l.error ? (
            <p className="mt-1 text-sm text-foreground">
              <code className="rounded bg-surface-muted px-1 py-px font-mono text-xs">{l.error}</code> {errorExplanation(l.error)}
            </p>
          ) : (
            <p className="mt-1 text-sm whitespace-pre-wrap text-status-absent-fg [overflow-wrap:anywhere]">{l.error}</p>
          )}
        </div>
      )}
    </div>
  );
}
