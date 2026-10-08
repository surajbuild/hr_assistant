# AGENTS.md — Mandatory Development Policy

> **Every agent (human or AI) MUST read this file before doing any development work on this repository.**
> The repository documentation is the persistent memory of this project. Do not rely on chat history.
> **If it isn't written in the repository, assume the next agent does not know it.**

---

## 0. Startup Procedure (do this every session, in order)

1. Read `AGENTS.md` (this file).
2. Read `README.md`.
3. Read `PROJECT_STATUS.md`.
4. Read `DEVELOPMENT_PLAN.md`.
5. Read the relevant sections of `PROJECT_DECISIONS.md` and `KNOWN_ISSUES.md`.
6. Read the relevant PRD requirements in `prd_extracted.md`.
   *(UI work: also read `frontend/DESIGN.md` and, while the redesign is in progress, `frontend/REDESIGN_NOTES.md`.)*
7. Inspect the actual code before making assumptions — docs can drift; code is the ground truth of *current behaviour*.
8. Only then begin implementation.

### Source-of-truth priority (highest first)

1. Current PRD / explicit product requirement (`prd_extracted.md`, or a newer explicit instruction from the product owner)
2. `AGENTS.md`
3. `PROJECT_DECISIONS.md`
4. Current implementation
5. `DEVELOPMENT_PLAN.md`
6. `PROJECT_STATUS.md`
7. `README.md`
8. Conversation history

If two sources contradict each other, **do not silently pick one**. Name the contradiction, resolve it using the
priority above, and record the resolution in `PROJECT_DECISIONS.md`.

### Handoff procedure (end of every substantial session)

Update, as applicable: `PROJECT_STATUS.md`, `DEVELOPMENT_PLAN.md`, `KNOWN_ISSUES.md`, `PROJECT_DECISIONS.md`,
`CHANGELOG.md`, `README.md` (if setup/architecture changed), and `AGENTS.md` (if a permanent rule/lesson was learned).
Never delete still-relevant knowledge just to keep files short. Mark completed work as completed; don't erase it.

---

## 1. What this project is

**AI HR Assistant** — an HRMS-style web application (module layout and roles modelled on
`https://hrms.nectorinternational.com/`; visual design = design system v2, D-026) whose distinguishing feature is an **AI chat assistant** that answers
natural-language HR questions from MySQL data (controlled tools) and from uploaded HR documents (RAG), while
enforcing role-based permissions. The PRD (`prd_extracted.md`) is the product requirement; the reference site is the
**module/role reference only** (D-002; its visual/navigation part was superseded by D-026).

- Backend: Python 3 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · MySQL (PyMySQL) · JWT (PyJWT) · bcrypt · Authlib (Google OAuth) · openpyxl
- Frontend: Bun · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui-style components on Radix primitives · lucide-react icons · recharts (`frontend/`, design system: `frontend/DESIGN.md`)
- AI: OpenAI-compatible Chat Completions API (currently OpenRouter) via `app/ai/llm.py`; rule-based intent router `app/ai/router.py`
- RAG: local document parsing (pypdf / python-docx / txt) → chunking → term-frequency vectors (pure Python) stored in MySQL → Okapi BM25 retrieval (`app/rag/`, D-004)

---

## 2. Architecture rules

1. **Layering is mandatory:** `app/api/*` (HTTP only: schemas, status codes, auth dependencies) → `app/services/*`
   (business logic & calculations, framework-free, raise domain exceptions) → `app/database/*` (models, session, queries).
   - Route handlers must not contain business calculations. Put them in a service so the AI tools can reuse them.
   - Services must not import FastAPI / raise `HTTPException`. They raise domain errors (e.g. `EmployeeNotFoundError`),
     and the router maps them to HTTP codes.
2. **The AI layer never gets raw DB access.** `app/ai/router.py` calls service functions only (controlled tools).
   The LLM never generates or executes SQL. (PRD §16)
3. **Calculations happen in Python, not in the LLM.** Attendance %, overtime, late counts, leave balances, salary
   totals are computed in services; the LLM only phrases the already-computed numbers. (PRD §20)
4. **Every chat interaction is logged** to `chat_logs` (user, question, intent, source, response, latency, error). (PRD §28)
5. New routers must be registered in `app/main.py`.
6. Schema changes **must** go through an Alembic migration in `alembic/versions/` — never edit tables by hand, never
   use `Base.metadata.create_all` against the real DB.
