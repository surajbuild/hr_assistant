# AI HR Assistant — Frontend

Bun + React 19 + TypeScript + Tailwind v4 SPA. Project docs live in the repository root: start with
[`../AGENTS.md`](../AGENTS.md) and [`../README.md`](../README.md).

```bash
bun install          # first time
bun dev              # dev server with HMR on http://localhost:3000 (PORT=3001 bun dev for another port)
bunx tsc --noEmit -p .   # type-check
bun run build        # production build into dist/
bun start            # serve production build
```

- `src/index.ts` — Bun server: proxies `/api/*` → `BACKEND_URL` (default `http://localhost:8000`, prefix stripped) and serves the SPA.
- `src/lib/` — `api.ts` (fetch wrapper, auth header, 401 → logout), `auth.tsx` (AuthContext), `router.tsx` (History-API router), `nav.ts` (role-gated menu), `types.ts`.
- `src/components/layout/AppShell.tsx` — top navbar layout modelled on the reference HRMS.
- `src/pages/` — one file per module.
- Theme tokens: `styles/globals.css`.

Restart `bun dev` after moving/creating many files if the browser shows a stale "Could not resolve" error (KNOWN_ISSUES KI-005).
