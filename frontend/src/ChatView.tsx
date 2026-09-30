import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Message {
  id: number;
  sender: "user" | "ai";
  text: string;
  intent?: string;
}

interface ChatViewProps {
  token: string;
  onLogout?: () => void;
  showHeader?: boolean;
}

// ── JWT decode (no library — base64 decode the payload) ───────────────────────

function decodeTokenPayload(token: string): { sub?: string; role?: string } {
  try {
    const payload = token.split(".")[1];
    if (!payload) return {};
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as { sub?: string; role?: string };
  } catch {
    return {};
  }
}

// ── Intent badge colours ───────────────────────────────────────────────────────

const INTENT_COLOURS: Record<string, string> = {
  ATTENDANCE: "bg-blue-100 text-blue-700",
  SALARY: "bg-green-100 text-green-700",
  LEAVE: "bg-yellow-100 text-yellow-700",
  EMPLOYEE: "bg-purple-100 text-purple-700",
  POLICY: "bg-orange-100 text-orange-700",
  GENERAL: "bg-gray-100 text-gray-600",
  UNKNOWN: "bg-gray-100 text-gray-400",
};

function intentBadgeClass(intent: string) {
  return INTENT_COLOURS[intent.toUpperCase()] ?? "bg-gray-100 text-gray-500";
}

// ── Component ──────────────────────────────────────────────────────────────────

export function ChatView({ token, onLogout, showHeader = false }: ChatViewProps) {
  const { role } = decodeTokenPayload(token);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      sender: "ai",
      text: "Hello! I'm your AI HR Assistant. Ask me anything about attendance, leave, salary, or company policies.",
    },
  ]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    const q = question.trim();
    if (!q || loading) return;

    setError("");
    setQuestion("");

    const userMsg: Message = { id: Date.now(), sender: "user", text: q };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question: q }),
      });

      if (res.status === 401) {
        // Token expired — log out cleanly
        onLogout?.();
        return;
      }

      const data = (await res.json()) as {
        answer?: string;
        intent?: string;
        detail?: string;
      };

      if (!res.ok) {
        setError(data.detail ?? "Something went wrong. Please try again.");
        return;
      }

      const aiMsg: Message = {
        id: Date.now() + 1,
        sender: "ai",
        text: data.answer ?? "No response received.",
        intent: data.intent,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch {
      setError("Network error. Please check your connection.");
    } finally {
      setLoading(false);
      // Return focus to input after reply
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage();
    }
  }

  return (
    <div className="flex flex-col h-full max-w-3xl w-full mx-auto">
      {/* ── Optional Header ─────────────────────────────────────────────────── */}
      {showHeader && (
        <header className="flex items-center justify-between px-4 py-3 border-b bg-card shrink-0">
          <div className="flex flex-col">
            <span className="font-semibold text-sm">AI HR Assistant</span>
            {role && (
              <span className="text-xs text-muted-foreground capitalize">{role}</span>
            )}
          </div>
          {onLogout && (
            <Button variant="outline" size="sm" onClick={onLogout}>
              Logout
            </Button>
          )}
        </header>
      )}

      {/* ── Message area ────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-1 max-w-[85%] ${
              msg.sender === "user" ? "self-end items-end" : "self-start items-start"
            }`}
          >
            {/* Bubble */}
            <div
              className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.sender === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-muted text-foreground rounded-bl-sm"
              }`}
            >
              {msg.text}
            </div>

            {/* Intent badge (AI messages only) */}
            {msg.sender === "ai" && msg.intent && (
              <span
                className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${intentBadgeClass(msg.intent)}`}
              >
                {msg.intent}
              </span>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="self-start flex gap-1.5 px-4 py-3 bg-muted rounded-2xl rounded-bl-sm">
            <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce [animation-delay:300ms]" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Error banner ────────────────────────────────────────────────────── */}
      {error && (
        <div className="mx-4 mb-2 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
          {error}
          <button
            className="ml-2 underline text-xs"
            onClick={() => setError("")}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Input bar ───────────────────────────────────────────────────────── */}
      <div className="px-4 py-3 border-t bg-card shrink-0 flex gap-2">
        <Input
          ref={inputRef}
          placeholder="Ask an HR question…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
          className="flex-1"
        />
        <Button
          onClick={() => void sendMessage()}
          disabled={loading || !question.trim()}
          size="default"
        >
          {loading ? "…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
