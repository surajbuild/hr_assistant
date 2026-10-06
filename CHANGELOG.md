# CHANGELOG

All meaningful changes, newest first. Keep entries concise; link decisions (D-xxx) and issues (KI-xxx).

## 2026-10-06 (session 5 — hardening, corrections, holidays, payroll, pagination, Docker, docs, redesign Part 2)

### Added
- **Attendance corrections** (D-033): employees request in/out times for a past day; the manager (team only) or HR/Admin
  approves or rejects — never their own; HR/Admin edit records directly (`PUT /attendance/records/{id}`, not their own).
  Table `attendance_corrections`, `correction_service.py`, Attendance → Corrections tab.
- **Holiday calendar** (D-034): HR-declared company holidays (`holidays` table, `GET/POST/DELETE /holidays`) on top of the
  national ones; excluded from payroll working days, leave-day counts and the OT rate; Leave → Holidays tab; chat answers.
- **Mark as paid** (D-036): `POST /salary/mark-paid`, irreversible; a paid month locks payroll regeneration and attendance edits.
- **Pagination** (D-035): `limit`/`offset` + `X-Total-Count` on `/employees`, `/attendance/records`, `/chat/logs` (+ `search`);
  `api.getPage<T>()` in the frontend.
- **Rate limiting** (D-031): `/auth/login` per IP and per (IP, email) failures, `/chat` per user → 429 + `Retry-After`.
- **Docker**: `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `docker/` (image build not yet run, see status).
- **PRD §33 docs**: `docs/ARCHITECTURE.md`, `docs/AI.md`, `docs/API.md`.
- Migration `f6a7b8c9d0e1` (holidays + attendance_corrections); tests `test_holidays_corrections.py`,
  `test_security_hardening.py`; question bank C14–C18, D14.
- Token `--status-present-solid` for filled success buttons (D-040).

### Changed
- **Secrets** (D-031): `JWT_SECRET_KEY` / `SESSION_SECRET_KEY` must be ≥ 32 bytes and not placeholders, else the app won't
  start; the hard-coded session-secret fallback is gone; dev secrets rotated.
- Chat: managers get team-scoped rankings (D-032); profile lookups follow `GET /employees/{id}` — employees can no longer read
  other people's profiles through chat (D-039); `POST /attendance` refuses the caller's own employee id.
- Google sign-in starts through the `/api` proxy (works in Docker).
- **Redesign Part 2** (D-037): Employee form, Employee profile, Departments, Attendance, Leave, Payroll, Documents, Reports,
  AI Assistant, Settings rebuilt on design system v2 (`pages/attendance|chat|leave|payroll|people|settings/*`).

### Removed
- The dark-mode legacy bridge and legacy colour aliases from `globals.css` (D-028 completed, D-040).

### Fixed
- KI-003, KI-011 (secrets), KI-012 (attendance corrections), KI-029 (manager rankings), KI-027 (redesign), KI-028
  (pagination verified in the browser).
- Light-mode contrast of the success button (Approve / check-in): 3.76:1 → AA.

### Notes
- Product-owner decisions this session: D-032, D-033, D-037, D-038 (unrecorded days stay paid), D-039.
- A power cut interrupted the session's last steps; they were completed afterwards (bridge removal, contrast fix, quality pass,
  handoff docs). Verification: 37 files / 882 checks / 0 failed, DB unchanged; `ui_qa.py` 0 issues; axe 0 violations in light
  and dark on 22 page views; `tsc` + build clean.

## 2026-10-06 (session 4 — PRD §30 question bank + AI router fixes)

### Added
- `tests/test_question_bank.py` — the PRD §30 question bank through `POST /chat`: 22 normal, 11 incorrect, 13 security,
  13 calculation questions (expected numbers computed from MySQL in the test) and 11 RAG checks (a real 2-page PDF with
  page citation, DOCX, TXT, archive, new version). Covers every PRD §35 demo question.
- Chat tools (D-030): rankings for overtime / late arrivals / absences (`attendance_service.rank_employees`), department
  headcount (scoped like `GET /departments`), company payroll summary for "all salaries" / "payroll for 2024".
- `attendance_service.get_months_with_data`, `salary_service.get_payroll_periods`.

### Changed
- Period handling in the AI router (D-029, KI-008): "this month" (falls back to the latest month with data, with a note),
  "last month", and a month without a year means the most recent such month with records — no more hard-coded 2024.
  `extract_month_and_year` returns `year=None` when no year is written; "May I…" is no longer the month of May.
- Attendance answers include half days and leave days; a person/period with no records now says
  "Attendance data is not available for the requested period" (PRD §29) instead of listing zeros.
- `app/ai/router.py` no longer runs its own queries (the overtime ranking and employee lookup moved to services, AGENTS.md §2.2).
- Tests and `scripts/smoke_test_chat.py` that expect seed numbers now name the year ("August 2024").

### Fixed
- R-019: HR "What is the total payroll for September 2024?" crashed `/chat` with a 500 (wrong summary keys).
- R-020: "What is another employee's salary?" (PRD demo 2) and "Show all salaries" returned the caller's own salary
  instead of a refusal.
- R-021: "What is my attendance this month?" / "Who worked the most overtime this month?" (PRD demos 1, 4) used all-time data.
- R-022: "Who was late the most?", "How many employees are in Engineering?", "Show all employee personal information"
  were not understood (UNKNOWN).

### Notes
- No permission rule changed; rankings stay HR/Admin only (manager team rankings = owner question, KI-029).
- Verification: `scripts/run_tests.py` 35 files / 769 checks / 0 failed; `db_snapshot.py diff` → "Database unchanged".
  The new bank fails 20 checks against the previous router.

## 2026-10-05 (session 3 — frontend redesign, Part 1 of 2)

### Added
- **Design system v2** (`frontend/DESIGN.md`, D-026): token layer in `styles/globals.css` (light + dark), indigo accent, fixed
  per-status colours, flat cards, motion utilities honouring `prefers-reduced-motion`.
- **Dark mode**: Light/Dark/System toggle (top bar + Login), persisted (`hr_theme`), applied before first paint.
- **App shell**: collapsible left sidebar (rail on tablet, drawer on phones), slim top bar with breadcrumb, **⌘/Ctrl+K command
  palette** (pages, actions, employee search for staff), notification bell for approver roles (pending leave requests), profile menu.
- Radix primitives + new UI components: Dialog/Drawer, DropdownMenu, Tooltip, Popover, Switch, Badge, Skeleton, Separator,
  Segmented, DataTable sorting/pagination/mobile cards, StatCard (count-up, delta, sparkline), RingProgress, Donut, Sparkline,
  AttendanceHeatmap (D-027).
- **Login** (split screen, inline validation, show/hide password, demo chips), **Dashboard** (four role-specific layouts built from
  existing endpoints), **Employees** (table ⇄ card view, status segmented filter, sort, pagination, row menu, mobile cards).
- `frontend/DESIGN.md`, `frontend/REDESIGN_NOTES.md`; decisions D-026/D-027/D-028.

### Changed
- `AGENTS.md` §7 rewritten for the new design; D-002's visual/navigation part and D-025 superseded.
- `Modal`/`ConfirmDialog` rebuilt on Radix Dialog (same API): focus trap, Escape, focus restored to the opener, bottom sheet on phones.
- Shared components restyled to tokens (States with skeletons, StatusBadge, Tabs with arrow-key navigation, Toast, Field, charts,
  LeaveBalanceGrid rings, TodayAttendanceCard hero). All 13 pages now render inside the new shell.
- `scripts/ui_qa.py` asserts the sidebar/rail/drawer shell at 1440/1024/390 instead of the old top navbar.

### Fixed
- KI-018: table rows with a click action are now keyboard-focusable and activatable.

### Notes
- Backend untouched; no API/contract/auth/role changes. Verification: `tsc` + `bun run build` clean; `ui_qa.py` 0 issues
  (4 roles × 3 widths × 14 routes); 56 scripted behaviour checks; axe-core WCAG 2.1 AA clean on Login/Dashboard/Employees in
  light + dark. Awaiting owner approval before Part 2 (remaining 10 pages).

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
