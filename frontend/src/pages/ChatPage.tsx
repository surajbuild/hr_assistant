/**
 * AI Assistant chat. POST /chat {message} → {answer, intent, source, confidence, page, sources[]}.
 * Previous conversation from GET /chat/history (displayed oldest first).
 */
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { AlertCircle, Bot, Database, FileText, Lightbulb, SendHorizonal, ShieldCheck, Sparkles, User } from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { Spinner } from "@/components/States";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { displayName, useAuth } from "@/lib/auth";
import { formatDateTime, humanize } from "@/lib/format";
import type { ChatHistoryItem, ChatResponse, ChatSource, Role } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp?: string;
  intent?: string | null;
  source?: string | null;
  confidence?: number | string | null;
  page?: number | null;
  sources?: ChatSource[];
  error?: boolean;
}

const PROMPTS: Record<Role, string[]> = {
  employee: [
    "What is my attendance this month?",
    "What is my leave balance?",
    "How many days was I late this month?",
    "What is my latest salary?",
    "What is the leave policy?",
    "How is overtime calculated?",
  ],
  manager: [
    "What is my team's attendance today?",
    "Who in my team was late this month?",
    "What is my leave balance?",
    "What is my attendance this month?",
    "What is the leave policy?",
    "Who in my team worked the most overtime?",
  ],
  hr: [
    "Who worked the most overtime this month?",
    "How many days was Aman present in August?",
    "Show employees who were late more than 5 times",
    "Who is on leave today?",
    "What is the leave policy?",
    "What is the total salary paid in September 2024?",
  ],
  admin: [
    "Who worked the most overtime this month?",
    "How many days was Aman present in August?",
    "Show employees who were late more than 5 times",
    "How many employees are in each department?",
    "What is the leave policy?",
    "What is the total salary paid in September 2024?",
  ],
};

const INTENT_STYLES: Record<string, string> = {
  ATTENDANCE: "bg-emerald-50 text-emerald-700",
  SALARY: "bg-amber-50 text-amber-700",
  LEAVE: "bg-violet-50 text-violet-700",
  EMPLOYEE: "bg-blue-50 text-blue-700",
  OVERTIME: "bg-blue-50 text-blue-700",
  POLICY: "bg-orange-50 text-orange-700",
  GENERAL: "bg-slate-100 text-slate-600",
  UNKNOWN: "bg-slate-100 text-slate-500",
  DENIED: "bg-red-50 text-red-700",
};

function sourceChips(m: Message): string[] {
  if (m.sources && m.sources.length > 0) {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const s of m.sources) {
      const label = s.page ? `${s.document} p.${s.page}` : s.document;
      if (!seen.has(label)) {
        seen.add(label);
        out.push(label);
      }
    }
    return out;
  }
  if (m.source) return [m.page ? `${m.source} p.${m.page}` : m.source];
  return [];
}

function formatConfidence(c: number | string | null | undefined): string | null {
  if (c === null || c === undefined || c === "") return null;
  if (typeof c === "number") return c <= 1 ? `${Math.round(c * 100)}%` : `${Math.round(c)}%`;
  const n = Number(c);
  if (!Number.isNaN(n)) return n <= 1 ? `${Math.round(n * 100)}%` : `${Math.round(n)}%`;
  return humanize(c);
}

function isDocSource(label: string) {
  return /\.(pdf|docx?|txt)\b/i.test(label) || / p\.\d+$/.test(label);
}

