# CHANGELOG

All meaningful changes, newest first. Keep entries concise; link decisions (D-xxx) and issues (KI-xxx).

## 2026-10-05 (session 2)

### Added
- **Payroll engine** — `salary_service.calculate_payroll` / `generate_payroll`, `POST /salary/generate` (HR/Admin),
  "Generate payroll" dialog on the Payroll page, `employees.monthly_gross_salary` (migration `e5f6a7b8c9d0`, backfilled;
  editable on the employee form, visible only to HR/Admin/self) (D-021).
- `scripts/generate_demo_month.py` — idempotent current-month demo attendance + leaves (D-024); run for 2026-09 and 2026-10.
- `scripts/ui_qa.py` — Playwright browser QA harness using the installed Edge; `requirements-dev.txt` (D-020).
- `scripts/db_snapshot.py` — DB/document-folder fingerprint: `save`, `diff`, `isolate` (D-023).
- `tests/helpers.py` (`TrackingClient`), `tests/test_payroll.py` (36 checks, hand-checked ₹64,728 example).
- `attendance_service.COMPANY_HOLIDAYS`, `is_working_day`, `working_days_between` (shared by payroll + demo generator).
- `retriever.search(..., document_ids=)` optional scoping.
- Leave approvals notice explaining that your own requests are reviewed by someone else (D-022).

### Changed
- Tests no longer modify the dev DB: `test_seed.py` seeds a namespaced copy (`TS-EMP*`); chat-calling tests delete exactly
  their own `chat_logs`; RAG ranking checks scoped to test documents. Full run verified byte-identical (D-023).
- Overtime report OT Amount = per-record minutes × that month's OT rate (pro-rated; KI-015).
- AI chat LEAVE tool now includes the Python-calculated leave balance (year from the question, else current year) and
  working-day lengths (KI-020).
- Navbar: hamburger < 1280 px, text-only 1280–1535 px, icons + name ≥ 1536 px, scroll arrows on overflow (D-025).
- `GET /employees/me` returns the detail schema (manager name, email, role, own salary structure).
- `PUT /employees/{id}` ignores `null` for NOT NULL fields (only `manager_id` can be cleared).
- `scripts/seed_db.py` sets `monthly_gross_salary` from the latest seeded salary.

### Fixed
- Chat "What is my leave balance?" answered "not available in the provided context".
- Phone (390 px) pages widened to 800–1200 px: `sr-only` header labels escaped table scroll containers.
- Admin menu items hidden off-screen at 1400 px with no cue.
- Employee profile name drawn over the navy banner; My Profile showed "Reporting manager #<id>".
- Employee form: missing required-field validation (department, designation, joining date).
- Own-row "Deactivate" button for HR/Admin; truncated stat-card labels on phones; leave-balance year label.

### Notes
- Task 1 sanity check: no file imports the removed `app/rag/retrievers.py`; retrieval is served by `app/rag/retriever.py`
  (router + tests); every `app.*` module imports cleanly. No dangling imports were found.
- KI-005 root cause found (Bun alias resolver cache for new files) — restart `bun dev` after adding files.
- KI-022: `uvicorn --reload` launched from an agent's console-less shell never restarts its worker; start without
  `--reload` in that situation.
- Product owner decision: keep the self-approval block for HR/Admin too (D-022).
- Tests: 34 files, 692 checks, 0 failures; dev DB unchanged by the run. Still uncommitted (by instruction).

## 2026-10-05

### Added
- Persistent project memory: `AGENTS.md`, `DEVELOPMENT_PLAN.md`, `PROJECT_DECISIONS.md`, `KNOWN_ISSUES.md`, `CHANGELOG.md`; rewrote `README.md` and `PROJECT_STATUS.md`.
- **Frontend rebuilt as an HRMS** modelled on hrms.nectorinternational.com (D-002): sticky top navbar with role-filtered menu,
  History-API router, auth context, API client, toast/modal/table/chart components and 13 pages — Login, Dashboard
  (role-aware), Employees, Employee form, Employee detail / My Profile, Departments, Attendance, Leave, Payroll, Documents,
  Reports, AI Assistant, Settings. `recharts` dependency.
