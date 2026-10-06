/**
 * AI Assistant (full height inside the shell). POST /chat {message} → {answer, intent, source, confidence, page, sources[]}.
 * The caller's previous conversation comes from GET /chat/history (own messages, oldest first). There are no
 * threads/sessions in the backend, so there is one continuous conversation (no conversation list).
 * POST /chat may answer 429 (per-user limit, D-031) → friendly bubble with a countdown; other failures → error bubble
 * with retry. Answers show a confidence label, the cited documents/pages or the HR data source, and a copy button.
 */
import { Fragment, useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowDown, FileText, Lightbulb, RefreshCw, SendHorizonal, ShieldCheck } from "lucide-react";
import { Notice } from "@/components/States";
import { RoleBadge } from "@/components/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "@/lib/router";
import { ApiError, api, errorMessage } from "@/lib/api";
import { displayName, useAuth } from "@/lib/auth";
import type { ChatHistoryItem, ChatResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AssistantMark, DayDivider, HistorySkeleton, MessageBubble, TypingIndicator, dayKey, type ChatMessage } from "./chat/Messages";
import { ACCESS_SCOPE, CONFIDENCE, CONFIDENCE_ORDER, PROMPTS, retryAfterSeconds } from "./chat/meta";

const MAX_LENGTH = 1000;
const HISTORY_LIMIT = 50;

function historyToMessages(items: ChatHistoryItem[]): ChatMessage[] {
  const sorted = [...items].sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? "") || a.id - b.id);
  const out: ChatMessage[] = [];
  for (const h of sorted) {
    out.push({ id: `h${h.id}q`, role: "user", text: h.question, timestamp: h.timestamp });
    out.push({
      id: `h${h.id}a`,
      role: "assistant",
      text: h.response || "No answer was recorded.",
      timestamp: h.timestamp,
      intent: h.detected_intent,
      source: h.data_source,
    });
  }
  return out;
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

let seq = 0;
const uid = (p: string) => `${p}${Date.now()}-${seq++}`;