7. The frontend talks to the backend **only through the Bun proxy under the `/api` prefix** (`frontend/src/index.ts`
   strips `/api` and forwards to `BACKEND_URL`). Do not hardcode `http://localhost:8000` in React code.
8. Frontend routing is client-side (History API) handled in `frontend/src/lib/router.tsx`; SPA routes must never
   collide with `/api/*`.

## 3. Security rules (non-negotiable)

1. **Backend authorization is the source of truth.** Hiding a menu item or button in React is UX only — every
   endpoint must enforce role/ownership checks server-side with `get_current_user` / `require_role` + ownership
   logic. Never trust IDs sent by the client for "my" data; always derive from `current_user`.
2. Role model (DB values, lowercase): `employee`, `manager`, `hr`, `admin`.
   - `employee` → own data only.
   - `manager` → own data + direct reports (`employees.manager_id == manager's employee id`). **No salary access to
     anyone but themselves.**
   - `hr` → company-wide HR data incl. salary.
   - `admin` → full access incl. user management and chat audit logs.
3. Salary of another employee must never be returned to `employee` or `manager` roles — via REST **or** via chat.
4. Chat guardrails (`app/ai/guardrails.py`) must run before data retrieval; prompt-injection attempts
   ("ignore previous instructions…", "give me admin access") must be refused without touching data.
5. Login errors stay generic ("Invalid email or password.") to prevent account enumeration.
6. Never log passwords, tokens, or full salary tables. Never commit `.env`. Keep `.env.example` updated when you add a variable.
7. File uploads: whitelist extensions (`pdf`, `docx`, `txt`), cap size (10 MB), store under `documents/` with a
   generated filename — never trust the client filename for the storage path.
8. `JWT_SECRET_KEY` and `SESSION_SECRET_KEY` must be ≥ 32 bytes — the app refuses to start otherwise (`load_secret`, D-031).
9. `/auth/login` and `/chat` are rate limited (429 + `Retry-After`, `app/utils/rate_limit.py`, in-memory → one uvicorn
   worker). Only trust `X-Forwarded-For` through `rate_limit.client_ip` (trusted proxies only).
10. Nobody reviews their own request — leave (D-022) or attendance correction (D-033); HR/Admin cannot edit their own
   attendance record directly.
11. Google sign-in (D-045): link an identity to an existing account only when `email_verified` is true; never create
   accounts for unknown Google users unless their domain is in `GOOGLE_ALLOWED_DOMAINS`.
12. The chat must never answer a question about someone else (a name in any case, "his", "my manager's", an ambiguous
   name) with the caller's own record, and must never guess between employees who share a name (D-043, D-044).

## 4. Database rules

- MySQL is the system of record. Connection string comes from `DATABASE_URL` in `.env`.
- Tables: `employees`, `users`, `attendance`, `leaves`, `salary`, `documents`, `document_chunks`, `chat_logs`, `holidays`,
  `attendance_corrections` (+ `alembic_version`). New tables must also be added to `scripts/db_snapshot.py` `TABLES`.
- `employees.monthly_gross_salary` is **confidential** (D-021): serialize it only for HR/Admin or the employee themself
  (`employee_service.serialize_employee(..., include_salary=employee_service.can_view_salary(user, emp_id))`).
- Enum-like columns are stored as **lowercase strings** (see enums in `app/database/models.py`). Keep using the enum `.value`s.
- Departments are **derived** from `employees.department` (no departments table) — see D-005.
- Deleting an employee is a **soft delete** (status → `inactive`, linked user → `inactive`) so attendance/salary history is preserved — see D-006.
- Demo/seed data: `python scripts/seed_db.py` (data in `app/data/seed_data.json`). The seed dataset covers **Aug–Sep 2024**.
  Current-month demo data: `python scripts/generate_demo_month.py` (idempotent, D-024) — run it each new month you demo.
  The dashboard falls back to the latest date that has attendance when today has none.
- Payroll rules (LOP, PF, OT pay) live as constants at the top of `app/services/salary_service.py` (D-021); the national
  holidays are `attendance_service.COMPANY_HOLIDAYS`, HR-declared ones are the `holidays` table (D-034) — anything counting
  working days must pass `holiday_service.get_declared_holiday_dates(db, …)` as `extra_holidays`/`holidays`. Never duplicate
  these numbers elsewhere.
