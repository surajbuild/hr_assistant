# PROJECT_STATUS.md — Current State

Last updated: **2026-10-06, session 5** (security hardening, attendance corrections, holidays, mark-paid, pagination, Docker,
PRD §33 docs, redesign Part 2 — completed and verified after a power cut interrupted the session's final steps)

Legend: ✅ Complete · 🟡 In progress / partial · ⚠️ Needs testing · 🔴 Not started · ⛔ Blocked · 💥 Broken

> Verify against code before trusting this file. Update it in the same session as the change.

## 1. Feature status

| Feature | Status | Notes |
|---|---|---|
| Project setup (FastAPI, MySQL, Alembic) | ✅ | Alembic head `f6a7b8c9d0e1` (holidays + attendance_corrections) |
| Authentication (email/password, JWT) | ✅ | bcrypt, generic errors, inactive → 403; secrets ≥ 32 bytes enforced at startup (D-031) |
| Rate limiting (`/auth/login`, `/chat`) | ✅ | In-memory, 429 + `Retry-After` (D-031; one worker, KI-031) |
| Google OAuth | ⚠️ | Backend + tests; starts through the `/api` proxy; real Google round-trip not tried (KI-004); auto-provisioning needs an owner decision (KI-033) |
| RBAC + manager team scope | ✅ | `get_scope_employee_ids`; manager = self + direct reports (D-010) |
| Self-approval of leave | ✅ | Blocked for every role incl. HR/Admin — product-owner decision D-022; UI explains it |
| Employee management (CRUD, soft delete) | ✅ | + `monthly_gross_salary` (confidential, D-021) |
| Departments | ✅ | Derived from employees (D-005) |
| Attendance: records, summary, HR create, check-in/out, daily sheet, search | ✅ | Rules D-007; holidays `COMPANY_HOLIDAYS` |
| Attendance: edit / correction workflow | ✅ | Request → approve (manager/HR, never self) + HR direct edit; paid months locked (D-033) |
| Leave: apply, balance, cancel, approvals | ✅ | Working-day counting (D-008) |
| Holidays calendar | ✅ | National (code) + HR-declared (table); Leave → Holidays tab; excluded from payroll/leave counts (D-034) |
| Payroll register + payslips | ✅ | |
| **Payroll engine** (`POST /salary/generate`, UI dialog) | ✅ | LOP / PF / OT pay, idempotent, paid rows locked (D-021) |
| "Mark as paid" action | ✅ | `POST /salary/mark-paid`, irreversible, locks the month (D-036) |
| List pagination | ✅ | `/employees`, `/attendance/records`, `/chat/logs` — `limit`/`offset` + `X-Total-Count` (D-035); browser-verified |
| Document upload + RAG indexing | ✅ | PDF (page-aware), DOCX, TXT; versioning; archive |
| AI chat: intent router + DB tools | ✅ | Leave balance; rankings (overtime/late/absent; managers team-scoped, D-032), department headcount, company payroll summary, holidays, "this month"/month-only periods (D-029, D-030); profile lookups follow REST (D-039) |
| PRD §30 question bank | ✅ | `tests/test_question_bank.py` — 22 normal / 11 incorrect / 13 security / 13 calculation / 11 RAG (70 checks) |
| AI chat: policy Q&A via RAG with sources | ✅ | D-009 |
| Prompt-injection protection | ✅ | D-011 |
| Chat logging + history + admin audit log | ✅ | |
| Dashboard (HR summary + trend, personal `/dashboard/me`) | ✅ | Live current-month demo data via `generate_demo_month.py` |
| Excel reports (attendance, overtime, leave) | ✅ | OT amount pro-rated per record (KI-015 fixed) |
| Users & roles admin | ✅ | |
| Frontend: 13 pages | ✅ | **Redesign complete** (D-026, D-037, D-040): all 13 pages on design system v2, light + dark; legacy bridge deleted; `ui_qa.py` 0 issues, axe 0 violations in both themes |
| Automated tests | ✅ | 37 files, 882 checks, all passing; dev DB unchanged by a run (D-023) |
| Demo data for the current month | ✅ | `scripts/generate_demo_month.py` (D-024) — re-run monthly |
| README / docs | ✅ | + `docs/ARCHITECTURE.md`, `docs/AI.md`, `docs/API.md` (PRD §33) |
| Deployment | 🟡 | `Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` + README; **image build not yet run** (Docker daemon not running on the dev machine) |
| Out-of-PRD reference modules | 🔴 | P3 by decision D-002 |

## 2. PRD acceptance criteria (§36)

| Criterion | Status |
|---|---|
| User authentication works | ✅ |
| Role-based access works | ✅ |
| MySQL integration works | ✅ |
| Employee data can be retrieved | ✅ |
| Attendance questions work | ✅ |
| Leave questions work | ✅ (balance answers fixed in session 2) |
| Salary questions respect permissions | ✅ |
| Overtime calculations are correct | ✅ |
| AI chatbot works | ✅ (verified live in the browser) |
| RAG works | ✅ |
| PDF/DOCX documents can be indexed | ✅ (PDF with page numbers, DOCX and TXT tested end to end in `test_question_bank.py`) |
| AI provides document/source references | ✅ |
| Hallucination handling is implemented | ✅ |
| Prompt injection protection is implemented | ✅ |
| Chat logs are maintained | ✅ |
| Excel reports work | ✅ (downloaded through the UI in browser QA) |
| Dashboard works | ✅ (browser-verified with live data) |
| Automated tests exist | ✅ |
| README is complete | ✅ |
| Git history is maintained | 🟡 Sessions 1–4 are committed on `feature/hr-assistant` (HEAD `7b3e79e`; `main` is far behind). **All session-5 work is uncommitted** (≈ 46 modified + new files) — commit when the product owner asks |

## 3. Test status

Final full run, 2026-10-06 session 5 (`python scripts/run_tests.py`): **37 files, 882 checks passed, 0 failed**
(new: `test_holidays_corrections.py`, `test_security_hardening.py`; question bank extended to C14–C18 / D14).
`scripts/db_snapshot.py` before/after: **"Database unchanged"**; no leftover test rows (`T-*`, `@hrtest.dev`, `RAGTEST*`)
after the power cut. Frontend: `bunx tsc --noEmit -p .` ✅ · `bun run build` ✅ (bundle ≈ 1.06 MB, KI-006).

Session 4 run (kept for history): **35 files, 769 checks passed, 0 failed.**
`scripts/db_snapshot.py` snapshot taken before the session's first run vs. after the last: **"Database unchanged (all tables +
documents folder identical)."** (Baseline at session start: 34 files, 692 checks, all passing.)
The new question bank was also run against the **old** router: 20 of its checks failed there (payroll crash, salary of
"another employee" answered, "this month" ignored, rankings/headcount missing) — so it detects the regressions it targets.
Frontend: untouched this session (last: `bunx tsc --noEmit` ✅, `bun run build` ✅ in session 3).

