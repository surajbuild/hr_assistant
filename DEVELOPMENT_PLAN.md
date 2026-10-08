# DEVELOPMENT_PLAN.md — Master Implementation Roadmap

> Mark tasks `[x]` when done — never delete them. Add new tasks where they belong.
> Priorities: **P0** blocker · **P1** critical (PRD acceptance) · **P2** important · **P3** nice-to-have.

Last updated: 2026-10-07 (session 9 — chat answer integrity D-044, Google sign-in D-045, health/readiness, real-LLM and Docker verification)

---

## Recommended implementation order

```
P0 docs ─► P0 proxy + API contract ─► P1 backend endpoints ─┬─► P1 frontend HRMS shell & pages
                                                             ├─► P1 RAG (documents) ─► P1 chat: policy via RAG + sources
                                                             └─► P1 tests for every new endpoint
                                          ─► P2 polish (settings, users, OAuth redirect, charts) ─► P3 extras
```

Dependencies:
- Frontend pages depend on the backend contract below (they can be built in parallel against the contract).
- Chat POLICY answers with sources depend on RAG (`document_chunks` table + `app/rag/*`).
- Leave balance depends on the policy entitlements constant (`app/services/leave_service.py: LEAVE_ENTITLEMENTS`).
- Payroll figures depend on `salary` rows (seeded); there is no payroll generation engine yet (P2).

---

## P0 — Blockers

- [x] Persistent project docs: `AGENTS.md`, `README.md`, `PROJECT_STATUS.md`, `DEVELOPMENT_PLAN.md`, `PROJECT_DECISIONS.md`, `KNOWN_ISSUES.md`, `CHANGELOG.md` (2026-10-05)
- [x] Single `/api/*` → backend proxy in `frontend/src/index.ts` (old proxy only forwarded 4 prefixes) (2026-10-05)
- [x] Fix `tests/test_rbac_matrix.py` false failures (`>= 7` employees vs 6 seeded) (2026-10-05)
- [x] Add `python-multipart`, `pypdf`, `pytest` to `requirements.txt` (upload endpoint + PDF parsing) (2026-10-05)

## P1 — Critical (PRD acceptance criteria + reference-site parity)

### Backend
- [x] `GET /auth/me` — current user + employee profile (frontend bootstrap)
- [x] Employees CRUD: `GET /employees` (filters; manager → team), `GET /employees/{id}` (ownership), `POST /employees`, `PUT /employees/{id}`, `DELETE /employees/{id}` (soft)
- [x] `GET /departments` — derived department stats
- [x] Attendance: `GET /attendance/daily`, `GET /attendance/records`, `POST /attendance/check-in`, `POST /attendance/check-out`, `GET /attendance/today`
- [x] Leaves: `GET /leaves` (HR all / manager team), `GET /leaves/balance/me`, `POST /leaves/{id}/cancel`, manager team-only approvals
- [x] Payroll: `GET /salary` list by month with employee names
- [x] Documents + RAG: `POST /documents/upload`, `GET /documents`, `DELETE /documents/{id}`, `document_chunks` migration, loader/chunker/embeddings/retriever
- [x] Chat: accept `message` or `question`, return `source`, `confidence`, `page`; POLICY intent uses RAG first, falls back to `policies.json`; `GET /chat/history`; `GET /chat/logs` (admin)
- [x] Reports: `GET /reports/leave` Excel export (attendance + overtime already existed)
- [x] Dashboard: `GET /dashboard/me` (any role, personal/team view) + `monthly_attendance` trend in `/dashboard/summary`
- [x] Users (admin): `GET /users`, `PATCH /users/{id}` (role / status)
- [ ] Manager team-scoped dashboard summary (currently manager sees personal + team counts via `/dashboard/me`)

### Frontend (HRMS shell like the reference site)
- [x] App shell: sticky top navbar, role-filtered menu, profile dropdown, mobile menu, client router
- [x] Login page (branded, email/password, Google button, demo accounts helper)
- [x] Dashboard (role-aware: HR/Admin KPIs + charts; employee/manager personal view)
- [x] Employees list (search, department/status filters, view/edit/delete) + add/edit form + detail page
- [x] Departments page
- [x] Attendance page (daily view for HR/manager, check-in/out + my history for everyone, HR mark attendance)
- [x] Leave page (apply, my leaves + balance, approvals for HR/manager, cancel)
- [x] Payroll page (HR/Admin: month selector, summary cards, salary table; employee: own payslips)
- [x] Documents page (HR/Admin upload + list + delete; everyone can view list)
- [x] Reports page (download attendance / overtime / leave Excel)
- [x] AI Assistant chat page (suggested prompts, sources/intent badges, history)
- [x] My Profile page
- [x] Settings page (admin: users & roles, chat audit log)

