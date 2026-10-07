/**
 * AI Assistant — static metadata: suggested prompts per role, confidence labels, data-source labels.
 * Prompts only use question types the backend router answers (app/ai/router.py): own attendance/leave/salary,
 * rankings and thresholds (HR/Admin company-wide, managers team-scoped — D-032), team / department attendance,
 * pending leave requests, headcount, company and department payroll (HR/Admin), the holiday calendar (D-034) and
 * policy questions (RAG over uploaded documents → policies.json). The first four are shown as composer chips.
 */
import type { Role } from "@/lib/types";

export const PROMPTS: Record<Role, string[]> = {
  employee: [
    "What is my attendance this month?",
    "What is my leave balance?",
    "How much PF was deducted last month?",
    "How many hours did I work last week?",
    "How many casual leaves are allowed?",
    "What are the company holidays this year?",
  ],
  manager: [
    "Which members of my team worked overtime last week?",
    "How many of my team were present today?",
    "Which leave requests are pending approval?",
    "Who on my team was late the most this month?",
    "What is my leave balance?",
    "What is the leave policy?",
  ],
  hr: [
    "Who worked the most overtime this month?",
    "Show employees with more than 5 late entries this month.",
    "How many employees are on leave today?",
    "Show department-wise overtime this month.",
    "What was Aman's attendance percentage in August 2024?",
    "What is the payroll of each department?",
  ],
  admin: [
    "How many employees were present today?",
    "Who worked the most overtime this month?",
    "How many employees are in each department?",
    "What is the total payroll for the latest month?",
    "Which leave requests are pending approval?",
    "What is the leave policy?",
  ],
};

/** What each role's answers are scoped to (mirrors the backend RBAC, AGENTS.md §3.2). */
export const ACCESS_SCOPE: Record<Role, string> = {
  employee: "Your own attendance, leave and salary, plus company policies and holidays.",
  manager: "You and your direct reports (attendance, leave, rankings). Salary: your own only.",
  hr: "Company-wide HR data including payroll, plus policies and holidays.",
  admin: "Company-wide HR data including payroll, plus policies and holidays.",
};

export type ConfidenceKey =
  | "data_verified"
  | "unverified"
  | "document_grounded"
  | "policy_reference"
  | "not_found"
  | "clarification_needed"
  | "access_denied"
  | "unavailable"
  | "general";
export type ConfidenceTone = "present" | "brand" | "half" | "late" | "absent" | "neutral";

export interface ConfidenceInfo {
  label: string;
  description: string;
  tone: ConfidenceTone;
}

/** POST /chat `confidence` values (app/api/chat.py `_confidence`). */
export const CONFIDENCE: Record<ConfidenceKey, ConfidenceInfo> = {
  data_verified: {
    label: "Verified HR data",
    description: "Numbers were calculated by the HR system from database records; the AI only phrased them.",
    tone: "present",
  },
  unverified: {
    label: "Check figures",
    description: "The answer contains a number that is not in the HR records it was given. Check it against the source page before relying on it.",
    tone: "late",
  },
  document_grounded: {
    label: "From HR documents",
    description: "Answered from uploaded HR documents. The cited documents and pages are listed with the answer.",
    tone: "brand",
  },
  policy_reference: {
    label: "Policy reference",
    description: "No uploaded document matched, so the built-in company policy reference was used.",
    tone: "half",
  },
  not_found: {
    label: "No matching records",
    description: "The HR system has no records for what was asked (for example that person or period).",
    tone: "late",
  },
  clarification_needed: {
    label: "Needs clarification",
    description: "It was not clear whose records (or which group) the question is about, so nothing was retrieved. Name the employee or rephrase.",
    tone: "late",
  },
  access_denied: {
    label: "Access restricted",
    description: "Your role is not allowed to see this. Nothing was retrieved and the AI was not asked.",
    tone: "absent",
  },
  unavailable: {
    label: "Service unavailable",
    description: "The HR data or the AI service could not be reached, so no answer was produced. Please try again.",
    tone: "neutral",
  },
  general: {
    label: "General answer",
    description: "General help that is not based on HR records or documents.",
    tone: "neutral",
  },
};

export const CONFIDENCE_ORDER: ConfidenceKey[] = [
  "data_verified",
  "unverified",
  "document_grounded",
  "policy_reference",
  "not_found",
  "clarification_needed",
  "access_denied",
  "unavailable",
  "general",
];

export function confidenceInfo(value: string | number | null | undefined): (ConfidenceInfo & { key: ConfidenceKey }) | null {
  if (typeof value !== "string") return null;
  const key = value.toLowerCase() as ConfidenceKey;
  const info = CONFIDENCE[key];
  return info ? { ...info, key } : null;
}

/** Friendly names for the non-document `source` / `data_source` values the backend logs. */
const DATA_SOURCES: Record<string, string> = {
  attendance_database: "Attendance records",
  leave_database: "Leave records",
  salary_database: "Payroll records",
  employee_database: "Employee records",
  "policies.json": "Company policy reference",
};

/** Sources that are not worth a chip (no data behind them). */
const SILENT_SOURCES = new Set(["general", "guardrail", "unknown", "error", ""]);

export interface SourceChip {
  key: string;
  label: string;
  kind: "document" | "data";
}

const DOC_FILE = /\.(pdf|docx?|txt)$/i;

/** Chips for one answer: documents with their cited pages (grouped), or the HR data source. */
export function sourceChips(
  sources: { document: string; page?: number | null }[] | undefined,
  source: string | null | undefined,
): SourceChip[] {
  if (sources && sources.length > 0) {
    const pages = new Map<string, Set<number>>();
    for (const s of sources) {
      const set = pages.get(s.document) ?? new Set<number>();
      if (s.page) set.add(s.page);
      pages.set(s.document, set);
    }
    return [...pages.entries()].map(([doc, set]) => {
      const list = [...set].sort((a, b) => a - b);
      const suffix = list.length === 0 ? "" : list.length === 1 ? ` · p. ${list[0]}` : ` · pp. ${list.join(", ")}`;
      return { key: doc, label: `${doc}${suffix}`, kind: "document" as const };
    });
  }
  const s = (source ?? "").trim();
  if (SILENT_SOURCES.has(s.toLowerCase())) return [];
  const known = DATA_SOURCES[s];
  if (known) return [{ key: s, label: known, kind: "data" }];
  return [{ key: s, label: s, kind: DOC_FILE.test(s) ? "document" : "data" }];
}

/** "ATTENDANCE" → "Attendance"; UNKNOWN is shown as "Unclassified". */
export function intentLabel(intent: string | null | undefined): string | null {
  if (!intent) return null;
  const v = intent.toUpperCase();
  if (v === "UNKNOWN") return "Unclassified";
  return v.charAt(0) + v.slice(1).toLowerCase();
}

/** Seconds to wait from a 429 message ("Please try again in 37 seconds."). */
export function retryAfterSeconds(message: string): number {
  const m = /(\d+)\s*seconds?/i.exec(message);
  const n = m ? Number(m[1]) : NaN;
  return Number.isFinite(n) && n > 0 ? Math.min(n, 3600) : 60;
}
