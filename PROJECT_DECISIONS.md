# PROJECT_DECISIONS.md — Decision Log

> Record every important architectural, product, UX, database or business decision here so future agents do not
> accidentally reverse it. Never delete an entry; if a decision is reversed, add a new entry that supersedes it and
> mark the old one `SUPERSEDED by D-xxx`.

Format: **Date · Decision · Reason · Alternatives considered · Impact**

---

### D-001 — Keep the React/Bun/Tailwind frontend instead of the PRD's "HTML/CSS/JS/Bootstrap"
- **Date:** 2026-10-05
- **Decision:** The frontend stays on Bun + React 19 + TypeScript + Tailwind v4 + shadcn-style components (`frontend/`).
- **Reason:** PRD §24 lists the stack as *"Suggested Technology Stack"*, not mandatory. A working React app already
  existed, and the reference site (Angular Material) needs a component framework to match its look. Rewriting in
  Bootstrap would throw away work with no product benefit.
- **Alternatives:** Plain HTML + Bootstrap (PRD suggestion); Angular (what the reference site uses).
- **Impact:** Interns/reviewers must be able to explain React + Bun. README documents the frontend architecture.

### D-002 — The reference site defines UI/UX and module layout only; the PRD defines scope
- **Status:** the **visual and navigation presentation** part (top navbar, navy palette, `#f1f5f9` background, Inter) is
  **SUPERSEDED by D-026**. Module list/order, role-gated menu, role-specific greetings, status-badge conventions and the
  "reference = UI/UX only, PRD = scope" rule still stand.
- **Date:** 2026-10-05
- **Decision:** `https://hrms.nectorinternational.com/` (Nector Foods HRMS, Angular + PrimeNG/Material) is used for: top
  navbar layout, palette (navy `#1e3a5f`, accent `#2563eb`, bg `#f1f5f9`), Inter font, module names/order, role-gated menu,
  role-specific dashboard greetings, status-badge conventions. Its extra modules (Recruitment, Performance, Biometric,
  Telegram, HR letters, bulk import, 3-stage leave approval) are **not** PRD requirements and are parked in P3.
- **Reason:** Source-of-truth rule: PRD > everything else. The user asked for "something like" the reference site.
- **Alternatives:** Cloning all reference modules (too large for the timeline, outside PRD acceptance criteria).
- **Impact:** Our menu = Dashboard, My Profile, Employees, Departments, Attendance, Leave, Payroll, Documents, Reports,
  AI Assistant, Settings. The AI Assistant is our differentiator and is not in the reference site.
- **How the reference was analysed:** the site is a login-walled SPA; routes, menu items, role guards and UI strings
  were extracted from its public JS bundles (`main-*.js`, lazy `chunk-*.js`). No credentials were used.

### D-003 — Single `/api` proxy prefix + client-side History routing
- **Date:** 2026-10-05
- **Decision:** The Bun server (`frontend/src/index.ts`) forwards `/api/*` → `${BACKEND_URL}/*` (prefix stripped) and
  serves the SPA for every other path. React routes (`/employees`, `/leave`, …) are handled by `frontend/src/lib/router.tsx`.
- **Reason:** The previous proxy whitelisted 4 prefixes, so new backend modules were unreachable, and SPA paths like
  `/employees` would collide with API paths of the same name.
- **Alternatives:** CORS + calling `:8000` directly (needs CORS config, leaks backend URL into code); hash routing.
- **Impact:** Frontend code always calls `/api/...`. Backend routes stay un-prefixed (tests and docs unchanged).

### D-004 — RAG uses BM25 over sparse term vectors stored in MySQL (no external vector DB)
- **Date:** 2026-10-05
- **Decision:** `app/rag/embeddings.py` produces sparse term-frequency vectors (tokenize → stopwords → light stemming);
  they are stored as JSON in `document_chunks.term_vector`; `app/rag/retriever.py` scores chunks of *active* documents
  with Okapi BM25 in Python and applies relevance thresholds.
- **Reason:** OpenRouter (the configured provider) has no reliable embeddings endpoint; local neural embeddings need
  torch/sentence-transformers (hundreds of MB); FAISS/Chroma add native dependencies on Windows. HR handbooks are small
  (hundreds of chunks), so lexical BM25 is fast, deterministic, testable and explainable in a review.
- **Alternatives:** OpenAI embeddings + FAISS/Chroma (PRD suggestion) — can be added later by replacing only
  `embeddings.py`/`retriever.py`; the DB schema (`document_chunks`) already isolates the index.
- **Impact:** No semantic matching of synonyms (see KNOWN_ISSUES KI-010). Thresholds: `MIN_SCORE=1.0`, coverage ≥ 34 %,
  or "strong coverage" ≥ 50 % with ≥ 2 matched terms (IDF is near zero in tiny corpora).

### D-005 — Departments are derived from `employees.department`
- **Date:** 2026-10-05
- **Decision:** No `departments` table; `GET /departments` aggregates employee rows (counts, designations, managers).
- **Reason:** PRD schema has `department` as a string column; adding a table + FK migration would touch every query and the seed for little value now.
- **Alternatives:** Departments/designations tables like the reference site (P2/P3 if needed).
- **Impact:** Renaming a department = updating employees. Department "CRUD" is not available.

### D-006 — Deleting an employee is a soft delete
- **Date:** 2026-10-05
- **Decision:** `DELETE /employees/{id}` sets `employees.status = inactive` and the linked `users.status = inactive`.
- **Reason:** Attendance, leave, salary and chat-log history must survive (audit, payroll, PRD logging). FKs would also block hard deletes.
- **Alternatives:** Hard delete with cascades (data loss), `deleted_at` column (needs migration).
- **Impact:** UI labels the action "Deactivate". Inactive users cannot log in (403).

### D-007 — Attendance calculation rules
- **Date:** 2026-10-05
- **Decision (in `app/services/attendance_service.py`, mirrors `app/data/policies.json`):**
  shift start 09:00 · grace 15 min (arrival ≤ 09:15 is on time) · `late_minutes` measured from 09:00 when beyond grace ·
  lunch 60 min deducted when the span is > 5 h · standard day 480 working minutes · `overtime_minutes = max(0, worked − 480)` ·
  worked < 240 min ⇒ `half_day`.
