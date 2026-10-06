/**
 * Holiday calendar helpers (D-034), shared by the Leave and Attendance pages.
 *
 * GET /holidays?year=YYYY returns national (fixed, id null) + HR-declared company holidays. Responses are cached per
 * year for the session; call `invalidateHolidays(year)` after adding/removing one.
 * `workingDaysBetween` mirrors the backend rule (`attendance_service.is_working_day`): Mon–Fri and not a holiday —
 * exactly what `count_leave_days` charges against a leave balance.
 */
import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { parseDate, toISODate } from "@/lib/format";
import type { Holiday, HolidayList } from "@/lib/types";

const cache = new Map<number, Promise<HolidayList>>();
const listeners = new Set<() => void>();

function fetchYear(year: number): Promise<HolidayList> {
  let p = cache.get(year);
  if (!p) {
    p = api.get<HolidayList>(`/holidays?year=${year}`);
    cache.set(year, p);
    p.catch(() => cache.delete(year));
  }
  return p;
}

export function invalidateHolidays(year?: number) {
  if (year === undefined) cache.clear();
  else cache.delete(year);
  listeners.forEach((l) => l());
}

export interface HolidayState {
  /** ISO date → holiday. */
  byDate: Map<string, Holiday>;
  items: Holiday[];
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Holidays of the given calendar years (deduplicated). Pass [] to skip. */
export function useHolidays(years: number[]): HolidayState {
  const key = [...new Set(years.filter((y) => y >= 2000 && y <= 2100))].sort().join(",");
  const [items, setItems] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(key !== "");
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const l = () => setTick((t) => t + 1);
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);

  useEffect(() => {
    if (!key) {
      setItems([]);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all(key.split(",").map((y) => fetchYear(Number(y))))
      .then((lists) => {
        if (alive) setItems(lists.flatMap((l) => l.items));
      })
      .catch((err: unknown) => {
        if (alive) setError(errorMessage(err, "Failed to load holidays."));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [key, tick]);

  const byDate = useMemo(() => new Map(items.map((h) => [h.date, h])), [items]);
  return {
    byDate,
    items,
    loading,
    error,
    reload: () => {
      key.split(",").forEach((y) => cache.delete(Number(y)));
      setTick((t) => t + 1);
    },
  };
}

/** Calendar years touched by an ISO date range. */
export function yearsBetween(from: string, to: string): number[] {
  const a = parseDate(from);
  const b = parseDate(to);
  if (!a || !b || b < a) return a ? [a.getFullYear()] : [];
  const out: number[] = [];
  for (let y = a.getFullYear(); y <= b.getFullYear() && out.length < 5; y++) out.push(y);
  return out;
}

export function isWeekend(iso: string): boolean {
  const d = parseDate(iso);
  return !!d && (d.getDay() === 0 || d.getDay() === 6);
}

/** Working days in [from, to] and the holidays that fall on weekdays inside it (same rule as the backend). */
export function workingDaysBetween(from: string, to: string, holidays: Map<string, Holiday>): { days: number; holidays: Holiday[] } {
  const a = parseDate(from);
  const b = parseDate(to);
  if (!a || !b || b < a) return { days: 0, holidays: [] };
  let days = 0;
  const hit: Holiday[] = [];
  const cur = new Date(a);
  for (let i = 0; cur <= b && i < 800; i++) {
    const iso = toISODate(cur);
    const dow = cur.getDay();
    const h = holidays.get(iso);
    if (dow !== 0 && dow !== 6) {
      if (h) hit.push(h);
      else days++;
    }
    cur.setDate(cur.getDate() + 1);
  }
  return { days, holidays: hit };
}
