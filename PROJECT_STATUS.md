# PROJECT_STATUS.md — Current State

Last updated: **2026-10-05, session 3** (frontend redesign Part 1 — awaiting owner approval; backend unchanged since session 2)

Legend: ✅ Complete · 🟡 In progress / partial · ⚠️ Needs testing · 🔴 Not started · ⛔ Blocked · 💥 Broken

> Verify against code before trusting this file. Update it in the same session as the change.

## 1. Feature status

| Feature | Status | Notes |
|---|---|---|
| Project setup (FastAPI, MySQL, Alembic) | ✅ | Alembic head `e5f6a7b8c9d0` |
| Authentication (email/password, JWT) | ✅ | bcrypt, generic errors, inactive → 403 |
| Google OAuth | ⚠️ | Backend + tests; SPA `#token=` hand-off verified in browser; real Google round-trip not tried (KI-004) |
| RBAC + manager team scope | ✅ | `get_scope_employee_ids`; manager = self + direct reports (D-010) |
| Self-approval of leave | ✅ | Blocked for every role incl. HR/Admin — product-owner decision D-022; UI explains it |
| Employee management (CRUD, soft delete) | ✅ | + `monthly_gross_salary` (confidential, D-021) |
| Departments | ✅ | Derived from employees (D-005) |
| Attendance: records, summary, HR create, check-in/out, daily sheet, search | ✅ | Rules D-007; holidays `COMPANY_HOLIDAYS` |
| Attendance: edit / correction workflow | 🔴 | KI-012 |
| Leave: apply, balance, cancel, approvals | ✅ | Working-day counting (D-008) |
| Holidays calendar UI | 🔴 | Fixed national holidays only (code constant) |
| Payroll register + payslips | ✅ | |
| **Payroll engine** (`POST /salary/generate`, UI dialog) | ✅ | LOP / PF / OT pay, idempotent, paid rows locked (D-021) |
| "Mark as paid" action | 🔴 | P2 |
| Document upload + RAG indexing | ✅ | PDF (page-aware), DOCX, TXT; versioning; archive |
| AI chat: intent router + DB tools | ✅ | Leave tool now includes the calculated balance |
| AI chat: policy Q&A via RAG with sources | ✅ | D-009 |
| Prompt-injection protection | ✅ | D-011 |
| Chat logging + history + admin audit log | ✅ | |
| Dashboard (HR summary + trend, personal `/dashboard/me`) | ✅ | Live current-month demo data via `generate_demo_month.py` |
| Excel reports (attendance, overtime, leave) | ✅ | OT amount pro-rated per record (KI-015 fixed) |
| Users & roles admin | ✅ | |
| Frontend: 13 pages | ✅ | Functionally complete, browser-verified (D-020). **Redesign (D-026) in progress:** Part 1 ✅ done — design system v2, sidebar shell, dark mode, ⌘K palette, Login/Dashboard/Employees redesigned; ⏸ **awaiting owner approval of the direction**; Part 2 🔴 (other 10 pages + quality pass) — `frontend/REDESIGN_NOTES.md` |
| Automated tests | ✅ | 34 files, 692 checks, all passing; dev DB unchanged by a run (D-023) |
| Demo data for the current month | ✅ | `scripts/generate_demo_month.py` (D-024) — re-run monthly |
| README / docs | ✅ | |
| Deployment | 🔴 | P2 (Docker compose) |
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
| PDF/DOCX documents can be indexed | ✅ (DOCX + TXT in tests; PDF parser implemented, no real-PDF test yet) |
| AI provides document/source references | ✅ |
| Hallucination handling is implemented | ✅ |
| Prompt injection protection is implemented | ✅ |
| Chat logs are maintained | ✅ |
| Excel reports work | ✅ (downloaded through the UI in browser QA) |
| Dashboard works | ✅ (browser-verified with live data) |
| Automated tests exist | ✅ |
| README is complete | ✅ |
| Git history is maintained | 🟡 Sessions 1–2 are committed on `feature/hr-assistant` (HEAD `943940c` at the start of session 3); the session-3 redesign work is uncommitted, intentionally — commit when the product owner asks |

## 3. Test status

Final full run, 2026-10-05 session 2 (`python scripts/run_tests.py`): **34 files, 692 checks passed, 0 failed.**
`scripts/db_snapshot.py` before/after the run: **"Database unchanged (all tables + documents folder identical)."**
Frontend: `bunx tsc --noEmit` ✅, `bun run build` ✅.

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

## 5. Where we are / what's next

**Current position:** All PRD requirements implemented and verified end-to-end in a browser; payroll engine added;
tests are self-cleaning. Work is uncommitted.

**Next logical tasks (DEVELOPMENT_PLAN.md):**
0. **Owner review of redesign Part 1**, then redesign Part 2 (pages 4–13 + quality pass + delete the legacy bridge).
1. Commit in logical commits (when the product owner asks).
2. "Mark as paid" for payroll rows; review the LOP policy for unrecorded days with HR (KI-023).
3. PRD §30 question-bank test file (20 normal / 10 incorrect / 10 security / 10 calculation / 10 RAG).
4. Attendance corrections, holidays calendar, pagination, ≥32-byte JWT secret, Docker deployment.

## 6. History

- **≤ 2026-09-28:** Backend foundation — models, migrations, auth, RBAC, core APIs, services, seed, AI chat MVP,
  dashboard summary, attendance/overtime Excel, Google OAuth backend, first React frontend.
- **2026-10-05 session 1:** Persistent docs; HRMS frontend rebuild (13 pages); employees CRUD, departments, attendance
  check-in/out/daily/records, leave balance/list/cancel + manager scope fix, payroll list, users admin, dashboard/me,
  leave report, RAG + documents, prompt-injection guardrail, chat sources/history/audit; 654 checks.
- **2026-10-05 session 3:** Frontend redesign Part 1 (D-026/27/28): tokens + dark mode, Radix primitives, sidebar shell, ⌘K palette, Login/Dashboard/Employees; docs `frontend/DESIGN.md`, `frontend/REDESIGN_NOTES.md`; `ui_qa.py` updated.
- **2026-10-05 session 2:** Sanity check of the uncommitted tree (no dangling `retrievers` imports); stale "Build Failed"
  root-caused (KI-005); full browser QA with 9 fixes; test isolation (D-023); current-month demo data (D-024); payroll
  engine + pro-rated OT report (D-021); self-approval rule confirmed (D-022); 692 checks.