export function ChatPage() {
  const { role, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const prompts = PROMPTS[role ?? "employee"];

  useEffect(() => {
    let cancelled = false;
    api
      .get<ChatHistoryItem[]>("/chat/history")
      .then((items) => {
        if (cancelled) return;
        const sorted = [...(items ?? [])].sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? ""));
        const msgs: Message[] = [];
        for (const h of sorted) {
          msgs.push({ id: `h${h.id}q`, role: "user", text: h.question, timestamp: h.timestamp });
          msgs.push({
            id: `h${h.id}a`,
            role: "assistant",
            text: h.response,
            timestamp: h.timestamp,
            intent: h.detected_intent,
            source: h.data_source,
          });
        }
        setMessages(msgs);
      })
      .catch((err: unknown) => {
        if (!cancelled) setHistoryError(errorMessage(err, "Could not load previous conversation."));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  // auto-grow textarea
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  async function send(text?: string) {
    const q = (text ?? input).trim();
    if (!q || sending) return;
    setInput("");
    const now = new Date().toISOString();
    setMessages((prev) => [...prev, { id: `u${Date.now()}`, role: "user", text: q, timestamp: now }]);
    setSending(true);
    try {
      const res = await api.post<ChatResponse>("/chat", { message: q });
      setMessages((prev) => [
        ...prev,
        {
          id: `a${Date.now()}`,
          role: "assistant",
          text: res.answer || "No response received.",
          timestamp: new Date().toISOString(),
          intent: res.intent,
          source: res.source,
          confidence: res.confidence,
          page: res.page,
          sources: res.sources,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `e${Date.now()}`, role: "assistant", text: errorMessage(err, "Something went wrong. Please try again."), error: true },
      ]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send();
    }
  }

  const empty = !historyLoading && messages.length === 0;

  return (
    <div className="flex h-[calc(100dvh-52px-40px)] min-h-[480px] flex-1 gap-5 sm:h-[calc(100dvh-52px-48px)]">
      {/* Chat card */}
      <section className="hr-card flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-navy text-white">
              <Bot className="size-5" />
            </span>
            <div>
              <h1 className="text-[15px] font-semibold text-ink">AI HR Assistant</h1>
              <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                <span className="size-1.5 rounded-full bg-success" /> Answers from your HR data and policy documents
              </p>
            </div>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto bg-slate-50/60 px-3 py-4 sm:px-5" aria-live="polite">
          {historyLoading ? (
            <div className="flex h-full items-center justify-center text-sm text-ink-muted">
              <Spinner className="mr-2 text-brand" /> Loading conversation...
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {historyError && (
                <p className="rounded-md bg-warning-light px-3 py-2 text-xs text-amber-800">{historyError}</p>
              )}
              {empty && (
                <div className="flex flex-col items-center px-2 py-8 text-center">
                  <span className="flex size-14 items-center justify-center rounded-2xl bg-brand-light text-brand">
                    <Sparkles className="size-7" />
                  </span>
                  <h2 className="mt-4 text-lg font-semibold text-ink">Hi {displayName(user).split(" ")[0]}, how can I help?</h2>
                  <p className="mt-1 max-w-md text-sm text-ink-muted">
                    Ask about attendance, leave, salary, overtime or company policies. I only show data you are allowed to see.
                  </p>
                  <div className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
                    {prompts.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => void send(p)}
                        className="rounded-lg border border-border bg-white px-3 py-2.5 text-left text-sm text-ink transition-colors hover:border-brand/50 hover:bg-brand-light focus-visible:outline-2 focus-visible:outline-brand"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m) => (
                <MessageBubble key={m.id} m={m} userName={displayName(user)} />
              ))}

              {sending && (
                <div className="flex items-end gap-2.5">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-navy text-white">
                    <Bot className="size-4" />
                  </span>
                  <div className="flex gap-1.5 rounded-2xl rounded-bl-sm border border-border bg-white px-4 py-3" aria-label="Assistant is typing">
                    <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-border bg-white px-3 py-3 sm:px-5">
          {!empty && (
            <div className="scrollbar-none relative mx-auto mb-2 flex max-w-3xl gap-2 overflow-x-auto">
              {prompts.slice(0, 4).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void send(p)}
                  disabled={sending}
                  className="shrink-0 rounded-full border border-border bg-white px-3 py-1 text-xs text-ink-muted hover:border-brand/50 hover:text-brand disabled:opacity-50"
                >
                  {p}
                </button>
              ))}
            </div>
          )}
          <form
            className="mx-auto flex max-w-3xl items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <label htmlFor="chat-input" className="sr-only">
              Ask a question
            </label>
            <textarea
              id="chat-input"
              ref={inputRef}
              rows={1}
              maxLength={1000}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask an HR question… (Enter to send, Shift+Enter for a new line)"
              className="max-h-40 min-h-10 flex-1 resize-none rounded-lg border border-input bg-white px-3 py-2.5 text-sm outline-none placeholder:text-ink-muted focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
            <Button type="submit" size="icon-lg" disabled={sending || !input.trim()} aria-label="Send message">
              {sending ? <Spinner /> : <SendHorizonal className="size-4" />}
            </Button>
          </form>
        </div>
      </section>

      {/* Side panel */}
      <aside className="hidden w-72 shrink-0 flex-col gap-4 overflow-y-auto xl:flex">
        <div className="hr-card p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Lightbulb className="size-4 text-warning" /> Try asking
          </h2>
          <ul className="mt-3 flex flex-col gap-1.5">
            {prompts.map((p) => (
              <li key={p}>
                <button
                  type="button"
                  onClick={() => void send(p)}
                  disabled={sending}
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm text-ink-muted hover:bg-brand-light hover:text-brand disabled:opacity-50"
                >
                  {p}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="hr-card p-4 text-sm text-ink-muted">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ShieldCheck className="size-4 text-success" /> How it works
          </h2>
          <ul className="mt-3 space-y-2">
            <li className="flex gap-2">
              <Database className="mt-0.5 size-4 shrink-0 text-brand" /> Numbers come from the HR database, calculated by the system.
            </li>
            <li className="flex gap-2">
              <FileText className="mt-0.5 size-4 shrink-0 text-brand" /> Policy answers cite uploaded documents and pages.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand" /> Your role decides what data can be shown.
            </li>
          </ul>
        </div>
      </aside>
    </div>
  );
}

function MessageBubble({ m, userName }: { m: Message; userName: string }) {
  if (m.role === "user") {
    return (
      <div className="flex items-end justify-end gap-2.5">
        <div className="max-w-[85%] sm:max-w-[75%]">
          <div className="whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-brand px-4 py-2.5 text-sm text-white">{m.text}</div>
          {m.timestamp && <p className="mt-1 text-right text-[11px] text-ink-muted">{formatDateTime(m.timestamp)}</p>}
        </div>
        <span className="hidden size-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600 sm:flex" title={userName}>
          <User className="size-4" />
        </span>
      </div>
    );
  }

  const chips = sourceChips(m);
  const confidence = formatConfidence(m.confidence);
  const intent = m.intent?.toUpperCase();

  return (
    <div className="flex items-end gap-2.5">
      <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full text-white", m.error ? "bg-danger" : "bg-navy")}>
        {m.error ? <AlertCircle className="size-4" /> : <Bot className="size-4" />}
      </span>
      <div className="min-w-0 max-w-[85%] sm:max-w-[75%]">
        <div
          className={cn(
            "rounded-2xl rounded-bl-sm border px-4 py-2.5 text-sm leading-relaxed",
            m.error ? "border-red-200 bg-danger-light text-red-800" : "border-border bg-white text-ink",
          )}
        >
          <Markdown text={m.text} />
        </div>
        {(intent || chips.length > 0 || confidence || m.timestamp) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
            {intent && (
              <span className={cn("rounded-full px-2 py-0.5 font-semibold", INTENT_STYLES[intent] ?? "bg-slate-100 text-slate-600")}>{intent}</span>
            )}
            {chips.map((c) => (
              <span key={c} className="inline-flex items-center gap-1 rounded-full border border-border bg-white px-2 py-0.5 text-ink-muted">
                {isDocSource(c) ? <FileText className="size-3" /> : <Database className="size-3" />}
                {c}
              </span>
            ))}
            {confidence && <span className="text-ink-muted">Confidence: {confidence}</span>}
            {m.timestamp && <span className="text-ink-muted">· {formatDateTime(m.timestamp)}</span>}
          </div>
        )}
      </div>
    </div>
  );
}