- Backend endpoints: `GET /auth/me`; `POST/PUT/DELETE /employees` + filters; `GET /departments`; `GET /attendance/today`,
  `POST /attendance/check-in`, `POST /attendance/check-out`, `GET /attendance/daily`, `GET /attendance/records`;
  `GET /leaves`, `GET /leaves/balance/me`, `POST /leaves/{id}/cancel`; `GET /salary` (payroll register);
  `POST /documents/upload`, `GET /documents`, `GET /documents/{id}/download`, `POST /documents/{id}/reindex`,
  `DELETE /documents/{id}`; `GET /chat/history`, `GET /chat/logs`; `GET /dashboard/me`; `GET /reports/leave`;
  `GET/PATCH /users`.
- RAG pipeline (`app/rag/document_loader.py`, `chunker.py`, `embeddings.py`, `retriever.py`) + `app/services/document_service.py`;
  migration `d4e5f6a7b8c9` (`document_chunks` table, `documents.error_message`) (D-004, D-017).
- Prompt-injection guardrail `detect_prompt_injection` (D-011).
- Attendance calculation engine helpers `calculate_day_metrics` / `calculate_late_minutes` (D-007); leave
  `count_leave_days` / `get_leave_balance` (D-008); dashboard `monthly_attendance` trend.
- Reports: Summary sheets with PRD §22 columns, `month`/`year`/`department` filters (D-013).
- Google OAuth `?next=frontend` → redirect to `FRONTEND_URL/login#token=` (D-014).
- `scripts/run_tests.py` canonical test runner; `tests/test_hrms_endpoints.py` (86 checks), `tests/test_rag.py` (38 checks).
- `sample_documents/` demo policies for RAG demos.

### Changed
- `POST /chat` accepts `message` (PRD) or `question`; returns `source`, `confidence`, `page`, `sources[]`; POLICY uses RAG
  first with `policies.json` fallback; UNKNOWN intent tries RAG (D-009, D-012). LLM failure wording per PRD §29 (D-015).
- `GET /employees` now allowed for managers (team only); `GET /employees/{id}` allows self/team (D-010).
- Bun server: single `/api/*` proxy instead of 4 hard-coded prefixes (D-003).
- `requirements.txt` rewritten as UTF-8; added `pypdf`, `python-multipart`, `pytest`.
- `scripts/seed_db.py` reset also removes documents uploaded by demo users (D-019).
- `.env.example`: `BACKEND_URL`, `FRONTEND_URL`, `DOCUMENTS_DIR`. `.gitignore`: `documents/`.
- Tests updated for new rules: `test_rbac_matrix.py`, `test_leaves_patch.py`, `test_chat_api.py`.

### Fixed
- Managers could approve/reject any employee's leave; now team-only and nobody can approve their own leave.
- `get_attendance_summary` returned `Decimal` values.
- `test_rbac_matrix.py` false failures (expected ≥ 7 employees; seed has 6).

### Removed
- Empty misnamed `app/rag/retrievers.py` (replaced by `retriever.py`).
- Old frontend files `APITester.tsx`, `LoginView.tsx`, `DashboardView.tsx`, `ChatView.tsx`, `react.svg`.

### Notes
- UI not yet visually verified in a browser (KI-016). Demo data is Aug–Sep 2024 (KI-001).
- Work is uncommitted; commit when the product owner asks.

## ≤ 2026-09-28 (before persistent changelog)
- Initial backend: models + Alembic migrations, bcrypt/JWT auth, RBAC, employees/leaves/attendance/salary APIs and
  services, seed data, rule-based AI chat MVP, dashboard summary, attendance & overtime Excel reports, Google OAuth,
  first React frontend. See git history (`git log`).
