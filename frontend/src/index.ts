/**
 * Bun dev/prod server for the AI HR Assistant frontend.
 *
 * - `/api/*`  → proxied to the FastAPI backend (`BACKEND_URL`, default http://localhost:8000)
 *               with the `/api` prefix stripped. Method, body (streamed), query string and the
 *               relevant headers are forwarded (plus X-Forwarded-For = the real client IP, for the
 *               backend's login rate limit); the backend response is passed through unchanged
 *               (status, content-type, content-disposition for xlsx downloads, ...).
 * - `/*`      → the React SPA (client-side routing in src/lib/router.tsx).
 */
import { serve, type Server } from "bun";
import index from "./index.html";

const BACKEND = (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");

/** Request headers forwarded to the backend. */
const FORWARD_REQUEST_HEADERS = ["content-type", "authorization", "accept", "accept-language", "cookie"];

/**
 * Response headers that must not be copied verbatim: Bun's fetch already decoded the body,
 * so encoding/length headers from upstream would be wrong.
 */
const DROP_RESPONSE_HEADERS = new Set(["content-encoding", "content-length", "transfer-encoding", "connection"]);

async function proxyApi(req: Request, server: Server<unknown>): Promise<Response> {
  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/api/, "") || "/";
  const target = `${BACKEND}${path}${url.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  // The backend rate-limits logins per client IP (D-031). Overwrite — never append to — whatever
  // X-Forwarded-For the browser sent, so a client cannot choose its own IP.
  const clientIp = server.requestIP(req)?.address;
  if (clientIp) headers.set("x-forwarded-for", clientIp);

  const hasBody = !["GET", "HEAD"].includes(req.method);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body: hasBody ? req.body : undefined,
      redirect: "manual",
      // Required so Bun streams the request body
      duplex: "half",
    } as RequestInit);
  } catch (err) {
    console.error(`[proxy] ${req.method} ${target} failed:`, err);
    return Response.json(
      { detail: "Unable to connect to server. Please check if the backend is running." },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!DROP_RESPONSE_HEADERS.has(key.toLowerCase())) responseHeaders.append(key, value);
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

const server = serve({
  routes: {
    // ── Proxy: /api/* → FastAPI (prefix stripped) ──────────────────────────
    "/api/*": proxyApi,

    // ── Serve React SPA for every other route ──────────────────────────────
    "/*": index,
  },

  development: process.env.NODE_ENV !== "production" && {
    // Enable browser hot reloading in development
    hmr: true,

    // Echo console logs from the browser to the server
    console: true,
  },
});

console.log(`Server running at ${server.url}`);
console.log(`Proxying /api/* -> ${BACKEND}`);
