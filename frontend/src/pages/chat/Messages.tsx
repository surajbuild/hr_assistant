/**
 * AI Assistant — message bubbles, assistant mark, typing indicator, day dividers.
 * Pure presentational components (state lives in ChatPage).
 */
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Copy, Database, FileText, Hourglass, Info, RefreshCw, Sparkles } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Markdown } from "@/components/Markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/tooltip";
import { formatDate, formatTime, parseDate } from "@/lib/format";
import type { ChatSource } from "@/lib/types";
import { cn } from "@/lib/utils";
import { confidenceInfo, intentLabel, sourceChips } from "./meta";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp?: string;
  intent?: string | null;
  source?: string | null;
  confidence?: number | string | null;
  sources?: ChatSource[];
  /** Error bubble (request failed). `question` is what to resend on retry. */
  error?: "rate_limit" | "failed";
  question?: string;
  /** Epoch ms when a rate-limited question may be sent again. */
  retryAt?: number;
}

/** The assistant's avatar: brand-tinted circle with a sparkle (decorative). */
export function AssistantMark({ className, tone = "brand" }: { className?: string; tone?: "brand" | "danger" | "warning" }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-full [&_svg]:size-4",
        tone === "brand" && "bg-brand-subtle text-brand-subtle-foreground",
        tone === "danger" && "bg-status-absent-bg text-status-absent-fg",
        tone === "warning" && "bg-status-late-bg text-status-late-fg",
        className,
      )}
    >
      {tone === "danger" ? <AlertTriangle /> : tone === "warning" ? <Hourglass /> : <Sparkles />}
    </span>
  );
}

