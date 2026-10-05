/**
 * Tiny History-API router (no dependency).
 *
 * - `useRoute()`         → { pathname, search, query }
 * - `navigate(path)`     → pushState (or replaceState with { replace: true })
 * - `<Link to="...">`    → anchor that navigates client-side (ctrl/cmd-click still opens a new tab)
 * - `matchPath(pattern, pathname)` → params for patterns like "/employees/:id/edit", or null
 *
 * SPA routes must never collide with `/api/*` (AGENTS.md §2.8).
 */
import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from "react";

const NAV_EVENT = "app:navigate";

function subscribe(callback: () => void) {
  window.addEventListener("popstate", callback);
  window.addEventListener(NAV_EVENT, callback);
  return () => {
    window.removeEventListener("popstate", callback);
    window.removeEventListener(NAV_EVENT, callback);
  };
}

function getSnapshot() {
  return window.location.pathname + window.location.search;
}

export function navigate(to: string, options: { replace?: boolean } = {}) {
  const current = window.location.pathname + window.location.search + window.location.hash;
  if (to === current) return;
  if (options.replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  window.dispatchEvent(new Event(NAV_EVENT));
  if (!options.replace) window.scrollTo({ top: 0 });
}

export interface RouteState {
  pathname: string;
  search: string;
  query: URLSearchParams;
}

export function useRoute(): RouteState {
  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const idx = snap.indexOf("?");
  const pathname = (idx >= 0 ? snap.slice(0, idx) : snap).replace(/\/+$/, "") || "/";
  const search = idx >= 0 ? snap.slice(idx) : "";
  return { pathname, search, query: new URLSearchParams(search) };
}

export function matchPath(pattern: string, pathname: string): Record<string, string> | null {
  const p = pattern.split("/").filter(Boolean);
  const s = pathname.split("/").filter(Boolean);
  if (p.length !== s.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    const seg = p[i]!;
    const val = s[i]!;
    if (seg.startsWith(":")) params[seg.slice(1)] = decodeURIComponent(val);
    else if (seg !== val) return null;
  }
  return params;
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string; replace?: boolean };

export function Link({ to, replace, onClick, children, ...rest }: LinkProps) {
  function handleClick(e: MouseEvent<HTMLAnchorElement>) {
    onClick?.(e);
    if (e.defaultPrevented) return;
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (rest.target && rest.target !== "_self") return;
    e.preventDefault();
    navigate(to, { replace });
  }
  return (
    <a href={to} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
}