- A month whose salary row is paid (`paid_at`) is **locked**: no payroll regeneration, no attendance correction/edit (D-033,
  D-036). Mark-as-paid is irreversible.

## 5. Testing rules

- Tests live in `tests/` and are **standalone scripts** that run against the **dev MySQL database configured in `.env`**.
  Run one with `python tests/test_xxx.py` or all with `python scripts/run_tests.py`. They print `[PASS]/[FAIL]` and exit
  non-zero on failure.
- **A test run must leave the dev database byte-identical (D-023).** Rules:
  - Create your own rows with unique markers (codes `T-<AREA>-*`, emails `@hrtest.dev`, document names `RAGTEST*`) and
    delete them in `finally`. Never modify or delete seeded/demo rows you did not create.
  - Any test that calls `POST /chat` must use `tests/helpers.TrackingClient(app, db)` and call
    `client.cleanup_chat_logs()` in `finally` (`/chat` always writes a `chat_logs` row). `TrackingClient` also resets the
    per-user chat rate limit before each `/chat` call (D-031); don't log in more than ~30×/min from one test file.
  - Assertions must not depend on how much demo data exists (derive expectations from the DB, compare deltas, or
    scope queries, e.g. `retriever.search(..., document_ids=own_ids)`).
  - Verify before handing off: `python scripts/db_snapshot.py save before.json` → `python scripts/run_tests.py` →
    `python scripts/db_snapshot.py diff before.json` must print "Database unchanged". `python scripts/db_snapshot.py isolate`
    names the offending test file.
- `pytest` can also collect them, but the canonical runner is `scripts/run_tests.py`.
- Tests that depend on seed data assume `scripts/seed_db.py` has been run. Do not hard-code employee counts higher than the seed provides (6 employees).
- UI changes: run the browser QA harness `python scripts/ui_qa.py` (needs `pip install -r requirements-dev.txt`, both
  servers running, Microsoft Edge installed; `--base http://localhost:3001` when :3000 is the Docker stack) — it must report
  `0 issue(s)`; then look at the screenshots it writes.
- Every new endpoint needs at least: happy path, 401 unauthenticated, 403 wrong role, ownership/isolation check.
- LLM calls must be mocked in tests (`unittest.mock.patch("app.api.chat.generate_response", ...)`) — never call the real provider from tests.
- Run the full suite before handing off and record the result in `PROJECT_STATUS.md`.

## 6. Coding conventions

### Python
- Type hints everywhere; Pydantic v2 models for request/response schemas (`model_config = {"from_attributes": True}` or `class Config: from_attributes = True`, matching the surrounding file).
- Module docstring at the top of each file explaining purpose and endpoints (match existing style).
- Section separators `# -----` as used in existing files.
- Domain exceptions defined in the service module (`class XxxError(Exception)`).
- Dates: `date` / `datetime` objects; month numbers 1–12.

### Frontend (TypeScript/React)
- Function components + hooks. Pages in `frontend/src/pages/`, shared UI in `frontend/src/components/`, API client in `frontend/src/lib/api.ts`.
- All HTTP calls go through `lib/api.ts` (adds `Authorization: Bearer`, handles 401 → logout).
- Use the existing `@/components/ui/*` primitives (Button, Card, Input, Label, Select, Textarea) before inventing new ones.
- Icons: `lucide-react` only.
- No `any` unless unavoidable; define response types in `lib/types.ts`.

## 7. UI/UX rules (design system v2 — see `frontend/DESIGN.md`, decision D-026)

> The product owner replaced the visual/navigation presentation of D-002 (top navbar, navy palette) with a premium SaaS
> design. **`frontend/DESIGN.md` is the source of truth for tokens, components and patterns; read it before UI work.**
> Still binding from D-002: module list and menu order, role-gated menu, role-specific dashboard greetings.

- **Navigation shell:** collapsible **left sidebar** (≥1280px expanded 248px, user-collapsible to a 68px icon rail; 768–1279px
  icon rail with tooltips; <768px hamburger → focus-trapped drawer) + slim sticky **56px top bar** (breadcrumb, ⌘/Ctrl+K
  command palette, notification bell **for approver roles only**, theme toggle, profile menu). Content max width 1400px,
  16/24/32px gutters, `#f8fafc`-style neutral page background (token `--background`).