- [x] Manual browser QA of every page × role at desktop and phone width (KI-016) — done 2026-10-05 s2 with `scripts/ui_qa.py` (4 roles × 1400/1280/390 px × 14 routes, 0 issues) + interactive flows; 9 defects fixed
- [x] Current-month demo attendance generator so the dashboard has live data (KI-001) — `scripts/generate_demo_month.py` (D-024)
- [x] Hide/disable buttons consistently when the backend would 403 — own-row deactivate, own-leave approve/reject, future-month payroll (2026-10-05 s2)

### Tests
- [x] Tests for new endpoints (employees CRUD, departments, attendance daily/check-in, leaves list/balance/cancel/manager scope, salary list, documents/RAG, chat sources, users, dashboard/me)
- [x] PRD §30 question bank: 20 normal / 10 incorrect / 10 security / 10 calculation / 10 RAG — `tests/test_question_bank.py`
      (22 / 11 / 13 / 13 / 11 = 70 checks, 2026-10-06); fixed the router gaps it exposed (D-029, D-030, R-019…R-022)
- [x] Session 8 (2026-10-07, D-043): no caller-record fallback in the chat router; thresholds, department-wise overtime,
      on leave today, last week, PF / overtime amount, hours worked, attendance %, employee-ID lookup; chat failures logged
      and labelled `unavailable` — question bank [F] 21 + [G] 21 checks, `test_chat_api.py` [10] (R-023…R-025)
- [x] Chat: lower-case unknown names (KI-038); group tools — team/department attendance, department payroll, leave in a
      period, pending requests, team lists (KI-039); ambiguous / duplicate names, pronouns, "my manager", requester
      phrasing; direct answers without the LLM; grounding post-check (2026-10-07 session 9, D-044) — question bank [H] 32
- [ ] LLM-assisted intent fallback (KI-008, P2); multi-turn follow-ups ("and in August?"); group leave-usage tool (KI-039 rest)
- [ ] Store `confidence` in `chat_logs` (migration) so reloaded history shows answer labels (KI-041)

## Frontend redesign (D-026) — product-owner request, 2026-10-05

- [x] Part 1: design tokens + dark mode, Radix primitives, sidebar shell, ⌘K palette, Login, Dashboard (4 role layouts), Employees
- [x] **Owner approval of the Part 1 direction** — owner said "go ahead and do all the tasks" (2026-10-06, D-037)
- [x] Part 2: Employee form, Employee profile (cover/tabs), Departments, Attendance (calendar heat-map), Leave (drawer/timeline),
      Payroll, Documents (drag-and-drop), Reports, AI Assistant (bubbles/copy/history), Settings (2026-10-06, session 5)
- [x] Part 2: delete the dark-mode legacy bridge, full quality pass (roles × widths × themes, axe, keyboard), finalise docs
      (2026-10-06, session 5 — finished after a power cut interrupted the session; D-040)

## P2 — Important improvements

- [x] Tests must not change the dev DB — done via test-owned data + `TrackingClient` + namespaced seed test, verified with `scripts/db_snapshot.py` (D-023)
- [ ] Dedicated test database (`TEST_DATABASE_URL`) for crash-safety (KI-002 residual)
- [ ] Synonym map or dense embeddings for RAG (KI-010)
- [x] Use working days for leave length in the AI router too (KI-020) — and the LEAVE tool now includes the balance
- [x] Code-split the frontend bundle (KI-006, 2026-10-07, D-042); keyboard-accessible table rows (KI-018)
- [x] Default the AI router's month-only questions to the latest year with data instead of 2024 (KI-008) — plus "this month" /
      "last month" (D-029, 2026-10-06)
- [x] Team-scoped chat rankings for managers — owner said yes (2026-10-06, D-032)

