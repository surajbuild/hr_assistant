# AI HR Assistant — HRMS with an AI chat assistant

> **New here (human or AI agent)?** Read [`AGENTS.md`](AGENTS.md) first — it is the mandatory development policy.
> Then [`PROJECT_STATUS.md`](PROJECT_STATUS.md), [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md),
> [`PROJECT_DECISIONS.md`](PROJECT_DECISIONS.md), [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md), [`CHANGELOG.md`](CHANGELOG.md).
> Product requirements: [`prd_extracted.md`](prd_extracted.md).

## 1. What the product is

An HR management web app (employees, departments, attendance, leave, payroll, documents, reports) whose headline feature
is an **AI HR Assistant**: users ask questions in plain English — *"How many days was Aman present in August?"*,
*"Who worked the most overtime this month?"*, *"What is the leave policy?"* — and get answers that are

- computed from **MySQL** by Python service functions (the LLM never touches the database or does the maths),
- or retrieved from **uploaded HR documents** (PDF/DOCX/TXT) via RAG, **with the source document cited**,
- filtered by **role-based permissions** (an employee can never see a colleague's salary, even via the chat),
- protected against **prompt injection**, and **logged** for audit.

The module layout and roles follow the reference HRMS `https://hrms.nectorinternational.com/` (D-002); the visual design is
a modern SaaS dashboard (indigo accent, collapsible sidebar, light/dark mode, ⌘K command palette) — see
[`frontend/DESIGN.md`](frontend/DESIGN.md) and `PROJECT_DECISIONS.md` D-026. *(The redesign is rolling out in two parts; progress:
`frontend/REDESIGN_NOTES.md`.)*

## 2. Technology

| Layer | Stack |
|---|---|
| Backend | Python 3.14 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · PyMySQL |
| Database | MySQL 8 (`ai_hr_assistant`) |
| Auth | Email + password (bcrypt) and Google OAuth 2.0 (Authlib) → JWT (PyJWT, HS256) · RBAC |
| AI | OpenAI-compatible Chat Completions API (configured for OpenRouter `openai/gpt-4o-mini`) |
| RAG | pypdf / python-docx / txt → cleaning + chunking → sparse term vectors → BM25 retrieval (stored in MySQL) |
| Reports | openpyxl (.xlsx) |
| Frontend | Bun 1.4 · React 19 · TypeScript · Tailwind CSS v4 · shadcn-style components on Radix primitives · lucide-react · recharts |
| Tests | Standalone Python test scripts (FastAPI TestClient) against the dev DB · `scripts/run_tests.py` |

## 3. How it works

```
Browser (React SPA, :3000)
   │  /api/*  (Bun proxy strips /api)
   ▼
FastAPI (:8000) ── JWT auth (get_current_user) ── RBAC (require_role + employee_service.get_scope_employee_ids)
   │
   ├── REST routers  app/api/*         → services app/services/*  → SQLAlchemy models → MySQL
   │
   └── POST /chat    app/api/chat.py
         1. sanitize + prompt-injection guardrail (app/ai/guardrails.py)   → refuse, log
         2. intent router (app/ai/router.py: EMPLOYEE / ATTENDANCE / LEAVE / SALARY / POLICY / GENERAL / UNKNOWN)
         3a. data intents  → controlled service calls + RBAC check (check_rbac_access) → verified context
             (profiles, directory, department headcount, attendance summaries, overtime/late/absence rankings,
              leave balances, payslips, payroll summary; periods like "this month" / "September" resolved per D-029)
         3b. POLICY/UNKNOWN → RAG search over uploaded docs (app/rag/retriever.py) → fallback app/data/policies.json
         4. LLM (app/ai/llm.py) phrases the verified context, with anti-hallucination prompt (app/ai/prompts.py)
         5. chat_logs row (user, question, intent, source, answer, latency, error)
         6. {answer, intent, source, confidence, page, sources[]}
```

Document upload: `POST /documents/upload` → validate (pdf/docx/txt, ≤10 MB) → store in `documents/` with a random
name → parse (page-aware for PDFs) → clean → chunk (~900 chars, 150 overlap) → term vectors → `document_chunks` →
status `active` (or `failed` with the reason). Re-uploading the same name creates a new version and archives the old one.

## 4. Running it locally

### Prerequisites
- Python 3.12+ (developed on 3.14), MySQL 8 running locally, Bun ≥ 1.4.
- An LLM API key for an OpenAI-compatible endpoint (OpenRouter/OpenAI).

### First-time setup
```powershell
cd D:\CODING\PROJECTS\hr_assistant
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # then edit DATABASE_URL, JWT_SECRET_KEY (≥32 chars), LLM_API_KEY, ...
# In MySQL:  CREATE DATABASE ai_hr_assistant;
alembic upgrade head            # creates/updates all tables
python scripts/seed_db.py       # demo employees, attendance (Aug–Sep 2024), leaves, salaries
python scripts/generate_demo_month.py   # realistic attendance + leaves for the CURRENT month (idempotent)
cd frontend
bun install
```

### Every day — two terminals
```powershell
# Terminal 1 — backend (http://localhost:8000, API docs at /docs)
cd D:\CODING\PROJECTS\hr_assistant
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (http://localhost:3000)
cd D:\CODING\PROJECTS\hr_assistant\frontend
bun dev
```
Set `PORT=3001` before `bun dev` to use another port (then set `FRONTEND_URL` accordingly for Google login).

Dev-server notes:
- **Restart `bun dev` after adding a new frontend file** — Bun's dev server can't resolve brand-new files imported via
  `@/…` until it restarts and shows "Build Failed — Could not resolve" (KNOWN_ISSUES KI-005).
- If you (or an agent) start uvicorn from a background/console-less shell, run it **without `--reload`** and restart it
  after backend edits (KI-022). From a normal terminal `--reload` works.

### Demo data for the current month
The seed data is from 2024. To make the dashboard, daily sheet and "this month" questions show live numbers:
```powershell
python scripts/generate_demo_month.py              # current month up to today (safe to re-run; skips existing rows)
python scripts/generate_demo_month.py --month 2026-09   # back-fill a whole past month
python scripts/generate_demo_month.py --dry-run    # preview counts
```
It creates attendance for every active employee (weekends/holidays, ~12 % late, ~4 % half days, some overtime, a few
absences, today = checked in) plus a handful of leave requests in mixed statuses. Then, as HR, open **Payroll → Generate
payroll** for the previous month to create payslips from that attendance.

### Demo accounts (created by `scripts/seed_db.py`, password `Demo@12345`)

| Email | Role | Employee |
|---|---|---|
| admin@company.com | admin | Vikram Sharma (EMP001) |
| neha.hr@company.com | hr | Neha Verma (EMP002) |
| priya.mgr@company.com | manager | Priya Nair (EMP003) — manages Aman & Rahul |
| aman@company.com | employee | Aman Gupta (EMP004) — 22/24 days present in Aug 2024, 4 late |
| rahul@company.com | employee | Rahul Sharma (EMP005) — 18 h 35 m overtime in Sep 2024 |
| sneha@company.com | employee | Sneha Patel (EMP006) |

Upload the files in `sample_documents/` as HR on the Documents page to demo policy Q&A (e.g. *"How many days can I work from home?"*).

### PRD demo script (§35)
1. Log in as **aman** → AI Assistant → *"What is my attendance this month?"* (current month after
   `generate_demo_month.py`; otherwise the latest month with data, and the answer says so) — or the fixed seed question
   *"How many days was I present in August 2024?"* → 22 days (attendance_database).
2. *"What is another employee's salary?"* or *"What is Rahul's salary?"* → access denied.
3. *"What is the leave policy?"* → answer + source.
4. Log in as **neha.hr** → *"Who worked the most overtime this month?"* (ranking computed in Python), or with seed data
   *"Who worked the most overtime in September 2024?"* → Rahul, 18 h 35 m.
5. Documents → upload `sample_documents/Work From Home Policy.txt` → ask *"How many days can I work from home in a month?"* → 8 days, source "Work From Home Policy.txt".
6. (Extra) As **neha.hr**: Payroll → pick last month → **Generate payroll** → LOP / PF / overtime computed from attendance.

## 5. Project structure

```
app/
  main.py                FastAPI app, middleware, router registration
  api/                   HTTP layer (schemas, auth dependencies, status codes)
    auth.py              /auth/login, /auth/me, /auth/google/*
    employees.py         /employees CRUD (+ manager team scope)
    departments.py       /departments (derived stats)
    attendance.py        /attendance me|summary|today|check-in|check-out|daily|records|{employee_id}
    leaves.py            /leaves apply|me|balance/me|list|{id}/status|{id}/cancel|{employee_id}
    salary.py            /salary me|list|summary|{employee_id}
    documents.py         /documents upload|list|download|reindex|archive
    chat.py              /chat, /chat/history, /chat/logs
    dashboard.py         /dashboard/summary, /dashboard/me
    reports.py           /reports/attendance|overtime|leave (.xlsx)
    users.py             /users (admin)
  services/              Business logic & calculations (framework-free; reused by the AI)
  ai/                    router.py (intent + controlled retrieval), guardrails.py, prompts.py, llm.py
  rag/                   document_loader.py, chunker.py, embeddings.py, retriever.py
  database/              connection.py, models.py, queries.py
  utils/                 security.py (bcrypt/JWT), dependencies.py (auth/RBAC), oauth.py
  data/                  seed_data.json, policies.json (built-in policy fallback)
alembic/                 migrations (head: e5f6a7b8c9d0 — employees.monthly_gross_salary)
frontend/
  src/index.ts           Bun server: /api/* proxy + SPA
  src/App.tsx            providers, routes, role guards
  src/lib/               api.ts, auth.tsx, router.tsx, types.ts, nav.ts, format.ts, useFetch.ts
  src/components/        ui/ primitives (Radix), layout/ (sidebar shell, ⌘K palette, bell), tables, badges, dialogs, charts, payslip, markdown
  src/pages/             Login, Dashboard, Employees, EmployeeForm, EmployeeDetail, Departments, Attendance,
                         Leave, Payroll, Documents, Reports, Chat, Settings
  styles/globals.css     design tokens (light + dark), status colours, motion
  DESIGN.md              design system v2 (tokens, components, patterns)  ·  REDESIGN_NOTES.md  redesign working notes
scripts/
  seed_db.py             demo data (2024) — resets demo employees/users when run
  generate_demo_month.py current-month demo attendance + leaves (idempotent)
  run_tests.py           canonical test runner
  db_snapshot.py         prove tests leave the DB unchanged (save / diff / isolate)
  ui_qa.py               browser QA harness (Playwright + installed Edge; requirements-dev.txt)
  smoke_test_chat.py     manual chat smoke test
sample_documents/        demo HR policies for RAG
tests/                   standalone test scripts (see §9); helpers.py = TrackingClient for /chat tests
documents/               uploaded files (git-ignored)
```

## 6. Major features

| Module | What it does |
|---|---|
| Dashboard | Four role-specific layouts. HR/Admin: KPIs (employees, present, absent, on leave, late, overtime), attendance by department, monthly trend, overtime & late leaders, leave usage, recent leaves. Employee/Manager: today's check-in/out, month stats, leave balance, latest payslip, team snapshot (managers). |
| Employees | Directory with search/filters, add/edit (optionally creating a login; monthly gross salary for payroll), deactivate (soft delete), detail page with attendance/leave/salary tabs. |
| Departments | Cards with headcount, active count, designations, managers. |
| Attendance | Self check-in/out (late after 9:15, OT beyond 8 h worked), my history + monthly summary, daily sheet and record search for HR/managers, HR "mark attendance". |
| Leave | Apply, balance (casual 12 / sick 10 / earned 15 working days per year), cancel pending, approvals (HR any, manager team only, never self). |
| Payroll | HR/Admin monthly payroll register + totals and **Generate payroll** (payroll engine: loss of pay for absences / half days / unpaid leave, PF 12 % of earned basic, overtime at 1.5× — PROJECT_DECISIONS D-021); employees see their payslips (printable). |
| Documents | HR/Admin upload PDF/DOCX/TXT → indexed for the AI; versioning; archive; everyone can list/download. |
| Reports | Attendance, Overtime, Leave Excel exports by month/year/department (PRD §22 summary columns). |
| AI Assistant | Natural-language Q&A over HR data + documents with intent, source and confidence chips; history. |
| Settings (admin) | Users & roles (change role, activate/deactivate), AI chat audit log, policy reference. |

## 7. Roles and permissions

| Capability | employee | manager | hr | admin |
|---|:-:|:-:|:-:|:-:|
| Own profile / attendance / leave / payslips | ✅ | ✅ | ✅ | ✅ |
| Check-in / check-out, apply & cancel leave | ✅ | ✅ | ✅ | ✅ |
| Employee directory, daily attendance, leave list | — | team | all | all |
| Approve/reject leave | — | team (not own) | all (not own) | all (not own) — nobody approves their own leave (D-022) |
| Create/edit/deactivate employees | — | — | ✅ (no admin accounts) | ✅ |
| Payroll register, generate payroll, other employees' salary / salary structure | — | — | ✅ | ✅ |
| Upload/archive documents | — | — | ✅ | ✅ |
| Excel reports | — | — | ✅ | ✅ |
| Users & roles, chat audit log | — | — | — | ✅ |
| AI chat | own data + policies | + team attendance/leave (no team salary) | HR data | everything |

"Team" = the manager plus employees whose `manager_id` is the manager. Enforced in the backend
(`employee_service.get_scope_employee_ids`, `require_role`, `guardrails.check_rbac_access`); the UI only hides what you can't use.

## 8. Environment variables (`.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://user:pass@localhost:3306/ai_hr_assistant` |
| `JWT_SECRET_KEY` | HS256 signing key — **≥ 32 bytes** |
| `JWT_ALGORITHM` / `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `HS256` / `60` |
| `SESSION_SECRET_KEY` | Cookie session for OAuth state |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Google OAuth (redirect `http://localhost:8000/auth/google/callback`) |
| `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` | OpenAI-compatible LLM endpoint |
| `BACKEND_URL` | Where the Bun server proxies `/api/*` (default `http://localhost:8000`) |
| `FRONTEND_URL` | Where Google login returns with `#token=` (default `http://localhost:3000`) |
| `DOCUMENTS_DIR` | Optional storage dir for uploads (default `./documents`) |

## 9. Testing

```powershell
.venv\Scripts\activate
python scripts/run_tests.py            # all 35 test files (769 checks, ~2 min)
python scripts/run_tests.py rag hrms   # subset by filename
python tests/test_rag.py               # one file
```
Tests hit the **dev MySQL database** from `.env` and expect seed data, but they **leave it byte-identical**: every test
creates its own marked rows and removes them (PROJECT_DECISIONS D-023). Prove it with:
```powershell
python scripts/db_snapshot.py save before.json
python scripts/run_tests.py
python scripts/db_snapshot.py diff before.json     # -> "Database unchanged"
python scripts/db_snapshot.py isolate              # which test file (if any) changes the DB
```
The LLM is always mocked.
Key suites: `test_question_bank.py` (**PRD §30 question bank**: 22 normal / 11 incorrect / 13 security / 13 calculation
questions + 11 RAG checks through `POST /chat`, expected numbers computed from MySQL in the test),
`test_hrms_endpoints.py` (HRMS APIs, 88 checks), `test_payroll.py` (payroll engine, 36), `test_rag.py` (RAG + guardrails, 38),
`test_rbac_matrix.py` (permissions, 77), `test_chat_api.py`, `test_ai_router.py`, `test_reports_api.py`.

Frontend: `cd frontend && bunx tsc --noEmit -p . && bun run build`.

Browser QA (both servers running, Microsoft Edge installed):
```powershell
pip install -r requirements-dev.txt     # playwright (uses the installed Edge, no browser download)
python scripts/ui_qa.py                 # 4 roles × 1440/1024/390 px × all pages -> screenshots + "0 issue(s)"
python scripts/ui_qa.py --roles admin --widths 1280 --out qa_shots
```

## 10. API overview

Full interactive docs: http://localhost:8000/docs. The frontend calls everything under `/api`.
The complete contract table (method, path, roles, notes) is in `DEVELOPMENT_PLAN.md` → "API contract".

## 11. Google OAuth setup (optional)

1. Google Cloud Console → create project → OAuth consent screen (External; scopes `openid email profile`; add test users).
2. Credentials → OAuth client ID → Web application. Authorized JavaScript origin `http://localhost:8000`;
   redirect URI `http://localhost:8000/auth/google/callback`.
3. Put the client ID/secret in `.env`. The login page's "Sign in with Google" goes to
   `/auth/google/login?next=frontend` and returns to `FRONTEND_URL/login#token=…`.

## 12. Current status, known issues, remaining work

- Status per feature: [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
- Known problems + workarounds: [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) — notably: run `generate_demo_month.py` each month
  for live demo data, restart `bun dev` after adding files, lexical (not semantic) RAG, short JWT secret in `.env`,
  no separate test database (tests are isolated by design instead).
- Roadmap: [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md)