- **Reason:** Matches the seed data exactly (09:00–18:00 ⇒ 480; 09:00–20:00 ⇒ 600 worked / 120 OT; 09:25 ⇒ 25 late) and PRD §20's
  "Standard Minutes" example. The policy text's "beyond 9 hours" = 9 h on premises incl. lunch = 480 worked minutes.
- **Impact:** Check-in/out and any future payroll engine must use these helpers (`calculate_day_metrics`).

### D-008 — Leave days and balances
- **Date:** 2026-10-05
- **Decision:** Leave days are counted as **working days (Mon–Fri)** (`leave_service.count_leave_days`). Balances are per
  calendar year for casual (12), sick (10), earned (15) — values from `policies.json`. Unpaid/maternity/paternity are
  not balance-tracked. `remaining = entitled − approved days`; pending days are reported separately.
- **Reason:** Weekends are non-working per the working-hours policy; charging them would be wrong.
- **Alternatives:** Calendar days (what the AI router previously displayed for leave history).
- **Impact:** The AI router's leave history still prints inclusive calendar days (`router.py` ~line 506) — see KI-020.

### D-009 — Policy questions: RAG first, `policies.json` fallback; UNKNOWN intent also tries RAG
- **Date:** 2026-10-05
- **Decision:** For `POLICY` intent, `/chat` searches uploaded documents; if nothing relevant is found it falls back to
  the built-in `app/data/policies.json`. For `UNKNOWN` intent it also searches documents and re-routes to `POLICY` on a
  hit. The LLM is instructed to answer exactly *"I could not find this information in the available HR documents."* when
  the context lacks the answer (PRD §19).
- **Reason:** PRD §11/§12 require answers from uploaded documents with sources; the rule-based classifier misses phrasings
  like "How many days can I work from home?".
- **Impact:** Response `source` is the document file name for RAG answers, `policies.json` for fallback. Tests accept both.

### D-010 — Manager data scope = self + direct reports; nobody approves their own leave
- **Date:** 2026-10-05
- **Decision:** `employee_service.get_scope_employee_ids()` is the single source of scope: admin/hr → all, manager → own
  id + employees whose `manager_id` is the manager, employee → own id. Applied to `/employees`, `/employees/{id}`,
  `/departments`, `/attendance/daily`, `/attendance/records`, `/leaves`, and leave approval. Managers never see others'
  salaries. Self-approval of leave is forbidden for every role.
- **Reason:** PRD §4.3/§17 ("Manager → Team data"). Previously managers got 403 on the directory but could approve **any** leave.
- **Alternatives:** Recursive reporting chain (skip-level) — not required now.
- **Impact:** `tests/test_rbac_matrix.py` and `tests/test_leaves_patch.py` were updated accordingly.

### D-011 — Prompt-injection guardrail runs before intent detection
- **Date:** 2026-10-05
- **Decision:** `guardrails.detect_prompt_injection()` (regex patterns: instruction override, role-play escalation,
  "give me admin access", system-prompt extraction, jailbreak keywords, SQL) refuses the request for **every** role,
  never calls the LLM or touches data, returns `source="guardrail"`, `confidence="access_denied"`, and logs
  `error="PROMPT_INJECTION_BLOCKED"`.
- **Reason:** PRD §18 + demo security questions. Regex is deterministic and testable; RBAC is still enforced separately.
- **Alternatives:** LLM-based classifier (costly, non-deterministic).
- **Impact:** Watch for false positives; add test cases to `tests/test_rag.py` [9] when patterns change.

### D-012 — Chat API contract
- **Date:** 2026-10-05
- **Decision:** `POST /chat` accepts `{"message": ...}` (PRD §27) and the legacy `{"question": ...}`; returns
  `{question, intent, answer, source, confidence, page, sources[]}`. `confidence` ∈ `data_verified | document_grounded |
  policy_reference | not_found | access_denied | general`.
- **Reason:** PRD §27 example + backwards compatibility with existing tests/clients.

### D-013 — Reports: period filters and PRD summary sheets
- **Date:** 2026-10-05
- **Decision:** All `/reports/*` accept `month`+`year` (or `year`, or `date_from`/`date_to`) and `department`. Attendance and
  overtime workbooks open on a **Summary** sheet with the exact PRD §22 columns, followed by the detailed sheet. OT Amount
  comes from `salary.overtime_amount` for the months in range.
- **Reason:** PRD §22 columns were missing (only daily records existed); the UI selects months.
- **Update 2026-10-05 (session 2):** OT Amount is no longer taken from whole-month payroll rows; it is computed per
  overtime record with the payroll engine's hourly OT rate, so partial-month ranges are exact (KI-015, D-021).

### D-014 — Google OAuth hands the token to the SPA only when asked
- **Date:** 2026-10-05
- **Decision:** `/auth/google/login?next=frontend` stores a session flag; the callback then 302-redirects to
  `${FRONTEND_URL}/login#token=<jwt>`. Without the flag the callback keeps returning JSON.
- **Reason:** Keeps the existing 45 OAuth tests/API behaviour while making the browser flow usable. The token is in the URL
  fragment (never sent to servers) and the SPA strips it immediately.

### D-015 — Error wording follows PRD §29
- **Date:** 2026-10-05
- **Decision:** LLM failure answer is *"The AI service is temporarily unavailable. Please try again."*; RAG not-found
  sentence as in D-009.

### D-016 — Keep the 4-role model
- **Date:** 2026-10-05
- **Decision:** Roles stay `employee`, `manager`, `hr`, `admin` (lowercase in DB/JWT), not the reference site's six
  (SUPER_ADMIN, ADMIN, HR_ADMIN, HR_MANAGER, MANAGER, EMPLOYEE).
- **Reason:** PRD §4 defines exactly these four. Reference role → ours: SUPER_ADMIN/ADMIN → admin, HR_ADMIN/HR_MANAGER → hr.

