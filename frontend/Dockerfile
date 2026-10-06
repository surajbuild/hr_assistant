# ---------------------------------------------------------------------------
# AI HR Assistant — frontend image (Bun server: React SPA + /api proxy)
# ---------------------------------------------------------------------------
# src/index.ts is a Bun.serve() full-stack server: it serves the SPA via an HTML import
# (bundled by Bun at runtime, Tailwind via the bunfig.toml [serve.static] plugin) and
# proxies /api/* to BACKEND_URL with the /api prefix stripped. Production mode is simply
# `NODE_ENV=production bun src/index.ts` (= `bun start`): no HMR, minified bundle.
# `bun run build` (build.ts -> dist/) only emits static assets and is not used by the server.
# ---------------------------------------------------------------------------
ARG BUN_VERSION=1.4
FROM oven/bun:${BUN_VERSION}

WORKDIR /app

# Run everything (install + server) as the image's non-root "bun" user.
RUN chown bun:bun /app
USER bun

# Dependencies first for layer caching. All deps are installed (not --production):
# tailwindcss (devDependency) is needed by bun-plugin-tailwind when Bun bundles the SPA at runtime.
COPY --chown=bun:bun package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY --chown=bun:bun . .

ENV NODE_ENV=production \
    PORT=3000 \
    BACKEND_URL=http://backend:8000

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD bun -e "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["bun", "src/index.ts"]