/** Local calendar day key for grouping ("2026-10-05"). */
export function dayKey(ts: string | undefined): string {
  const d = parseDate(ts);
  if (!d) return "";
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(ts: string): string {
  const d = parseDate(ts);
  if (!d) return "";
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Today";
  if (same(d, yesterday)) return "Yesterday";
  return formatDate(ts);
}

export function DayDivider({ timestamp }: { timestamp: string }) {
  return (
    <div className="flex items-center gap-3 py-1" role="separator" aria-label={dayLabel(timestamp)}>
      <span className="h-px flex-1 bg-border" />
      <span className="text-[11px] font-medium text-muted-foreground">{dayLabel(timestamp)}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex items-end gap-2.5" role="status">
      <AssistantMark />
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3.5">
        <span className="sr-only">The assistant is preparing an answer</span>
        {[0, 160, 320].map((delay) => (
          <span
            key={delay}
            aria-hidden="true"
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard unavailable (insecure context) — leave the button as is */
    }
  }

  return (
    <Hint label={copied ? "Copied" : "Copy answer"}>
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={copied ? "Answer copied" : "Copy answer"}
        className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        {copied ? <Check className="size-3.5 text-status-present-fg" /> : <Copy className="size-3.5" />}
      </button>
    </Hint>
  );
}

function UserBubble({ m, userName, userSeed }: { m: ChatMessage; userName: string; userSeed?: number }) {
  return (
    <div className="flex items-end justify-end gap-2.5">
      <div className="flex max-w-[85%] min-w-0 flex-col items-end sm:max-w-[75%]">
        <div className="rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap text-brand-foreground [overflow-wrap:anywhere]">
          {m.text}
        </div>
        {m.timestamp && <time className="mt-1 text-[11px] text-muted-foreground tabular-nums" dateTime={m.timestamp}>{formatTime(m.timestamp)}</time>}
      </div>
      <Avatar name={userName} seed={userSeed} size="sm" className="mb-5 hidden sm:inline-flex" />
    </div>
  );
}

function ErrorBubble({ m, now, onRetry, busy }: { m: ChatMessage; now: number; onRetry: (m: ChatMessage) => void; busy: boolean }) {
  const limited = m.error === "rate_limit";
  const wait = limited && m.retryAt ? Math.max(0, Math.ceil((m.retryAt - now) / 1000)) : 0;
  return (
    <div className="flex items-end gap-2.5">
      <AssistantMark tone={limited ? "warning" : "danger"} className="mb-1" />
      <div
        role="alert"
        className={cn(
          "max-w-[85%] min-w-0 rounded-2xl rounded-bl-md border px-4 py-3 text-sm sm:max-w-[75%]",
          limited ? "border-status-late/30 bg-status-late-bg text-status-late-fg" : "border-status-absent/30 bg-status-absent-bg text-status-absent-fg",
        )}
      >
        {limited ? (
          <>
            <p className="font-medium">You're sending messages a little fast.</p>
            <p className="mt-0.5">
              {wait > 0 ? (
                <>
                  To keep the assistant responsive there is a short limit per person. You can ask again in{" "}
                  <strong className="tabular-nums">{wait}s</strong>.
                </>
              ) : (
                "You can ask again now."
              )}
            </p>
          </>
        ) : (
          <>
            <p className="font-medium">The answer could not be loaded.</p>
            <p className="mt-0.5 [overflow-wrap:anywhere]">{m.text}</p>
          </>
        )}
        {m.question && (
          <Button variant="outline" size="sm" className="mt-2.5" disabled={busy || wait > 0} onClick={() => onRetry(m)}>
            <RefreshCw /> {wait > 0 ? `Retry in ${wait}s` : "Retry"}
          </Button>
        )}
      </div>
    </div>
  );
}

/** A Markdown pipe table (header row followed by a |---| separator) — such answers get the full width. */
const TABLE_RX = /^.*\|.*\n\s*\|?\s*:?-{2,}/m;

function AssistantBubble({ m }: { m: ChatMessage }) {
  const chips = sourceChips(m.sources, m.source);
  const conf = confidenceInfo(m.confidence);
  const intent = intentLabel(m.intent);
  const wide = TABLE_RX.test(m.text);
  return (
    <div className="flex items-end gap-2.5">
      <AssistantMark className="mb-6" />
      <div className={cn("flex min-w-0 flex-col", wide ? "flex-1" : "max-w-[85%] sm:max-w-[75%]")}>
        <div className="rounded-2xl rounded-bl-md border border-border bg-surface px-4 py-3 text-sm leading-relaxed text-foreground">
          <Markdown text={m.text} />
          {(chips.length > 0 || conf) && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border pt-2.5">
              {conf && (
                <Hint label={conf.description}>
                  <button type="button" className="rounded-full focus-visible:outline-2" aria-label={`${conf.label}: ${conf.description}`}>
                    <Badge tone={conf.tone}>
                      <Info className="size-3" aria-hidden="true" />
                      {conf.label}
                    </Badge>
                  </button>
                </Hint>
              )}
              {chips.map((c) => (
                <span
                  key={c.key}
                  className="inline-flex max-w-full items-center gap-1 rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs text-muted-foreground"
                  title={c.label}
                >
                  {c.kind === "document" ? <FileText className="size-3 shrink-0" aria-hidden="true" /> : <Database className="size-3 shrink-0" aria-hidden="true" />}
                  <span className="sr-only">{c.kind === "document" ? "Source document:" : "Source:"}</span>
                  <span className="truncate">{c.label}</span>
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
          {m.timestamp && (
            <time className="tabular-nums" dateTime={m.timestamp}>
              {formatTime(m.timestamp)}
            </time>
          )}
          {intent && (
            <>
              <span aria-hidden="true">·</span>
              <span>
                <span className="sr-only">Topic: </span>
                {intent}
              </span>
            </>
          )}
          <span className="-my-1.5 ml-auto">
            <CopyButton text={m.text} />
          </span>
        </div>
      </div>
    </div>
  );
}

export function MessageBubble({
  m,
  userName,
  userSeed,
  now,
  onRetry,
  busy,
}: {
  m: ChatMessage;
  userName: string;
  userSeed?: number;
  now: number;
  onRetry: (m: ChatMessage) => void;
  busy: boolean;
}) {
  if (m.role === "user") return <UserBubble m={m} userName={userName} userSeed={userSeed} />;
  if (m.error) return <ErrorBubble m={m} now={now} onRetry={onRetry} busy={busy} />;
  return <AssistantBubble m={m} />;
}

/** Skeleton conversation while the history loads. */
export function HistorySkeleton() {
  const rows: { mine: boolean; w: string }[] = [
    { mine: true, w: "w-48" },
    { mine: false, w: "w-72" },
    { mine: true, w: "w-40" },
    { mine: false, w: "w-80" },
  ];
  return (
    <div role="status" className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <span className="sr-only">Loading your conversation</span>
      {rows.map((r, i) => (
        <div key={i} className={cn("flex items-end gap-2.5", r.mine && "justify-end")}>
          {!r.mine && <span className="skeleton size-8 shrink-0 rounded-full" />}
          <span className={cn("skeleton h-12 max-w-[75%] rounded-2xl", r.w, !r.mine && "h-20")} />
        </div>
      ))}
    </div>
  );
}