- Menu items (grouped Overview · People · Workspace · Insights · Admin; order unchanged): Dashboard · My Profile · Employees ·
  Departments · Attendance · Leave · Payroll · Documents · Reports · AI Assistant · Settings (admin). Filtered by role with the
  same role sets the backend enforces (`lib/nav.ts`). The command palette lists only pages the role may open.
- **Tokens only:** every colour, radius and shadow is a CSS variable in `frontend/styles/globals.css` with a light **and** a
  dark value. **No hex in components. No `text-white`/`bg-white`/raw palette classes in new code** (use `bg-brand
  text-brand-foreground`, `bg-surface`, `text-muted-foreground`, `bg-status-*-bg text-status-*-fg`, …). Accent = indigo;
  semantic colours are for status only, one fixed colour per status shared by badges, charts and calendars.
- Type: Inter; title 24/600, section 16/600, body 14/400, meta 12/500; tabular numerals on every metric. Radius 8px controls /
  12px cards; 8px spacing grid; 1px borders; one soft shadow (`shadow-float`) for floating layers only; motion 150–250ms and
  honours `prefers-reduced-motion`.
- **Dark mode:** system by default, toggle in the top bar (`ThemeProvider`, `localStorage` `hr_theme`), applied before first
  paint. Every new view must be checked in light **and** dark.
- Reuse the shared system (`DESIGN.md` §4): `components/ui/*` primitives (Radix-based dialog/dropdown/tooltip/popover/switch),
  `PageHeader`/`Panel`/`StatCard`/`DataTable`/`StatusBadge`/`States`/`Modal`/`Tabs`/`Segmented`/`Toast`. Dialogs and drawers
  must be Radix (focus trap, Escape, focus returns to the opener). Icons: `lucide-react` only; charts: `recharts` only.
- Every data view needs **loading (skeleton), empty (with a next action) and error (with retry)** states; every mutation gives
  toast feedback; forms get inline validation, labels, focus rings and loading/disabled submit buttons.
- Status badges: colored pills (present/approved/active/paid = green, absent/rejected = red, late/pending = amber, half day =
  sky, leave = violet, holiday/weekend/inactive = slate) via `StatusBadge`.
- **No fake data.** A widget without an existing endpoint is derived client-side from existing endpoints or hidden — never
  invent an API or numbers (e.g. no notification bell for employees, no deltas without history).
- Dashboards are role-specific (admin / hr / manager / employee feel different). Greeting wording: "Welcome, Admin! Full system
  overview." / "Welcome, HR! …" / "Welcome, Manager! Team overview." / "Welcome back, <first name>!".