### D-017 — Documents are archived, versioned, and visible to all roles
- **Date:** 2026-10-05
- **Decision:** `DELETE /documents/{id}` archives (removes chunks from the index, keeps row + file). Uploading a document
  whose display name matches an existing non-archived one archives the old version(s) and stores `version = max + 1`.
  Every authenticated user can list/download active documents (policies are company-wide); only HR/Admin upload/archive.
  Unparseable files are stored with `status=failed` + `error_message` instead of erroring.
- **Reason:** PRD §23 requires name/date/uploader/version/status tracking; audit trail.

### D-018 — Single-stage leave approval
- **Date:** 2026-10-05
- **Decision:** A pending leave is approved/rejected once by HR/Admin or the employee's manager.
- **Reason:** PRD only requires approval; the reference's 3-stage flow (manager → department head → HR) is P3.

### D-019 — Seed reset removes documents uploaded by demo users
- **Date:** 2026-10-05
- **Decision:** `scripts/seed_db.py` (and therefore `tests/test_seed.py`) deletes `documents`/`document_chunks` rows uploaded
  by demo users before deleting those users (FK `documents.uploaded_by`). Files on disk are kept.
- **Reason:** Otherwise reseeding fails with an FK error once anyone has uploaded a document.
- **Impact:** After running the full test suite, re-upload demo policy documents (see `sample_documents/`).
- **Update 2026-10-05 (session 2):** `tests/test_seed.py` no longer resets the real demo data (D-023), so a test run
  no longer deletes uploaded documents. The rule still applies when someone runs `python scripts/seed_db.py` by hand.

### D-020 — Browser QA with Playwright driving the installed Microsoft Edge (dev-only)
- **Date:** 2026-10-05 (session 2)
- **Decision:** `scripts/ui_qa.py` uses the Python `playwright` package with `channel="msedge"` (the Edge already installed
  on Windows), so no browser binaries are downloaded. `playwright` lives in `requirements-dev.txt`, **not** in
  `requirements.txt` — the app never imports it.
- **Reason:** KI-016 required real browser verification; the Claude-in-Chrome extension was declined. Playwright is
  scriptable and repeatable (4 roles × 3 widths × 14 routes in ~2 min).
- **Alternatives:** Manual clicking (not repeatable); full Playwright browser download (~300 MB); Selenium (needs a driver).
- **Impact:** Run `python scripts/ui_qa.py` after UI changes (both servers running). It fails on console errors, failed
  API calls, horizontal overflow, missing/visible-sidebar navbar violations, clipped menu items without a scroll cue,
  wrong role menus, and unguarded forbidden routes.