export function ChatPage() {
  const { role, user } = useAuth();
  const r = role ?? "employee";
  const prompts = PROMPTS[r];
  const name = displayName(user);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyTick, setHistoryTick] = useState(0);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [atBottom, setAtBottom] = useState(true);
  const [announce, setAnnounce] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── history ────────────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    api
      .get<ChatHistoryItem[]>(`/chat/history?limit=${HISTORY_LIMIT}`)
      .then((items) => {
        if (cancelled) return;
        // keep anything typed in this session (e.g. while a retry of the history was loading)
        setMessages((prev) => [...historyToMessages(items ?? []), ...prev.filter((m) => !m.id.startsWith("h"))]);
      })
      .catch((err: unknown) => {
        if (!cancelled) setHistoryError(errorMessage(err, "Could not load your previous conversation."));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [historyTick]);

  // ── rate-limit countdown (ticks only while a cooldown is active) ────────────
  const coolingDown = cooldownUntil > now;
  useEffect(() => {
    if (cooldownUntil <= Date.now()) return;
    const t = setInterval(() => {
      const n = Date.now();
      setNow(n);
      if (n >= cooldownUntil) clearInterval(t);
    }, 1000);
    return () => clearInterval(t);
  }, [cooldownUntil]);

  // ── scrolling ──────────────────────────────────────────────────────────────
  const scrollToBottom = useCallback((smooth = true) => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth && !prefersReducedMotion() ? "smooth" : "auto" });
  }, []);

  useEffect(() => {
    scrollToBottom(!historyLoading);
  }, [messages, sending, historyLoading, scrollToBottom]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 120);
  }

  // auto-grow textarea
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  // ── sending ────────────────────────────────────────────────────────────────
  async function ask(question: string, opts: { appendUser: boolean }) {
    if (sending) return;
    if (opts.appendUser) {
      setMessages((prev) => [...prev, { id: uid("u"), role: "user", text: question, timestamp: new Date().toISOString() }]);
    }
    setSending(true);
    setAnnounce("");
    try {
      const res = await api.post<ChatResponse>("/chat", { message: question });
      setMessages((prev) => [
        ...prev,
        {
          id: uid("a"),
          role: "assistant",
          text: res?.answer || "No response received.",
          timestamp: new Date().toISOString(),
          intent: res?.intent,
          source: res?.source,
          confidence: res?.confidence,
          sources: res?.sources,
        },
      ]);
      setAnnounce("The assistant answered.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        const until = Date.now() + retryAfterSeconds(err.message) * 1000;
        setCooldownUntil(until);
        setNow(Date.now());
        setMessages((prev) => [...prev, { id: uid("e"), role: "assistant", text: err.message, error: "rate_limit", question, retryAt: until }]);
      } else {
        setMessages((prev) => [
          ...prev,
          { id: uid("e"), role: "assistant", text: errorMessage(err, "Something went wrong. Please try again."), error: "failed", question },
        ]);
      }
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || sending || coolingDown) return;
    if (text === undefined) setInput("");
    void ask(q.slice(0, MAX_LENGTH), { appendUser: true });
  }

  function retry(m: ChatMessage) {
    if (!m.question || sending || coolingDown) return;
    setMessages((prev) => prev.filter((x) => x.id !== m.id));
    void ask(m.question, { appendUser: false });
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  }

  const empty = !historyLoading && messages.length === 0;
  const waitSeconds = coolingDown ? Math.ceil((cooldownUntil - now) / 1000) : 0;
  const blocked = sending || coolingDown;

  return (
    <div className="flex h-[calc(100dvh-56px-40px)] min-h-[420px] gap-5 sm:h-[calc(100dvh-56px-48px)]">
      {/* ── Conversation ─────────────────────────────────────────────────── */}
      <section aria-labelledby="chat-title" className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3 sm:px-5">
          <AssistantMark className="size-9 rounded-lg [&_svg]:size-5" />
          <div className="min-w-0 flex-1">
            <h1 id="chat-title" className="text-base font-semibold text-foreground">
              AI HR Assistant
            </h1>
            <p className="truncate text-xs text-muted-foreground">Answers from HR records and policy documents, limited to what you may see</p>
          </div>
          <RoleBadge role={r} className="hidden sm:inline-flex" />
        </header>

        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollRef}
            onScroll={onScroll}
            role="log"
            aria-label="Conversation"
            aria-busy={historyLoading}
            className="h-full overflow-y-auto bg-background px-3 py-5 sm:px-5"
          >
            {historyLoading ? (
              <HistorySkeleton />
            ) : (
              <div className="mx-auto flex max-w-3xl flex-col gap-4">
                {historyError && (
                  <Notice tone="warning" className="items-center">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                      <span>{historyError} You can still ask new questions.</span>
                      <Button variant="outline" size="sm" onClick={() => setHistoryTick((t) => t + 1)}>
                        <RefreshCw /> Retry
                      </Button>
                    </div>
                  </Notice>
                )}

                {empty && <Welcome firstName={name.split(" ")[0] ?? ""} prompts={prompts} onPick={send} disabled={blocked} />}

                {messages.map((m, i) => {
                  const prev = messages[i - 1];
                  const showDay = !!m.timestamp && dayKey(m.timestamp) !== dayKey(prev?.timestamp) && m.role === "user";
                  return (
                    <Fragment key={m.id}>
                      {showDay && <DayDivider timestamp={m.timestamp!} />}
                      <MessageBubble m={m} userName={name} userSeed={user?.user_id} now={now} onRetry={retry} busy={blocked} />
                    </Fragment>
                  );
                })}

                {sending && <TypingIndicator />}
              </div>
            )}
          </div>
          {!atBottom && !historyLoading && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => scrollToBottom()}
              className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full shadow-float"
            >
              <ArrowDown /> Latest
            </Button>
          )}
        </div>

        <span className="sr-only" aria-live="polite">
          {announce}
        </span>

        {/* ── Composer ─────────────────────────────────────────────────────── */}
        <div className="border-t border-border bg-surface px-3 pt-3 pb-3 sm:px-5">
          {!empty && (
            <div className="scrollbar-none relative mx-auto mb-2.5 flex max-w-3xl gap-2 overflow-x-auto" role="group" aria-label="Suggested questions">
              {prompts.slice(0, 4).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => send(p)}
                  aria-disabled={blocked || undefined}
                  className="shrink-0 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-brand/50 hover:bg-brand-subtle hover:text-brand-subtle-foreground aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                >
                  {p}
                </button>
              ))}
            </div>
          )}
          <form
            className="mx-auto max-w-3xl"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <div className="flex items-end gap-2 rounded-xl border border-input bg-surface p-1.5 pl-3 transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/25">
              <label htmlFor="chat-input" className="sr-only">
                Ask an HR question
              </label>
              <textarea
                id="chat-input"
                ref={inputRef}
                rows={1}
                maxLength={MAX_LENGTH}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                aria-describedby="chat-hint"
                placeholder="Ask about attendance, leave, payroll or policies…"
                className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus-visible:outline-none"
              />
              <Button type="submit" size="icon" disabled={blocked || !input.trim()} loading={sending} aria-label="Send message">
                {!sending && <SendHorizonal />}
              </Button>
            </div>
            <p id="chat-hint" className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[11px] text-muted-foreground">
              {coolingDown ? (
                <span className="text-status-late-fg" aria-live="polite">
                  Message limit reached — you can send again in <span className="tabular-nums">{waitSeconds}s</span>.
                </span>
              ) : (
                <span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span>
              )}
              {input.length > MAX_LENGTH * 0.8 && (
                <span className={cn("ml-auto tabular-nums", input.length >= MAX_LENGTH && "text-status-absent-fg")}>
                  {input.length}/{MAX_LENGTH}
                </span>
              )}
            </p>
          </form>
        </div>
      </section>

      {/* ── Side panel (≥1280px) ─────────────────────────────────────────── */}
      <aside className="hidden w-72 shrink-0 flex-col gap-4 overflow-y-auto xl:flex" aria-label="Assistant help">
        <section className="rounded-xl border border-border bg-surface p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Lightbulb className="size-4 text-muted-foreground" aria-hidden="true" /> Try asking
          </h2>
          <ul className="mt-2.5 flex flex-col gap-0.5">
            {prompts.map((p) => (
              <li key={p}>
                <button
                  type="button"
                  onClick={() => send(p)}
                  aria-disabled={blocked || undefined}
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-brand-subtle hover:text-brand-subtle-foreground aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-border bg-surface p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" /> Your access
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">{ACCESS_SCOPE[r]}</p>
        </section>

        <section className="rounded-xl border border-border bg-surface p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <FileText className="size-4 text-muted-foreground" aria-hidden="true" /> Answer labels
          </h2>
          <dl className="mt-3 flex flex-col gap-2.5">
            {CONFIDENCE_ORDER.map((k) => (
              <div key={k}>
                <dt>
                  <Badge tone={CONFIDENCE[k].tone}>{CONFIDENCE[k].label}</Badge>
                </dt>
                <dd className="mt-1 text-xs text-muted-foreground">{CONFIDENCE[k].description}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">
            Labels are shown for answers in this session. Policy answers come from{" "}
            <Link to="/documents" className="font-medium text-brand underline-offset-4 hover:underline">
              uploaded documents
            </Link>
            .
          </p>
        </section>
      </aside>
    </div>
  );
}

function Welcome({ firstName, prompts, onPick, disabled }: { firstName: string; prompts: string[]; onPick: (p: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-col items-center px-2 py-6 text-center sm:py-10">
      <AssistantMark className="size-14 rounded-2xl [&_svg]:size-7" />
      <h2 className="mt-4 text-lg font-semibold text-foreground">{firstName ? `Hi ${firstName}, how can I help?` : "How can I help?"}</h2>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">
        Ask about attendance, leave, payroll or company policies. Numbers are calculated by the HR system, and you only see data your role allows.
      </p>
      <div className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2" role="group" aria-label="Suggested questions">
        {prompts.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPick(p)}
            aria-disabled={disabled || undefined}
            className="card-interactive rounded-lg border border-border bg-surface px-3 py-2.5 text-left text-sm text-foreground hover:bg-brand-subtle aria-disabled:cursor-not-allowed aria-disabled:opacity-50"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}