- [x] Google OAuth callback redirects to the frontend with the token when started with `?next=frontend` (D-014) — real-account test pending, KI-004
- [ ] LLM-assisted intent/entity extraction as fallback when rule-based router returns UNKNOWN
- [x] Payroll generation engine — `generate_payroll`, `POST /salary/generate`, UI dialog, `employees.monthly_gross_salary` (D-021); OT amount pro-rated in reports (KI-015)
- [x] "Mark as paid" action for payroll rows — `POST /salary/mark-paid`, irreversible (2026-10-06, D-036)
- [ ] Salary-structure breakdown (basic / HRA / allowances) and payslip PDF
- [x] Revisit LOP policy for working days with no attendance record (KI-023) — owner: keep paid (2026-10-06, D-038)
- [x] Attendance edit (`PUT /attendance/records/{id}`) and correction-request workflow (request → approve) (2026-10-06, D-033)
- [x] Holidays calendar (table + API + Leave-page tab; payroll/leave counting exclude holidays) (2026-10-06, D-034)
- [x] Pagination on list endpoints (employees, attendance records, chat logs) — `limit`/`offset` + `X-Total-Count` (2026-10-06, D-035)
- [x] Rate limiting on `/auth/login` and `/chat` (2026-10-06, D-031)
- [x] Rotate to a ≥32-byte JWT secret; move SessionMiddleware secret fallback out of code — enforced at startup (2026-10-06, D-031)
- [x] Architecture document + AI documentation + generated API reference (PRD §33) — `docs/` (2026-10-06)
- [x] Deployment (Docker compose: MySQL + backend + frontend) — files + README; stack built and verified healthy in session 6 (2026-10-06)
- [x] Session-7 cleanups: `user_service` (KI-034), chat confidence post-check (KI-035), unused `axios` removed (KI-037),
      `limit`/`offset` on `/users`, `/leaves`, `/documents` (KI-007) — 2026-10-07, D-042
- [ ] Use the new `/leaves`, `/documents`, `/users` pagination in the UI tables (API-only so far)
- [x] Google sign-in production rules: verified email for linking, invite-only by default, `GOOGLE_ALLOWED_DOMAINS`,
      errors back to the login page (KI-033, 2026-10-07 session 9, D-045)
- [ ] Real Google consent round-trip with a real account (KI-004) — needs a person + the redirect URI in Google Cloud Console
- [x] `/health` + `/health/ready` (Docker healthcheck on readiness), `pool_pre_ping`, operational logging (`LOG_LEVEL`),
      LLM retry for fast transient failures (2026-10-07 session 9)
- [x] Docker images rebuilt and verified in an isolated compose project (2026-10-07 session 9)
- [ ] Owner: recreate the running Docker stack with the rebuilt images — `docker compose up -d` (KI-044)

## P3 — Nice-to-have (reference-site modules outside PRD scope)

- [ ] Recruitment module (jobs, candidates pipeline)
- [ ] Performance module (review cycles, goals)
- [ ] Biometric sync
- [ ] HR letter generation (offer/relieving/experience letters, payslip PDF)
- [x] Notifications bell — approver roles only, pending leave requests (redesign Part 1; employees have no notification endpoint)
- [ ] Bulk employee import from Excel
- [ ] Streaming chat responses
- [x] Dark mode (redesign Part 1, D-026)

---

## API contract (implemented 2026-10-05)