## 4. Browser verification (2026-10-05 session 2)

- `scripts/ui_qa.py`: admin, hr, manager, employee × 1400 / 1280 / 390 px × 14 routes → **0 issues** (no console
  errors, no failed API calls, no horizontal overflow, top navbar without sidebar, role menus correct, hamburger on
  phones, forbidden routes redirect, role greetings correct).
- Interactive: phone hamburger + navigation, Attendance/Leave/Settings tabs, Mark Attendance and Apply Leave modals,
  document upload modal, Excel download, AI chat (balance + RAG answer with source chips), `#token=` login,
  Generate payroll (Sep 2026: 6 created), manager's own-leave notice, employee form validation.
- Defects found and fixed: 390 px table overflow, 1400 px hidden menu items, profile header overlap, manager shown as
  "#id", missing form validation, own-row deactivate button, truncated stat labels, wrong leave-balance year label,
  chat leave-balance answer. Details: KNOWN_ISSUES "Resolved".

## 4b. Redesign Part 1 verification (2026-10-05 session 3)

- `bunx tsc --noEmit -p .` ✅ · `bun run build` ✅ (bundle ≈ 923 KB).
- `python scripts/ui_qa.py` (updated for the sidebar shell): admin/hr/manager/employee × 1440/1024/390 × 14 routes → **0 issues**.
- Scripted behaviour checks (login validation, theme persistence/no flash, sidebar collapse, ⌘K palette, bell, role gating, mobile
  drawer focus trap/Escape/focus return, Employees filters/sort/menu/keyboard/view toggle/manager scope): **56/56**.
