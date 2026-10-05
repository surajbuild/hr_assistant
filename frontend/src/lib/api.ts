/**
 * HTTP client for the FastAPI backend.
 *
 * All calls go through the Bun proxy under `/api` (AGENTS.md §2.7). The JWT from localStorage
 * (`hr_token`) is attached as a Bearer token; a 401 clears it and redirects to /login.
 * Errors are thrown as `ApiError` carrying the backend `detail` message.
 */

export const TOKEN_KEY = "hr_token";
const BASE = "/api";

export const NETWORK_ERROR_MESSAGE = "Unable to connect to server. Please check if the backend is running.";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string };

/** Turn a FastAPI `detail` (string | validation array | object) into a readable message. */
export function formatDetail(detail: unknown, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[]).map((d) => {
      const loc = (d.loc ?? []).filter((p) => p !== "body" && p !== "query" && p !== "path").join(".");
      const msg = d.msg ?? "Invalid value";
      return loc ? `${loc}: ${msg}` : msg;
    });
    return parts.join("; ") || fallback;
  }
  if (typeof detail === "object") {
    const maybe = detail as { message?: string; msg?: string };
    return maybe.message ?? maybe.msg ?? fallback;
  }
  return String(detail);
}

function handleUnauthorized(path: string) {
  // Login failures are also 401 — let the login form show the message instead of redirecting.
  if (path.startsWith("/auth/login")) return;
  setToken(null);
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function errorFromResponse(res: Response, path: string): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const ct = res.headers.get("content-type") ?? "";
    if (ct.includes("application/json")) {
      const body = (await res.json()) as { detail?: unknown };
      detail = body?.detail;
    } else {
      const text = await res.text();
      detail = text && text.length < 300 ? text : null;
    }
  } catch {
    /* ignore parse errors */
  }
  if (res.status === 401) handleUnauthorized(path);
  const fallback =
    res.status === 403
      ? "You do not have permission to perform this action."
      : res.status === 404
        ? "The requested resource was not found."
        : res.status === 502 || res.status === 503 || res.status === 504
          ? NETWORK_ERROR_MESSAGE
          : `Request failed (status ${res.status}).`;
  return new ApiError(formatDetail(detail, fallback), res.status);
}

async function rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }
  if (!res.ok) throw await errorFromResponse(res, path);
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "Content-Type": "application/json" };
  }
  const res = await rawRequest(path, init);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) return null;
  const star = disposition.match(/filename\*=(?:UTF-8'')?([^;]+)/i);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ""));
    } catch {
      /* fall through */
    }
  }
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain?.[1]?.trim() ?? null;
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  del: <T>(path: string) => request<T>("DELETE", path),

  /** Multipart upload. Do not set Content-Type: the browser adds the boundary. */
  async upload<T>(path: string, form: FormData): Promise<T> {
    const res = await rawRequest(path, { method: "POST", body: form });
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  },

  /** Download a file (e.g. xlsx report). Returns the filename used. */
  async download(path: string, fallbackFilename: string): Promise<string> {
    const res = await rawRequest(path, { method: "GET", headers: { Accept: "*/*" } });
    const blob = await res.blob();
    const filename = filenameFromDisposition(res.headers.get("content-disposition")) ?? fallbackFilename;
    saveBlob(blob, filename);
    return filename;
  },
};

export function errorMessage(err: unknown, fallback = "Something went wrong."): string {
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