- Must be usable at 390 px: no horizontal page scroll; tables scroll **inside** their card (scroll containers need `relative`
  so `sr-only`/absolute children can't widen the page); dialogs become bottom sheets.
- Accessibility: AA contrast (axe clean in both themes), visible `:focus-visible`, keyboard-operable everything (rows with
  `onRowClick` are keyboard-activatable), `aria-label` on icon-only buttons.
- Never show an action the backend will refuse for this user (e.g. approving your own leave, deactivating yourself) — hide it
  and, where the reason isn't obvious, explain it with a `Notice`.
- Adding a menu item or changing the shell? Re-run `python scripts/ui_qa.py` (asserts sidebar/rail/drawer per width, role menus).
- The redesign is complete (Part 1 + Part 2, D-040): every page uses design system v2 and the dark-mode legacy bridge
  is gone — raw palette classes (`bg-white`, `slate-*`, `text-white`) now render wrongly in dark mode, so use tokens only.
  Filled success buttons use `status-present-solid` (AA with white text). After UI work run `ui_qa.py` **and** an axe scan in
  both themes (`ui_qa.py` checks the light theme only).

---

## 8. Things agents MUST do

- Follow the startup and handoff procedures above.
- Enforce permissions on the backend for every new endpoint and add tests for it.
- Keep `README.md` API table and `.env.example` in sync with the code.
- Add an Alembic migration for every model change and run `alembic upgrade head`.
- Record significant decisions in `PROJECT_DECISIONS.md` and newly found bugs in `KNOWN_ISSUES.md`.
- Use the `/api` proxy prefix from the frontend.
- Prefer extending existing services over duplicating queries.
- Restart `bun dev` after creating a new frontend file imported via `@/` (KI-005).
- Ask the product owner before changing a permission rule; record the answer in `PROJECT_DECISIONS.md` (e.g. D-022).

## 9. Things agents MUST NOT do

- Must NOT let the LLM compute numbers or query the DB directly.
- Must NOT return another employee's salary to non-HR/admin users (REST or chat).
- Must NOT rely on frontend-only role checks.
- Must NOT hard-delete employees, attendance, salary, or chat logs.
- Must NOT commit `.env`, uploaded documents (`documents/`), or `__pycache__`.
- Must NOT call the real LLM provider in automated tests.
- Must NOT replace the doc files with vague summaries or delete historical decisions.
- Must NOT add heavyweight dependencies (torch, sentence-transformers, chromadb, faiss) without a recorded decision — see D-004.
- Must NOT commit/push to git unless the product owner asks.
- Must NOT let a test touch rows it did not create, and must NOT re-seed the real demo data from a test.
- Must NOT allow anyone (including HR/Admin) to approve their own leave (D-022, confirmed by the product owner) or review their
  own attendance correction (D-033).
- Must NOT expose `monthly_gross_salary` or another person's salary to managers or employees.

## 10. Known constraints

- Windows dev machine; shell is PowerShell / Git Bash. `requirements.txt` was historically UTF-16 — keep it **UTF-8**.
- The LLM provider is OpenRouter (`LLM_BASE_URL=https://openrouter.ai/api/v1`, `LLM_MODEL=openai/gpt-4o-mini`). OpenRouter
  does not reliably offer an embeddings endpoint, which is why RAG uses local TF-IDF (D-004).
- Seed data is from 2024; "this month" questions resolve to the current month, or to the latest month that has data when
  the current month has none; a month without a year means the most recent such month with records (`resolve_period`, D-029).
  Tests that expect seed numbers must name the year ("August 2024") — the demo generator adds newer months.
- Frontend dev server: Bun (`bun dev`, port 3000). Backend: uvicorn port 8000.
- Agents start servers from a console-less shell: there `uvicorn --reload` never restarts its worker (KI-022) — run
  `uvicorn app.main:app --port 8000` without `--reload` and restart it after backend edits; kill leftover
  `multiprocessing.spawn` python children that keep port 8000 bound.

## 11. Lessons learned / common mistakes to avoid

- `PROJECT_STATUS.md` previously drifted badly (claimed frontend/reports didn't exist when they did). Always verify against code and update status in the same session as the change.
- `tests/test_rbac_matrix.py` asserted `>= 7` employees while the seed creates 6 → false failures. Match assertions to seed data.
- The old Bun proxy forwarded only `/auth`, `/chat`, `/dashboard`, `/reports`; new backend modules were unreachable from the UI. Fixed by the single `/api/*` proxy (D-003).
- Managers could approve/reject **any** leave, not only their team's — fixed; keep ownership checks when adding approval flows.
- Heredocs in Git Bash on this machine can mangle backslashes in Python regexes — write scripts with the Write tool instead.
- `bcrypt` hashing is slow by design (work factor 12); avoid hashing in loops in tests.
- **FastAPI route order matters:** static paths (`/attendance/daily`, `/attendance/records`, `/leaves/balance/me`) must be
  declared **before** catch-all `/{employee_id}` routes in the same router, or they 422.
- **MySQL REPEATABLE READ in tests:** a test's own `SessionLocal()` keeps an old snapshot; call `db.commit()` before
  re-reading rows that were written through the API (TestClient uses a different session).
- (Historical, fixed in session 2) `tests/test_seed.py` used to reset the real demo data and thereby delete uploaded
  documents and chat logs. It now seeds a namespaced copy (D-023). Running `python scripts/seed_db.py` by hand still
  resets demo data and removes documents uploaded by demo users (D-019) — re-upload `sample_documents/` afterwards.
- Don't assert that policy answers come from `policies.json` — an uploaded document may legitimately match first (D-009).
- MySQL `SUM()` returns `Decimal`; cast aggregates to `int`/`float` in services before doing arithmetic.
- `email-validator` rejects reserved TLDs like `.test`/`.example` — use e.g. `@hrtest.dev` for test accounts.
- BM25 IDF is near zero when only a few chunks are indexed; retrieval therefore also accepts chunks matching ≥ 50 % of query terms (D-004). Re-check thresholds if you change tokenisation.
- Radix `Dialog` only restores focus to a `<Trigger>`; our dialogs are state-controlled, so `components/ui/dialog.tsx` captures the opener in `onOpenAutoFocus` and restores it on close (`useRestoreFocus`). Don't capture it at mount — `DialogContent` renders while closed.
- In dark mode the legacy bridge maps Tailwind's `white` to the surface colour, so `text-white` turns dark. Use `text-brand-foreground` / `text-brand-panel-foreground`; check new views in both themes (axe-core via cdnjs works for contrast scans).
- Don't define a component inside a component's render (e.g. a row-menu `function RowMenu`) — it remounts every render and closes open menus; call a plain render function instead.
- After large file moves in `frontend/src`, restart `bun dev` — the hot-reload resolver caches missing paths (KI-005).
- The reference site is a login-walled Angular SPA; its module list/labels/roles were obtained from public JS bundles (see D-002). Don't try to log in to it.
- Session 1 had no browser automation; session 2 added `scripts/ui_qa.py` (Playwright + installed Edge) and found 9 real
  UI defects that type-check/build/HTTP tests had missed — always run it after UI work.
- Git Bash rewrites arguments that look like paths (`/employees` → `C:/Program Files/Git/employees`). Prefix with
  `MSYS_NO_PATHCONV=1` when passing URL paths to scripts.
- Printing `₹` from Python on this Windows console needs `PYTHONIOENCODING=utf-8`.
- The AI router only knows what its tool puts in the context: when a question type returns "not available", check the
  router branch builds the needed numbers (the leave-balance bug was exactly this).
- When demo data grows, hard-coded expectations like "latest payroll month = Sep 2024" break — derive them from the DB.
- List endpoints paginate with `limit`/`offset` and report the total in `X-Total-Count` (D-035) — keep returning a plain array;
  the frontend reads it with `api.getPage<T>()`.
- Starting the backend for browser QA: raise the login limit (`RATE_LIMIT_LOGIN_PER_MINUTE=1000`) or QA scripts that log in
  many times get 429s.
- `tests/test_question_bank.py` is the AI regression bank (PRD §30). When a chat question is answered wrongly, add it there
  first (failing), then fix the router. Check refusals with "LLM not called", not only with the answer text — the old router
  answered "another employee's salary" with the caller's own salary, which looked fine at a glance.
- (Session 9) In chat routing, "I"/"me" is often the **requester**, not the subject ("Can I see bruce's salary?", "show me
  the payroll") — use `router.refers_to_self`, never a bare `\b(i|me)\b` check. Names must match case-insensitively; a new
  ordinary word that lands in a name slot goes into `_NOT_A_NAME`.
- Clarifications and "employee not found" are final answers built by the router (`CLARIFICATION_PREFIX` /
  `NOT_FOUND_PREFIX` → `direct_answer`); don't write LLM instructions into those contexts.
- Every figure the LLM may quote must be written in the context in its final form (totals included) — the grounding
  post-check (`app/ai/grounding.py`) labels answers with any other number `unverified`. Mock LLM answers in tests must not
  invent numbers unless the test is about that check.
- The real provider is verified only with the manual `scripts/verify_real_llm.py` (it cleans up its `chat_logs` rows).
  Browser scripts that send chat messages must wait for the request to finish before deleting their log rows — a row that
  lands after the cleanup breaks the "DB unchanged" check.
- Before editing uncommitted work in place, note that new tests should also be run against the *old* code: Claude Code keeps
  pre-edit snapshots in `~/.claude/file-history/<session>/` (`…@v1`); copy them into a scratch tree to prove a test fails on
  the old behaviour. Never leave `.env` copies behind.
- Docker verification without touching the owner's stack: build with `docker compose build`, then run the images as another
  project (`docker compose -p hrverify -f docker-compose.yml -f <override with image: …>` with `FRONTEND_PORT`,
  `DOCKER_SUBNET`, `FRONTEND_IP` overridden), and remove it with `down -v` (only that project's volumes).
