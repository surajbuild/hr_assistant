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

**AI HR Assistant** — an HRMS-style web application (modelled on the look and module layout of
`https://hrms.nectorinternational.com/`) whose distinguishing feature is an **AI chat assistant** that answers
natural-language HR questions from MySQL data (controlled tools) and from uploaded HR documents (RAG), while
enforcing role-based permissions. The PRD (`prd_extracted.md`) is the product requirement; the reference site is the
**UI/UX and module-layout reference only** (see `PROJECT_DECISIONS.md` D-002).

- Backend: Python 3 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · MySQL (PyMySQL) · JWT (PyJWT) · bcrypt · Authlib (Google OAuth) · openpyxl
- Frontend: Bun · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui-style components · lucide-react icons (`frontend/`)
- AI: OpenAI-compatible Chat Completions API (currently OpenRouter) via `app/ai/llm.py`; rule-based intent router `app/ai/router.py`
- RAG: local document parsing (pypdf / python-docx / txt) → chunking → TF-IDF vectors (pure Python) stored in MySQL → cosine similarity retrieval (`app/rag/`)

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
8. JWT secret must be ≥ 32 bytes in any shared environment.

## 4. Database rules

- MySQL is the system of record. Connection string comes from `DATABASE_URL` in `.env`.
- Tables: `employees`, `users`, `attendance`, `leaves`, `salary`, `documents`, `document_chunks`, `chat_logs` (+ `alembic_version`).
- `employees.monthly_gross_salary` is **confidential** (D-021): serialize it only for HR/Admin or the employee themself
  (`employee_service.serialize_employee(..., include_salary=employee_service.can_view_salary(user, emp_id))`).
- Enum-like columns are stored as **lowercase strings** (see enums in `app/database/models.py`). Keep using the enum `.value`s.
- Departments are **derived** from `employees.department` (no departments table) — see D-005.
- Deleting an employee is a **soft delete** (status → `inactive`, linked user → `inactive`) so attendance/salary history is preserved — see D-006.
- Demo/seed data: `python scripts/seed_db.py` (data in `app/data/seed_data.json`). The seed dataset covers **Aug–Sep 2024**.
  Current-month demo data: `python scripts/generate_demo_month.py` (idempotent, D-024) — run it each new month you demo.
  The dashboard falls back to the latest date that has attendance when today has none.
- Payroll rules (LOP, PF, OT pay) live as constants at the top of `app/services/salary_service.py` (D-021); the company
  holiday calendar is `attendance_service.COMPANY_HOLIDAYS`. Never duplicate these numbers elsewhere.

## 5. Testing rules

- Tests live in `tests/` and are **standalone scripts** that run against the **dev MySQL database configured in `.env`**.
  Run one with `python tests/test_xxx.py` or all with `python scripts/run_tests.py`. They print `[PASS]/[FAIL]` and exit
  non-zero on failure.
- **A test run must leave the dev database byte-identical (D-023).** Rules:
  - Create your own rows with unique markers (codes `T-<AREA>-*`, emails `@hrtest.dev`, document names `RAGTEST*`) and
    delete them in `finally`. Never modify or delete seeded/demo rows you did not create.
  - Any test that calls `POST /chat` must use `tests/helpers.TrackingClient(app, db)` and call
    `client.cleanup_chat_logs()` in `finally` (`/chat` always writes a `chat_logs` row).
  - Assertions must not depend on how much demo data exists (derive expectations from the DB, compare deltas, or
    scope queries, e.g. `retriever.search(..., document_ids=own_ids)`).
  - Verify before handing off: `python scripts/db_snapshot.py save before.json` → `python scripts/run_tests.py` →
    `python scripts/db_snapshot.py diff before.json` must print "Database unchanged". `python scripts/db_snapshot.py isolate`
    names the offending test file.
- `pytest` can also collect them, but the canonical runner is `scripts/run_tests.py`.
- Tests that depend on seed data assume `scripts/seed_db.py` has been run. Do not hard-code employee counts higher than the seed provides (6 employees).
- UI changes: run the browser QA harness `python scripts/ui_qa.py` (needs `pip install -r requirements-dev.txt`, both
  servers running, Microsoft Edge installed) — it must report `0 issue(s)`; then look at the screenshots it writes.
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

## 7. UI/UX rules (reference: hrms.nectorinternational.com)

- Layout: **sticky white top navbar (52px)** with brand at left, horizontally scrollable icon+label nav links in the
  middle, notification/profile menu at right. **No left sidebar.** Content area on `#f1f5f9` background, max width ~1400px, 24px padding.
- Palette (CSS variables in `frontend/styles/globals.css`): primary navy `#1e3a5f`, accent blue `#2563eb`,
  success `#059669`, warning `#d97706`, danger `#dc2626`, text `#0f172a` / `#64748b`, border `#e2e8f0`, cards white.
- Font: Inter.
- Menu items are filtered by role (the same role sets the backend enforces). Order:
  Dashboard · My Profile (employee) · Employees · Departments · Attendance · Leave · Payroll · Documents · Reports · AI Assistant · Settings (admin).
- Status badges: colored pills (present=green, absent=red, late=amber, half day=blue, leave=purple, holiday/weekend=gray).
- Every data view needs: loading state, empty state, error state.
- Dashboard greeting is role-specific ("Welcome, Admin! Full system overview." / "Welcome, HR! …" / "Welcome, Manager! Team overview." / "Welcome back, <name>!").
- Must be usable at phone width (390 px): no horizontal page scroll; tables scroll **inside** their card (scroll
  containers need `relative` so `sr-only`/absolute children can't widen the page).
- Navbar density (D-025): hamburger menu below 1280 px; 1280–1535 px text-only links; ≥ 1536 px icons + user name;
  scroll arrows when the row overflows. Adding a menu item? Re-run `scripts/ui_qa.py` at 1280 and 1400 px.
- Never show an action the backend will refuse for this user (e.g. approving your own leave, deactivating yourself) —
  hide it and, where the reason isn't obvious, explain it with a `Notice`.

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
- Must NOT allow anyone (including HR/Admin) to approve their own leave (D-022, confirmed by the product owner).
- Must NOT expose `monthly_gross_salary` or another person's salary to managers or employees.

## 10. Known constraints

- Windows dev machine; shell is PowerShell / Git Bash. `requirements.txt` was historically UTF-16 — keep it **UTF-8**.
- The LLM provider is OpenRouter (`LLM_BASE_URL=https://openrouter.ai/api/v1`, `LLM_MODEL=openai/gpt-4o-mini`). OpenRouter
  does not reliably offer an embeddings endpoint, which is why RAG uses local TF-IDF (D-004).
- Seed data is from 2024; "this month" questions for the demo resolve to the latest month that has data (see router).
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