All endpoints require `Authorization: Bearer <jwt>` unless noted. Frontend calls them as `/api/<path>`.

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/auth/login` | public | `{email,password}` → `{access_token, token_type}` |
| GET | `/auth/me` | any | `{user_id,email,role,status,employee:{...}}` |
| GET | `/employees` | admin, hr, manager | query `search, department, status, limit?, offset?` (`X-Total-Count`); manager → self + direct reports. Items include `manager_name, email, role` |
| GET | `/employees/me` | any | own profile (detail schema incl. manager_name and own `monthly_gross_salary`) |
| GET | `/employees/{id}` | any | employee → self only; manager → self/team; hr/admin → any |
| POST | `/employees` | admin, hr | body: employee fields (+ `monthly_gross_salary`) + optional `email,password,role` to create login |
| PUT | `/employees/{id}` | admin, hr | partial update |
| DELETE | `/employees/{id}` | admin, hr | soft delete → status `inactive`, user `inactive` |
| GET | `/departments` | admin, hr, manager | `[{name, employee_count, active_count, designations[], managers[]}]` |
| GET | `/attendance/me` | any | own records |
| GET | `/attendance/summary` | any | own summary, `start_date,end_date` (aliases `from_date,to_date`) |
| GET | `/attendance/today` | any | own record for today or null |
| POST | `/attendance/check-in` | any | creates today's record; late after 09:15 |
| POST | `/attendance/check-out` | any | computes working/overtime minutes (OT beyond 540 min) |
| GET | `/attendance/daily` | admin, hr, manager | `date` (default latest with data); every in-scope employee + record or `not_marked` |
| GET | `/attendance/records` | admin, hr, manager | `employee_id?, from_date?, to_date?, status?, limit?, offset?` (`X-Total-Count`); manager limited to team |
| PUT | `/attendance/records/{id}` | admin, hr | `{status, in_time?, out_time?}`; worked days computed; not own record; 409 when the month is paid (D-033) |
| POST | `/attendance/corrections` | any | own past day `{attendance_date, in_time, out_time, reason}` → 201; 409 duplicate pending / paid month |
| GET | `/attendance/corrections/me` | any | own requests |
| GET | `/attendance/corrections` | admin, hr, manager | `status?`; manager → team; own excluded |
| POST | `/attendance/corrections/{id}/approve` · `/reject` | admin, hr, manager | `{note?}`; never own; manager → team |
| POST | `/attendance/corrections/{id}/cancel` | owner | pending only |
| GET | `/holidays` | any | `year?` → national + company holidays (D-034) |
| POST | `/holidays` | admin, hr | `{holiday_date, name}`; 422 weekend, 409 national/duplicate |
| DELETE | `/holidays/{id}` | admin, hr | company holidays only |
| POST | `/attendance` | admin, hr | create record for any employee |
| GET | `/attendance/{employee_id}` | admin, hr | existing |
| POST | `/leaves` | any | apply |
| GET | `/leaves/me` | any | own leaves |
| GET | `/leaves/balance/me` | any | per type: entitled, used, pending, remaining (calendar year) |
| GET | `/leaves` | admin, hr, manager | `status?`; manager → team only. Items include `employee_name, department, days` |
| PATCH | `/leaves/{id}/status` | admin, hr, manager | manager → team only |
| POST | `/leaves/{id}/cancel` | owner | only pending |
| GET | `/leaves/{employee_id}` | admin, hr | existing |
| GET | `/salary/me` | any | own slips |
| GET | `/salary` | admin, hr | `month?, year?` (default latest) items include `employee_name, employee_code, department` |
| GET | `/salary/summary` | admin, hr | existing |
| POST | `/salary/mark-paid` | admin, hr | `{salary_ids}` → `{marked, already_paid, not_found, paid_at}`; irreversible lock (D-036) |
| POST | `/salary/generate` | admin, hr | `{month, year, employee_ids?}` → `{working_days, provisional, created, updated, skipped[], items[]}` — payroll engine (D-021); future month → 400 |
| GET | `/salary/{employee_id}` | admin, hr | existing |
| GET | `/documents` | any | list (active + processing + failed; `include_archived` for hr/admin) |
| GET | `/documents/{id}/download` | any | original file (archived → hr/admin only) |
| POST | `/documents/{id}/reindex` | admin, hr | re-parse + re-index |
| POST | `/documents/upload` | admin, hr | multipart `file`, `name?` → parse+index |
| DELETE | `/documents/{id}` | admin, hr | archive + remove chunks |
| POST | `/chat` | any | `{message}` (or legacy `{question}`) → `{question, answer, intent, source, confidence, page, sources[]}`; confidence ∈ data_verified/unverified/document_grounded/policy_reference/not_found/clarification_needed/access_denied/unavailable/general |
| GET | `/health` · `/health/ready` | public | liveness · readiness (`SELECT 1`; 503 when MySQL is unreachable) |
| GET | `/chat/history` | any | own last N chat logs |
| GET | `/chat/logs` | admin | audit log; `limit, offset, search` (`X-Total-Count`) |
| GET | `/dashboard/summary` | admin, hr | KPIs + charts (+ `monthly_attendance`) |
| GET | `/dashboard/me` | any | personal month stats, leave balance, latest salary, today's status; manager: `team` block |
| GET | `/reports/attendance` | admin, hr | xlsx; `month+year` \| `year` \| `date_from,date_to`; `department` |
| GET | `/reports/overtime` | admin, hr | xlsx; `month+year` \| `year` \| `date_from,date_to`; `department` |
| GET | `/reports/leave` | admin, hr | xlsx; `month+year` \| `year` \| `date_from,date_to`; `department` |
| GET | `/users` | admin | list users with employee name |
| PATCH | `/users/{id}` | admin | `{role?, status?}` (cannot demote/deactivate self) |