### D-021 — Payroll engine rules (PRD has no formulas)
- **Date:** 2026-10-05 (session 2)
- **Decision:** `salary_service.generate_payroll(db, month, year, employee_ids=None)` / `POST /salary/generate` (HR/Admin):
  - Salary structure = new column `employees.monthly_gross_salary` (migration `e5f6a7b8c9d0`, backfilled from each
    employee's latest salary row); fallback = latest salary row's gross; none → employee skipped with a reason.
  - Working days = Mon–Fri minus `attendance_service.COMPANY_HOLIDAYS` (the 3 mandatory national holidays in policies.json).
  - LOP days = absent + 0.5 × half days + approved **unpaid** leave working days not already marked absent/half day.
    Working days **without any attendance record are not deducted** (avoids docking pay for unrecorded data).
  - LOP deduction = gross ÷ working days × LOP days (stored in `salary.deductions`).
  - PF = 12 % × earned basic, basic = 35 % of gross (35 % reproduces the seeded PF figures to within ₹100 for 5 of 6 employees).
  - Overtime pay = OT minutes ÷ 60 × gross ÷ (working days × 8) × 1.5.
  - net = gross + overtime − PF − deductions (same relation as the seeded rows).
  - Idempotent per (employee, month, year): unpaid row → updated in place; row with `paid_at` → locked/skipped; else created.
  - Future months → 400; current month allowed but flagged `provisional`.
- **Privacy:** `monthly_gross_salary` is returned only to HR/Admin, or to the employee for their own record
  (`employee_service.can_view_salary`); managers get `null`. Settable via POST/PUT `/employees` (HR/Admin).
- **Reason:** KI-014 (no payroll engine). Constants live at the top of `salary_service.py` so finance can change them in one place.
- **Alternatives:** Deriving basic/HRA/allowances per Indian CTC structures (needs a salary-structure table — P2).
- **Impact:** The overtime report's OT Amount now uses the same hourly OT rate per record (KI-015, see D-013 update).

### D-022 — Nobody approves their own leave, including HR and Admin (confirmed by the product owner)
- **Date:** 2026-10-05 (session 2)
- **Decision:** The block in `app/api/leaves.py` (self-approval → 403 "You cannot approve or reject your own leave
  request.") stays for **every** role. Confirmed by the product owner when asked. An HR/admin user's own leave must be
  decided by another HR/admin user or their reporting manager.
- **UI:** Own requests are excluded from the approval queue and get no Approve/Reject buttons anywhere; when the approver
  has pending requests of their own, the Approvals tab shows a notice explaining who will review them.
- **Supersedes:** nothing — this confirms D-010's "no self-approval" clause after an explicit product decision.

### D-023 — Tests must leave the dev database byte-identical
- **Date:** 2026-10-05 (session 2)
- **Decision:** Tests still run against the dev MySQL DB, but every test owns its data:
  - Test rows use unique markers (codes like `T-PAY-*`, `T-HRMS-*`, emails `@hrtest.dev`, `RAGTEST` document names) and
    are deleted in `finally`.
  - `tests/test_seed.py` seeds a **namespaced copy** of `seed_data.json` (`TS-EMP004`, `ts.aman@hrtest.dev`) and clears only
    that copy — it no longer resets the real demo data.
  - Tests that call `POST /chat` use `tests/helpers.TrackingClient`, which deletes exactly the `chat_logs` rows created by
    questions it sent (rows newer than the test start with a matching question), so a human using the app concurrently is unaffected.
  - RAG ranking assertions pass `document_ids=` to `retriever.search` so real uploaded HR documents can't change the outcome.
  - Proof: `python scripts/db_snapshot.py save before.json` → run tests → `python scripts/db_snapshot.py diff before.json`
    (row count + SHA-256 of every row of 8 tables + the documents folder). `python scripts/db_snapshot.py isolate` runs
    each test file alone and names any file that changes the DB.
- **Reason:** KI-002 — the suite used to wipe demo data and uploaded documents.
- **Alternatives:** A separate test database (still a good P2 — would also protect against crashes mid-test).

### D-024 — Current-month demo data generator
- **Date:** 2026-10-05 (session 2)
- **Decision:** `scripts/generate_demo_month.py [--month YYYY-MM] [--dry-run]` creates attendance for all active
  employees from the 1st of the month up to today (weekends → `weekend`, company holidays → `holiday`, ~3 % absent,
  ~12 % late, ~4 % half day, ~18 % overtime evenings, today → checked in but not out when run before 18:00) and a few
  leave requests (approved ones only on past days, pending/rejected on future days). Values are deterministic per
  (employee code, date) and computed with `attendance_service.calculate_day_metrics`. Existing (employee, date) rows and
  overlapping leaves are skipped → idempotent. The 2024 seed data is never touched.
- **Reason:** KI-001 — dashboard showed "1 present / 5 absent" from the sparse 2024 seed.
- **Impact:** Run it once per new month for demos (it was run for 2026-09 and 2026-10 in the dev DB). Tests do not depend on it.

### D-025 — Desktop navbar density breakpoints
- **Status:** **SUPERSEDED by D-026** (the top navbar was replaced by a sidebar; the breakpoints below no longer apply).
- **Date:** 2026-10-05 (session 2)
- **Decision:** Hamburger menu below 1280 px; 1280–1535 px text-only links and avatar-only profile button; ≥ 1536 px icons +
  user name. Scroll arrows appear whenever the link row still overflows; the active item is scrolled into view.
- **Reason:** At 1400 px the admin's 11 items overflowed and "AI Assistant"/"Settings" were hidden with no cue (found in browser QA).
- **Impact:** AGENTS.md §7 updated; `scripts/ui_qa.py` asserts no clipped item without a scroll cue at ≥ 1280 px.

### D-026 — Frontend redesign: premium SaaS look, sidebar navigation, light/dark (supersedes the visual/navigation part of D-002 and all of D-025)
- **Date:** 2026-10-05 (redesign Part 1)
- **Decision:** The product owner rejected the HRMS-reference look and explicitly asked for a modern, premium SaaS dashboard
  that is visibly different side by side. Per AGENTS.md's priority order (newer explicit owner instruction > AGENTS.md > D-002),
  the **visual and navigation presentation** changes; everything else is kept:
  - Navigation: collapsible **left sidebar** (≥1280px expanded, 768–1279px icon rail, <768px drawer) + slim 56px top bar
    (breadcrumb, ⌘/Ctrl+K command palette, notification bell for approver roles, theme toggle, profile menu). Menu order,
    module list and role filtering are unchanged (same role sets as the backend); items are grouped Overview/People/Workspace/
    Insights/Admin.
  - Visual language: indigo accent (`#4f46e5` light / `#818cf8` dark), slate neutrals, flat 12px-radius cards with 1px borders,
    8px controls, one soft shadow level for floating layers only, Inter with tabular numerals, 150–250ms motion that honours
    `prefers-reduced-motion`. Fixed colour per status (present/absent/late/half/leave/neutral) shared by badges, charts, heat-map.
  - **Dark mode**: system by default, toggle in the top bar (and on Login), persisted in `localStorage` (`hr_theme`), applied
    before first paint. All colours/radii/shadows are tokens in `styles/globals.css`; no hex in components.
  - Role-specific dashboards (admin / hr / manager / employee) with intentionally different layouts, built **only** from
    existing endpoints (no new API, no fake data). Widgets without real data are derived client-side or hidden (e.g. no
    notification bell for employees; no deltas on today-only KPIs).
- **Reason:** owner instruction; the old look was judged dated. The reference site remains the module/role reference only.
- **Alternatives:** recolouring the old top-navbar layout (rejected: "must not look like a recolour"); MUI/Ant Design (forbidden —
  fights the shadcn/Tailwind stack).
- **Impact:** `AGENTS.md` §7 rewritten; `frontend/DESIGN.md` is the design source of truth; `scripts/ui_qa.py` now asserts the
  sidebar shell instead of the top navbar; D-025's breakpoints are obsolete. No backend, API-contract, auth, role-rule or
  business-logic change. Done in two sessions: Part 1 (tokens, primitives, shell, Login/Dashboard/Employees — awaiting owner
  approval) and Part 2 (remaining 10 pages + quality pass). Working notes: `frontend/REDESIGN_NOTES.md`.

### D-027 — Frontend dependencies added for the redesign (Radix primitives only)
- **Date:** 2026-10-05
- **Decision:** Added `@radix-ui/react-dialog` (Modal/ConfirmDialog/drawers/command palette — focus trap, Escape, scroll lock),
  `@radix-ui/react-dropdown-menu` (row/profile/theme menus), `@radix-ui/react-tooltip` (icon-rail labels), `@radix-ui/react-popover`
  (notification bell), `@radix-ui/react-switch` (Switch primitive for Part 2 forms/settings). They match the existing
  shadcn/Radix stack (`react-select`, `react-label`, `react-slot` were already used).
- **Not added:** `framer-motion` (CSS keyframes cover every needed animation), `@tanstack/react-table` (sorting + pagination are
  ~60 lines inside `DataTable`), `cmdk` (palette built on Radix Dialog), any chart/icon library (recharts + lucide-react stay).
- **Reason:** accessibility-critical behaviour (focus trapping, roving focus, ARIA) should not be hand-rolled.
- **Impact:** +5 small packages; production bundle ≈ 923 KB minified (was ≈ 898 KB; KI-006 code-splitting still open).

### D-028 — Temporary "legacy bridge" for dark mode on not-yet-redesigned pages — COMPLETED (bridge deleted 2026-10-06, D-040)
- **Date:** 2026-10-05
- **Decision:** While Part 2 is pending, `globals.css` re-points Tailwind's raw palette variables (`--color-white`, `slate-*`,
  `emerald-50`, …) at design tokens under `.dark`, and keeps the old aliases (`navy`, `ink`, `page`, `brand-light`) mapped to tokens,
  so un-redesigned pages stay readable in both themes and inherit the new colours.
- **Reason:** the theme toggle is global; shipping a half-broken dark mode between sessions would mislead the owner's review.
- **Impact:** **Delete the bridge and the legacy aliases at the end of Part 2** (see `REDESIGN_NOTES.md` §4). New code must not rely
  on it: never use `text-white`/`bg-white`/raw palette classes — use tokens (`bg-brand text-brand-foreground`, `bg-surface`, …).

### D-029 — How the AI assistant resolves time periods ("this month", "September", "last month")
- **Date:** 2026-10-06
- **Decision:** `router.resolve_period()` decides the period of every attendance / ranking / salary question:
  - month **and** year given → used as given;
  - month without a year → the most recent such month (not in the future) that has records — attendance months for
    attendance questions, payroll months for salary questions; with no records at all, the most recent past occurrence
    by calendar;
  - "this/current month" → the current month; if the current month has no records yet, the latest month with data, and the
    context carries a note saying so (the LLM must tell the user which month it describes);
  - "last/previous month" → the previous calendar month; a year alone → the whole year; nothing → all recorded dates
    (company payroll summaries: the latest payroll month).
  - `extract_month_and_year()` now returns `year=None` when no year is written; "May I…" is not the month of May.
- **Reason:** The old router hard-coded 2024 for a month without a year (KI-008) and ignored "this month", so PRD demo 1
  ("What is my attendance this month?") and demo 4 ("Who worked the most overtime this month?") answered with all-time totals.
  Since D-024 the demo data has 2026 months too, so "September" was ambiguous.
- **Alternatives:** Always the calendar year (wrong for the 2024 seed dataset); always 2024 (wrong for live data); asking a
  follow-up question (the chat is single-turn).
- **Impact:** Tests that expect seed numbers must write the year ("August 2024"); `test_chat_api.py`, `test_ai_router.py` and
  `scripts/smoke_test_chat.py` were updated. Period queries go through `attendance_service.get_months_with_data` /
  `salary_service.get_payroll_periods`.

### D-030 — Chat answers for rankings, headcount, unnamed colleagues and company payroll (no permission rule changed)
- **Date:** 2026-10-06
- **Decision:** New controlled tools in `app/ai/router.py`, each applying the permission rule that already exists for the
  same data over REST:
  - **Rankings** — "who worked the most overtime / was late the most / was absent the most" →
    `attendance_service.rank_employees` (top 5, ties share a rank). HR/Admin only, like the existing overtime ranking.
  - **Department headcount** — "How many employees are in Engineering?" → `employee_service.list_departments`; HR/Admin
    company-wide, manager limited to self + direct reports, employee refused (same as `GET /departments`).
  - **Unnamed other person** — "another employee's salary", "a colleague's leave": refused when the role may not see that
    kind of data for others (salary: everyone but HR/Admin; attendance/leave: employees); otherwise the user is asked to name
    the person. Previously the router silently fell back to the caller's own record.
  - **Company payroll** — "total payroll", "all salaries", "payroll for 2024" with nobody named → HR/Admin get the payroll
    **summary** only (never a per-person salary table, AGENTS.md §3.6); others are refused.
  - "Show all employee personal information" → the directory rule (HR/Admin only).
  - A person/period with no records → explicit "not available for the requested period" context (PRD §29) instead of zeros.
- **Reason:** PRD §30 examples and the §35 demo 2 question were mis-routed (UNKNOWN) or answered with the caller's own data;
  the HR payroll summary crashed with a `TypeError` (the router read summary keys that `get_salary_summary` never returned).
  Found by the new `tests/test_question_bank.py`.
- **Alternatives:** Team-scoped rankings for managers — not done: it would change the existing HR/Admin-only ranking rule, which
  needs the product owner (AGENTS.md §8). Open question, see KI-029.
- **Impact:** `tests/test_question_bank.py` (PRD §30 bank, 70 checks) guards all of the above.

### D-031 — Signing secrets are mandatory; rate limiting on login and chat (KI-003, KI-011)
- **Date:** 2026-10-06 (session 5)
- **Decision:** `app/utils/security.load_secret()` refuses to start the app when `JWT_SECRET_KEY` or `SESSION_SECRET_KEY` is
  missing, shorter than 32 bytes, or still an `.env.example` placeholder. The `"default-session-secret-key"` fallback in
  `app/main.py` is gone. `app/utils/rate_limit.py` adds in-memory sliding-window limits (no new dependency):
  every `POST /auth/login` per client IP (30/min), failed logins per (IP, email) (5 per 15 min, cleared by a success), and
  `POST /chat` per user (20/min, checked before any work so a flood never reaches the LLM or `chat_logs`). Over the limit →
  429 with `Retry-After`; values via `RATE_LIMIT_*` env vars. The client IP comes from `X-Forwarded-For` only when the direct
  peer is in `TRUSTED_PROXY_IPS` (IPs/CIDRs, default loopback); the Bun proxy overwrites that header with the real address.
- **Reason:** owner-approved P2 security hardening (session 5 "do all the tasks"). Login brute force and LLM cost abuse were
  unbounded; the 12-byte dev secret triggered PyJWT warnings.
- **Alternatives:** `slowapi`/Redis — heavier, a new dependency; unnecessary for a single-process deployment.
- **Impact:** state is per process → run one uvicorn worker (Docker does). Multi-worker needs a shared store (KI-031). Test
  files reset the chat limiter through `tests/helpers.TrackingClient` (`reset_chat_rate_limit=False` in the limiter's own test).
  Rotating `JWT_SECRET_KEY` logs everyone out (done once for the dev `.env` in session 5).

### D-032 — Managers get attendance rankings for their own team in chat (KI-029, confirmed by the product owner)
- **Date:** 2026-10-06 (session 5)
- **Decision:** "Who was late / absent / did overtime the most?" — HR/Admin company-wide (unchanged); **managers: ranking over
  themselves + direct reports** (`get_scope_employee_ids`, the same scope as `GET /attendance/records`); employees refused.
  The context says "limited to you and your direct reports". Salary rankings stay HR/Admin-only.
- **Reason:** product owner answered "Yes, team-scoped" (2026-10-06). Managers can already see each report's attendance.
- **Impact:** `tests/test_question_bank.py` C14 (no out-of-team names in the context) and D14 (numbers match a scoped SQL ranking).

### D-033 — Attendance corrections: request → approve, plus HR direct edit (KI-012, confirmed by the product owner)
- **Date:** 2026-10-06 (session 5)
- **Decision:** table `attendance_corrections` + `app/services/correction_service.py`.
  - Any employee requests in/out times for one of their **past** days with a reason (`POST /attendance/corrections`); one
    pending request per day; status is derived on approval with the check-out rules (D-007: < 4 h → half day; late after the
    grace period; OT beyond 480 min).
  - Reviewers: the employee's manager (direct reports only) or HR/Admin. **Nobody reviews their own request** (same principle
    as D-022); the review queue excludes the caller's own requests. Approval creates or updates the attendance row.
  - HR/Admin may edit any record directly (`PUT /attendance/records/{id}`), **but not their own** (they file a request).
  - Both are refused (409) when that month's salary row of the employee is paid (D-036): paid payroll must not silently
    disagree with attendance.
- **Reason:** product owner chose "Request → approve" (2026-10-06); the reference HRMS has a request → approve flow.
- **Alternatives:** HR-only edit (rejected by the owner); editing absent/leave statuses through requests (leave has its own
  module, so requests only carry worked-day times).
- **Impact:** approval does not regenerate payroll automatically — HR re-runs generation for unpaid months.

### D-034 — Holiday calendar: national holidays in code + HR-declared company holidays in a table
- **Date:** 2026-10-06 (session 5)
- **Decision:** the 3 fixed national holidays stay in `attendance_service.COMPANY_HOLIDAYS` (recur yearly, cannot be removed).
  HR/Admin declare one-off company holidays in table `holidays` (`GET/POST/DELETE /holidays`; weekends and national dates are
  rejected). Declared holidays are excluded from payroll working days (`salary_service`), from leave-day counting
  (`leave_service.count_leave_days(..., holidays=)` — so leave balances no longer charge national **or** declared holidays,
  extending D-008), from the OT hourly rate in reports, and are marked `holiday` by the demo generator. The chat answers
  holiday-calendar questions from this data (also when a document matched first).
- **Reason:** DEVELOPMENT_PLAN P2 "Holidays calendar (table + UI)"; the reference HRMS keeps holidays in the Leave module.
- **Impact:** deleting a holiday does not recalculate payroll already generated; re-run generation for unpaid months.

### D-035 — List pagination convention: `limit`/`offset` + `X-Total-Count`
- **Date:** 2026-10-06 (session 5)
- **Decision:** `GET /employees` (optional `limit`), `GET /attendance/records` (default 1000 as before) and `GET /chat/logs`
  (+ `search` on question/email) accept `limit`/`offset`; the response stays a plain JSON array and the total is in the
  `X-Total-Count` header (`app/utils/pagination.py`; frontend `api.getPage<T>()` → `{items,total}`).
- **Reason:** keeps every existing client working (no envelope change) while letting the UI page on the server.

### D-036 — "Mark as paid" for salary rows is irreversible
- **Date:** 2026-10-06 (session 5)
- **Decision:** `POST /salary/mark-paid {salary_ids}` (HR/Admin) sets `paid_at` on unpaid rows; already-paid / unknown ids are
  reported, not errors. There is no "unpay" in the API or UI: a paid row is locked for the payroll engine (D-021) and for
  attendance corrections (D-033). HR may mark any row including their own — it is bookkeeping, not an approval of a request.
- **Reason:** DEVELOPMENT_PLAN P2; the engine already honoured `paid_at`.
- **Alternatives:** admin-only unpay — not requested; a correction after payment should be a new adjustment, not an edit.

### D-037 — Redesign Part 2 started on the product owner's go-ahead
- **Date:** 2026-10-06 (session 5)
- **Decision:** the owner asked to "go ahead and do all the tasks", which included Part 2 of the redesign; this is recorded as
  approval of the Part 1 direction (the D-026 checkpoint). No design feedback was given, so tokens/components are unchanged.

### D-038 — Unrecorded working days stay paid (KI-023, confirmed by the product owner)
- **Date:** 2026-10-06 (session 5)
- **Decision:** the D-021 rule stands: a working day without any attendance record is **not** loss of pay; only recorded
  absences, half days and approved unpaid leave reduce pay. The owner chose "Keep paid".
- **Reason:** attendance capture is not complete enough (no biometric sync) to treat a missing record as an absence.

### D-039 — Chat profile lookups follow `GET /employees/{id}` (confirmed by the product owner)
- **Date:** 2026-10-06 (session 5)
- **Decision:** asking the chat about another person's profile ("Who is Rahul?", "What is Sneha's department?") is allowed for
  HR/Admin (everyone), managers (direct reports only) and refused for employees — exactly the REST rule. The refusal comes from
  `guardrails.check_rbac_access` before the LLM is called. Previously `check_rbac_access` allowed every profile lookup
  ("general employee profile lookups"), so the chat exposed code, department, designation, joining date, status and manager
  that REST refused. Found by the documentation pass; owner chose "Match REST".
- **Also:** `POST /attendance` (HR/Admin create) now refuses the caller's own employee id (403), in line with D-033.
- **Impact:** `tests/test_question_bank.py` C15–C18.

### D-040 — Redesign finished: legacy bridge removed, solid-success token added
- **Date:** 2026-10-06 (end of session 5, completed after a power cut interrupted the session)
- **Decision:** With all 13 pages on design system v2 and no component using raw palette classes, the D-028 bridge
  (`@layer base .dark { --color-white … }`) and the legacy aliases (`--color-page/ink/ink-muted/navy/navy-dark/brand-light`,
  `--legacy-navy`) were deleted from `globals.css`. A new token `--status-present-solid` (`#047857` light, `#34d399` dark) is used
  by the `success` button variant.
- **Reason:** the bridge was temporary by design. axe found white text on `#059669` (Approve / check-in buttons) at 3.76:1 in light
  mode; darkening `--status-present` itself would have shifted every badge, chart and calendar, which share that colour (D-026).
- **Verification:** `ui_qa.py` 0 issues (4 roles × 1440/1024/390); axe WCAG 2.1 A/AA 0 violations on 22 page views in light and in
  dark; server pagination verified in the browser (KI-028); `tsc` + `bun run build` clean.

### D-041 — Google OAuth redirect URI goes through the frontend proxy
- **Date:** 2026-10-06
- **Decision:** `GOOGLE_REDIRECT_URI` defaults to `http://localhost:3000/api/auth/google/callback` (`.env.example`, README §11) instead
  of `http://localhost:8000/auth/google/callback`.
- **Reason:** in Docker only port 3000 is published, so Google could never redirect the browser to `:8000`. The SPA already starts
  the login through `/api/auth/google/login`, so the callback must use the same origin (the session cookie is set there too).
- **Impact:** that URI must be registered in Google Cloud Console. `FRONTEND_URL` stays `http://localhost:3000`. Real Google
  round-trip still unverified (KI-004).

### D-042 — Session-7 cleanups: D-035 pagination on `/users`, `/leaves`, `/documents`; route-level code-splitting
- **Date:** 2026-10-07 (session 7). **Written in session 9** (KI-040): session 7 cited D-042 in commit `41e9cc4`
  ("refactor: extract user_service and paginate users/leaves/documents (D-042, KI-007, KI-034)"), in CHANGELOG
  2026-10-07, DEVELOPMENT_PLAN and KNOWN_ISSUES KI-006, but never wrote the entry. This record states only what those
  sources and the code establish; nothing was added.
- **Decision:**
  - `GET /users`, `GET /leaves` and `GET /documents` accept optional `limit` / `offset` and report the total in
    `X-Total-Count`, following D-035 (the response stays a plain JSON array, so existing clients are unaffected).
    The UI tables do not use it yet (DEVELOPMENT_PLAN P2).
  - The frontend route pages are `React.lazy` chunks behind `Suspense` and `frontend/build.ts` sets `splitting: true`
    (commit `f3e5a63`, KI-006): the single ≈ 780 KB bundle became 53 chunks, the largest ≈ 407 KB.
- **Reason:** KI-007 (lists returned everything) and KI-006 (bundle size); both were open P2 items.
- **Impact:** `tests/test_pagination_cleanups.py`; `scripts/ui_qa.py` waits for the page `<h1>` because lazy pages mount
  after `networkidle`.

### D-043 — The chat never substitutes the caller's record; group / threshold / PF / hours questions get their own tools
- **Date:** 2026-10-07 (session 8)
- **Decision:**
  - `router.find_target_employee` lost its last line ("nobody named → the caller"). It now returns `(employee, is_other, note)`:
    a named employee (code, **employee ID** — "employee 4" = the number of the code, EMP004 — or name); unknown code/ID/name or an
    unnamed colleague → nobody (`not_found` / refusal, D-030); a team, department, "employees", company … question → nobody
    (group); "my / I / me" → the caller. When **nothing** is named: the `employee` role gets their own record **with a note the
    answer must state** ("no person was named, so these are your records") unless the wording is aggregate (total, average,
    most, who, which …) — an employee can only ever see their own records, so a plain "How much PF was deducted?" can only mean
    them. Every other role gets a **clarification** context (`Clarification needed: …`, no records loaded, confidence
    `clarification_needed`) instead of their own figures.
  - Group questions with no tool ("attendance of the Engineering department", "salary of the Engineering department") → the
    same clarification for roles that may see the data, the usual access denial for those that may not.
  - New controlled tools (same roles/scope as the rankings, D-032: HR/Admin company-wide, managers self + direct reports,
    employees refused): thresholds ("more than 5 late entries", "more than 10 hours overtime", "at least …", "N or more"),
    lists ("who worked overtime last week", "which members of my team …"), department-wise overtime
    (`attendance_service.get_overtime_by_department`), who is on approved leave today/yesterday/tomorrow
    (`leave_service.get_employees_on_leave`, the dashboard rule). "my team" → self + direct reports for any role.
  - Individual attendance context adds hours worked and an **attendance percentage** = (present days + 0.5 × half days) ÷
    recorded working days (recorded days minus weekend/holiday rows; absences and leave count as not attended) —
    `attendance_service.attendance_percentage`. For Aman, August 2024 this gives 22 of 24 = 91.7 %, matching the PRD §1 example.
  - SALARY intent now covers "PF", "provident fund", "overtime amount/pay"; "total PF / total overtime amount" with nobody named is
    the company payroll summary (HR/Admin; others refused). A per-person salary context lists a Python-computed totals line when
    several months are shown, so the LLM never adds money up. A department name is never answered with the company summary.
  - `resolve_date_range`: "today", "yesterday", "this week", "last week" (previous Monday–Sunday) for attendance, rankings,
    thresholds, department overtime and "leave taken in …".
  - `POST /chat` failures: a retrieval/database exception is caught (session rolled back, fixed "could not retrieve" answer, LLM
    not called, `chat_logs.error = RETRIEVAL_ERROR: …`, source `error`); LLM failures keep their message. Both → confidence
    `unavailable` (previously an LLM failure on a data question was labelled `data_verified`, and a DB failure was a 500 without a
    log row). The chat UI knows the two new labels (`clarification_needed`, `unavailable`).
- **Reason:** project audit (session 8): HR asking "Who is employee 1025?", "Show department-wise overtime", "How many employees are on
  leave today?" received **their own** profile/attendance/leave record, labelled `data_verified`; several PRD §7–§10 example
  questions were mis-routed (PF and "hours did X work" → UNKNOWN; "total overtime amount" → the caller's attendance).
- **Alternatives:** clarification for every role including employees (rejected: an employee's plain question has exactly one
  possible subject; the note keeps it explicit — easy to switch off in `find_target_employee` if the owner prefers);
  answering clarifications without the LLM (kept the existing pattern: the LLM gets a context with no figures, as for D-030).
- **Impact:** no permission rule changed. `tests/test_question_bank.py` [F] (21 PRD questions, numbers from raw SQL) and [G]
  (13 no-substitution questions + 8 direct target checks); `tests/test_chat_api.py` [10] (failure handling). Against the old code
  34 question-bank checks fail and the target check crashes; the retrieval-failure test raised a 500.
- **Reviewed in session 9 (D-044):** kept. An employee's unnamed "How much PF was deducted?" can only be about themself
  (they may see no one else's data) and the note makes the assumption explicit — privacy-safe and matching PRD §4.1/§8.
  Extended to managers for salary only (they may see no one else's salary). The real risk was a *different* person
  being mistaken for "nobody named" (lower-case names, "his", "my manager's", "Can I see bruce's …"), fixed in D-044.

### D-044 — Chat answer integrity: who is asked about, direct answers, grounding post-check, group tools (session 9)
- **Date:** 2026-10-07 (session 9)
- **Decision:**
  - **Target resolution** (`router.match_employees`, `find_target_employee`): employee codes match as whole words
    (`EMP0040` no longer matches EMP004); names match in any case, full name before first name / surname; a name that fits
    several employees (shared surname, duplicate full name) is **never guessed** — the caller gets a clarification listing
    the candidates they may see; two people in one question → "one at a time". Unknown persons are recognised in any case
    by name slots (possessive, "was X present", "who is X", "of / for X" when the caller is not the subject) with an
    exclusion list of ordinary/HR words, relatives and festivals (KI-038). "he / his / she / her / they / their" = an
    unnamed other person. "my manager's …" = the caller's manager. "I" / "me" as the *requester* ("Can I see …", "show
    me …") does not make the caller the subject.
  - **Direct answers:** clarifications and "employee not found" are written by the router (`direct_answer`, prefixes
    `Clarification needed:` / `Employee not found:`) and returned without calling the LLM, in PRD §29 wording
    (`I could not find an employee named "Bruce".`).
  - **No enumeration:** for roles that may not see other people's data of the asked kind, an unknown name gets the same
    access denial as a real colleague.
  - **Grounding post-check** (`app/ai/grounding.py`): every number in an LLM answer must occur by value in the verified
    context, the question or today's date; otherwise confidence `unverified` (UI "Check figures") and
    `chat_logs.error = UNVERIFIED_NUMBERS: …`. The answer is not rewritten.
  - **Prompt:** today's date in the user prompt; system rules for numbers (copy exactly, no arithmetic), stating `Note:`
    lines, uploaded document text as data not instructions, Markdown tables for lists of 3+.
  - **Group tools (KI-039):** attendance of a team / department / company for a day (daily sheet) or period (per
    department and per employee up to 25; attendance %), department payroll totals (HR/Admin, aggregates only), who was on
    leave in any period (was: always today), pending leave requests (approval queue, own requests excluded), team /
    department employee lists (same scope as `GET /employees`; managers were refused before).
  - **Routing:** "How many casual leaves are allowed?" (PRD §11) is POLICY, not the caller's balance; "who works in X" is
    EMPLOYEE.
  - **LLM client:** one retry for fast transient failures (connect error, 429/502/503/504), never for read timeouts;
    `max_tokens` 700.
- **Reason:** session-9 audit + a real-provider run. On the session-8 code an employee asking "Can I see bruce's salary?",
  "What is his salary?" or "What is my manager's salary?" received **their own salary** labelled `data_verified`; HR's
  "Can I see the payroll?" returned HR's own salary; "was bruce present yesterday?" gave the employee their own attendance
  (the real model then mixed both subjects); `EMP0040` resolved to EMP004; duplicate names silently picked the first;
  "Who was on leave last week?" answered for today; PRD §11's policy question returned a balance.
- **Permissions:** no rule widened beyond an existing REST rule — managers' team lists follow `GET /employees`, department
  payroll is HR/Admin like `GET /salary/summary`. The chat became stricter (no enumeration, no guessing).
- **Alternatives:** rewriting or blocking `unverified` answers (rejected: a false positive would destroy a correct answer;
  a visible flag + audit entry is safer); an LLM-based entity extractor (rejected for now: non-deterministic, and the
  permission-relevant decision "who is this about" must be testable).
- **Impact:** `tests/test_question_bank.py` [H] 32 checks (+ 10 updated [B]/[F]/[G] cases), `tests/test_production_hardening.py`,
  `tests/test_chat_api.py` [7]; `scripts/verify_real_llm.py` (manual real-provider check). On the session-8 code 34
  question-bank checks fail.

### D-045 — Google sign-in stays, invite-only by default, verified email required (KI-033)
- **Date:** 2026-10-07 (session 9)
- **Decision:** Keep Google sign-in (built in D-014/D-041, credentials configured), but:
  - a **new** Google identity is linked to an existing account only when Google reports `email_verified = true`
    (otherwise 403);
  - an unknown Google account is **not** auto-provisioned unless its email domain is listed in `GOOGLE_ALLOWED_DOMAINS`
    (comma-separated; empty = invite-only, the default). HR creates the employee with that email; the person then signs
    in with Google;
  - a failed sign-in started from the SPA returns to `/login#error=<reason>` and the login page shows it (was a raw JSON
    error page).
- **Reason:** an HRMS is not open registration. Before, any Google account became an active `employee` with an employee
  row (visible in headcount, documents, holiday data), and the email-linking path did not check `email_verified` — a
  Google account carrying an unverified copy of a colleague's address could be linked to that colleague's account
  (takeover). Reproduced in session 9: running the new tests against the old code created such an account.
- **Alternatives:** removing Google sign-in (rejected: it is already built and the owner configured credentials; with
  these rules it adds convenience, not risk); domain allow-list as the only mode (rejected: many deployments have one HR
  team creating accounts — invite-only is the safer default).
- **Impact:** `.env.example` `GOOGLE_ALLOWED_DOMAINS`; `tests/test_oauth_google.py` [2a], unverified/no-claim linking,
  [12], [13]. **Not verified:** the real Google consent round-trip (needs a person signing in; KI-004).
