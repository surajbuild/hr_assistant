/** Formatting helpers shared by pages. */

const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** Parse "YYYY-MM-DD" (or an ISO datetime) without timezone shifts for plain dates. */
export function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "05 Oct 2026" */
export function formatDate(value: string | null | undefined): string {
  const d = parseDate(value);
  if (!d) return "—";
  return `${String(d.getDate()).padStart(2, "0")} ${MONTHS_SHORT[d.getMonth()]} ${d.getFullYear()}`;
}

/** "05 Oct 2026, 09:30" */
export function formatDateTime(value: string | null | undefined): string {
  const d = parseDate(value);
  if (!d) return "—";
  return `${formatDate(value)}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** "09:05:00" → "09:05" */
export function formatTime(value: string | null | undefined): string {
  if (!value) return "—";
  const m = /^(\d{1,2}):(\d{2})/.exec(value);
  if (m) return `${m[1]!.padStart(2, "0")}:${m[2]}`;
  const d = parseDate(value);
  if (!d) return value;
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/** 510 → "8h 30m" */
export function formatMinutes(mins: number | null | undefined): string {
  if (mins === null || mins === undefined || Number.isNaN(mins)) return "—";
  const total = Math.round(mins);
  if (total <= 0) return "0m";
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function formatINR(value: number | null | undefined, decimals = false): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return (decimals ? inr2 : inr).format(Number(value));
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits });
}

/** "half_day" → "Half Day" */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function initials(name: string | null | undefined): string {
  if (!name) return "?";
  const parts = name.trim().split(/[\s@.]+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "?";
  const second = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + second).toUpperCase();
}

export function monthLabel(month: number, year: number): string {
  return `${MONTHS_LONG[month - 1] ?? month} ${year}`;
}

export function monthShortLabel(month: number, year: number): string {
  return `${MONTHS_SHORT[month - 1] ?? month} ${year}`;
}

/** Local "YYYY-MM-DD" for a Date. */
export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** First and last ISO date of the month. */
export function monthRange(month: number, year: number): { from: string; to: string } {
  const last = new Date(year, month, 0).getDate();
  const mm = String(month).padStart(2, "0");
  return { from: `${year}-${mm}-01`, to: `${year}-${mm}-${String(last).padStart(2, "0")}` };
}

/** "2024-09" for a month/year. */
export function monthKey(month: number, year: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

/** Inclusive day count between two ISO dates. */
export function daysBetween(from: string, to: string): number {
  const a = parseDate(from);
  const b = parseDate(to);
  if (!a || !b) return 0;
  return Math.max(1, Math.round((b.getTime() - a.getTime()) / 86_400_000) + 1);
}

/** Download rows as CSV (client-side). */
export function downloadCSV(filename: string, headers: string[], rows: (string | number | null | undefined)[][]) {
  const escape = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const csv = [headers, ...rows].map((r) => r.map(escape).join(",")).join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
