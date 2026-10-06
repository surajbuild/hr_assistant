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

### D-028 — Temporary "legacy bridge" for dark mode on not-yet-redesigned pages
- **Date:** 2026-10-05
- **Decision:** While Part 2 is pending, `globals.css` re-points Tailwind's raw palette variables (`--color-white`, `slate-*`,
  `emerald-50`, …) at design tokens under `.dark`, and keeps the old aliases (`navy`, `ink`, `page`, `brand-light`) mapped to tokens,
  so un-redesigned pages stay readable in both themes and inherit the new colours.
- **Reason:** the theme toggle is global; shipping a half-broken dark mode between sessions would mislead the owner's review.
- **Impact:** **Delete the bridge and the legacy aliases at the end of Part 2** (see `REDESIGN_NOTES.md` §4). New code must not rely
  on it: never use `text-white`/`bg-white`/raw palette classes — use tokens (`bg-brand text-brand-foreground`, `bg-surface`, …).
