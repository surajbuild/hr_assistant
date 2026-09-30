import { serve } from "bun";
import index from "./index.html";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

/**
 * Forward an incoming Bun request to the FastAPI backend.
 * Preserves method, body, Content-Type, and Authorization headers.
 */
async function proxyTo(req: Request, backendUrl: string): Promise<Response> {
  const headers: Record<string, string> = {};

  const contentType = req.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  const authorization = req.headers.get("authorization");
  if (authorization) headers["authorization"] = authorization;

  return fetch(backendUrl, {
    method: req.method,
    headers,
    // Only forward body for methods that can carry one
    body: ["GET", "HEAD"].includes(req.method) ? undefined : req.body,
    // Required so Bun streams the body correctly
    duplex: "half",
  } as RequestInit);
}

const server = serve({
  routes: {
    // ── Proxy: /auth/* → FastAPI /auth/* ────────────────────────────────────
    "/auth/:path*": async (req) => {
      const url = new URL(req.url);
      // Reconstruct the full path including any query string
      const target = `${BACKEND}${url.pathname}${url.search}`;
      return proxyTo(req, target);
    },

    // ── Proxy: /chat → FastAPI /chat ─────────────────────────────────────
    "/chat": async (req) => {
      return proxyTo(req, `${BACKEND}/chat`);
    },

    // ── Proxy: /dashboard/* → FastAPI /dashboard/* ───────────────────────
    "/dashboard/:path*": async (req) => {
      const url = new URL(req.url);
      const target = `${BACKEND}${url.pathname}${url.search}`;
      return proxyTo(req, target);
    },

    // ── Proxy: /reports/* → FastAPI /reports/* ───────────────────────────
    "/reports/:path*": async (req) => {
      const url = new URL(req.url);
      const target = `${BACKEND}${url.pathname}${url.search}`;
      return proxyTo(req, target);
    },

    // ── Serve React SPA for every other route ────────────────────────────
    "/*": index,
  },

  development: process.env.NODE_ENV !== "production" && {
    // Enable browser hot reloading in development
    hmr: true,

    // Echo console logs from the browser to the server
    console: true,
  },
});

console.log(`🚀 Server running at ${server.url}`);
console.log(`🔀 Proxying /auth/* and /chat → ${BACKEND}`);