- axe-core (WCAG 2.1 A/AA) clean on Login + Dashboard (4 roles) + Employees, light and dark; reduced-motion and focus rings checked.
- **Not verified:** table pagination (demo data < page size), check-in/out POSTs (would mutate the dev DB), real Google round-trip.
- Backend/tests untouched, so `scripts/run_tests.py` was **not** re-run (last full run: session 2, 692 checks).

## 4c. Redesign Part 2 + final quality pass (2026-10-06 session 5)

- `python scripts/ui_qa.py`: admin/hr/manager/employee × 1440/1024/390 × 14 routes → **0 issues** (after deleting the bridge).
- axe-core WCAG 2.1 A/AA on 22 page views (HR: every page; admin: Settings; manager: Attendance/Leave; employee: 7 pages) →
  **0 violations in dark and in light** after one fix (success button 3.76:1 → `status-present-solid`, D-040).
- Pagination (KI-028): Attendance → Records 276 rows / 25 per page at 1440 and 390 px — range text, `offset` API calls,
  Prev/Next by mouse and keyboard, last page, no overflow.
- Screenshots reviewed: Attendance, Leave, Payroll, Employee profile, AI Assistant (dark); Leave, Documents, Reports, Settings (light).
- **Not verified:** check-in/out and correction POSTs by clicking (covered by API tests; would change the dev DB), real Google
  round-trip, Docker image build.

## 5. Where we are / what's next

**Current position:** All PRD requirements and all planned P1/P2 items are implemented and verified; the redesign is
complete. **Session-5 work is uncommitted.**

**Next logical tasks (DEVELOPMENT_PLAN.md):**
1. **Commit** session 5 in logical commits (when the product owner asks) — it is the largest uncommitted change so far.
2. Build and run the Docker stack once on a machine with Docker running (`docker compose up --build`).
3. Owner decision on Google sign-in auto-provisioning (KI-033: domain allow-list / `email_verified`).
4. Small cleanups: `users.py` queries → service (KI-034), chat confidence post-check (KI-035), drop unused `axios` (KI-037),
   frontend code-splitting (KI-006), pagination for `/leaves`, `/documents`, `/users` (KI-007 remainder).

## 6. History

- **≤ 2026-09-28:** Backend foundation — models, migrations, auth, RBAC, core APIs, services, seed, AI chat MVP,
  dashboard summary, attendance/overtime Excel, Google OAuth backend, first React frontend.
- **2026-10-05 session 1:** Persistent docs; HRMS frontend rebuild (13 pages); employees CRUD, departments, attendance
  check-in/out/daily/records, leave balance/list/cancel + manager scope fix, payroll list, users admin, dashboard/me,
  leave report, RAG + documents, prompt-injection guardrail, chat sources/history/audit; 654 checks.
- **2026-10-05 session 3:** Frontend redesign Part 1 (D-026/27/28): tokens + dark mode, Radix primitives, sidebar shell, ⌘K palette, Login/Dashboard/Employees; docs `frontend/DESIGN.md`, `frontend/REDESIGN_NOTES.md`; `ui_qa.py` updated.
- **2026-10-06 session 4:** PRD §30 question bank (`tests/test_question_bank.py`, 70 checks incl. a real 2-page PDF); AI
  router fixes it exposed — period resolution (D-029), rankings/headcount/unnamed-colleague/company-payroll tools (D-030),
  payroll-summary crash (R-019), "another employee's salary" leak of own data (R-020); 769 checks.
- **2026-10-06 session 5:** Mandatory ≥32-byte secrets + rate limiting (D-031); manager team rankings (D-032); attendance
  corrections + HR edit (D-033); holiday calendar (D-034); pagination (D-035); mark-as-paid (D-036); LOP rule confirmed
  (D-038); chat profile lookups match REST (D-039); Docker files; `docs/` (PRD §33); redesign Part 2 of all 10 pages (D-037).
  A power cut interrupted the final steps; they were finished afterwards: legacy bridge deleted, success-button contrast fix,
  dark/light axe pass, pagination browser check, handoff docs (D-040); 882 checks.
- **2026-10-05 session 2:** Sanity check of the uncommitted tree (no dangling `retrievers` imports); stale "Build Failed"
  root-caused (KI-005); full browser QA with 9 fixes; test isolation (D-023); current-month demo data (D-024); payroll
  engine + pro-rated OT report (D-021); self-approval rule confirmed (D-022); 692 checks.
