/**
 * Authentication context: JWT token + current user (GET /api/auth/me).
 *
 * - login(email, password) → POST /api/auth/login → stores `access_token` in localStorage (`hr_token`)
 * - logout() clears the token
 * - On load, a `#token=...` URL hash (Google OAuth redirect) is stored and stripped; `#error=...` (failed Google
 *   sign-in) is read by the login page via consumeHashError().
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, getToken, setToken as persistToken } from "./api";
import type { CurrentUser, LoginResponse, Role } from "./types";

/**
 * Google OAuth goes through the same-origin /api proxy (a full-page navigation, not fetch): the proxy passes the
 * backend's 302 to Google and its session cookie through unchanged, so this works wherever the SPA is served —
 * including Docker, where the backend port is not published. GOOGLE_REDIRECT_URI may point at the backend directly
 * (local dev) or at `<frontend>/api/auth/google/callback` (deployments).
 */
export const GOOGLE_LOGIN_URL = "/api/auth/google/login?next=frontend";

interface AuthContextValue {
  token: string | null;
  user: CurrentUser | null;
  role: Role | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function consumeHashToken() {
  const hash = window.location.hash;
  if (!hash || !hash.includes("token=")) return;
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const token = params.get("token") ?? params.get("access_token");
  if (token) {
    persistToken(token);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}

/**
 * A failed Google sign-in comes back as `/login#error=<reason>` (backend `_oauth_failure`, D-045).
 * Returns the reason once and strips it from the URL.
 */
export function consumeHashError(): string | null {
  const hash = window.location.hash;
  if (!hash || !hash.includes("error=")) return null;
  const message = new URLSearchParams(hash.replace(/^#/, "")).get("error");
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return message ? message.slice(0, 300) : null;
}

/** Fallback when GET /auth/me is unavailable (404): derive a minimal user from the JWT payload. */
function userFromToken(token: string): CurrentUser | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as {
      sub?: string;
      role?: string;
      email?: string;
      user_id?: number;
    };
    if (!json.role) return null;
    return {
      user_id: json.user_id ?? (Number(json.sub) || 0),
      email: json.email ?? (json.sub && json.sub.includes("@") ? json.sub : "user"),
      role: json.role.toLowerCase() as Role,
      status: "active",
      employee: null,
    };
  } catch {
    return null;
  }
}

async function fetchMe(token: string): Promise<CurrentUser> {
  try {
    return await api.get<CurrentUser>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      const fallback = userFromToken(token);
      if (fallback) return fallback;
    }
    throw err;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => {
    consumeHashToken();
    return getToken();
  });
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState<boolean>(() => !!getToken());

  const skipNextLoad = useRef(false);

  const loadUser = useCallback(async () => {
    if (skipNextLoad.current) {
      skipNextLoad.current = false;
      return;
    }
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await fetchMe(getToken() ?? "");
      setUser(me);
    } catch {
      // 401 is handled by api.ts (clears token + redirect); other errors → treat as logged out
      persistToken(null);
      setTokenState(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [token, loadUser]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<LoginResponse>("/auth/login", { email, password });
    persistToken(res.access_token);
    let me: CurrentUser;
    try {
      me = await fetchMe(res.access_token);
    } catch (err) {
      persistToken(null);
      throw err;
    }
    skipNextLoad.current = true;
    setUser(me);
    setTokenState(res.access_token);
    return me;
  }, []);

  const logout = useCallback(() => {
    persistToken(null);
    setTokenState(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      role: (user?.role?.toLowerCase() as Role | undefined) ?? null,
      loading,
      login,
      logout,
      refresh: loadUser,
    }),
    [token, user, loading, login, logout, loadUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function hasRole(role: Role | null, allowed: readonly Role[]): boolean {
  return !!role && allowed.includes(role);
}

export function displayName(user: CurrentUser | null): string {
  if (!user) return "";
  return user.employee?.name ?? user.email.split("@")[0] ?? user.email;
}
