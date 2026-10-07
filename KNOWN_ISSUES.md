# KNOWN_ISSUES.md

> Every significant known problem, so nobody wastes time rediscovering it. Update the status instead of deleting entries;
> move fixed issues to the "Resolved" section with the date.

Severity: 🔴 high · 🟠 medium · 🟡 low

| ID | Issue | Severity | Area | Status |
|---|---|---|---|---|
| KI-001 | Demo data goes stale every month (dashboard falls back to the last date with data) | 🟡 | Seed / Dashboard | Mitigated — run `scripts/generate_demo_month.py` monthly (D-024) |
| KI-002 | Tests run against the dev database (no separate test DB) | 🟡 | Tests | Mitigated — tests leave it byte-identical (D-023); separate DB still P2 |
| KI-004 | Google OAuth browser flow not verified with a real Google account | 🟡 | Auth | Partially tested (token hand-off `#token=` verified; since session 5 the login starts through the `/api` proxy — 302 + session cookie verified) |
| KI-005 | Bun dev server can't resolve **new** files imported via the `@/` alias until restarted | 🟡 | Frontend DX | Root cause found — restart `bun dev` after adding a file |
| KI-006 | Frontend bundle ≈ 780 KB minified, no code-splitting | 🟡 | Frontend perf | Fixed 2026-10-07 (D-042): route pages lazy-loaded, largest chunk ≈ 407 KB. The shared React/Radix/recharts chunks are still large — vendor splitting is a further option |
| KI-007 | No pagination on list endpoints/tables | 🟡 | API / UI | Partly done 2026-10-06 (D-035): `/employees`, `/attendance/records`, `/chat/logs`; UI uses it for Attendance records + audit log. `/users`, `/leaves`, `/documents` accept `limit`/`offset` since 2026-10-07 (API only — the UI still loads everything); `/salary` still returns everything (small today) |
| KI-008 | Rule-based intent router misses some phrasings; month without year defaulted to 2024 | 🟡 | AI | Partly fixed 2026-10-06 — period resolution D-029; PRD §30 phrasings covered by `test_question_bank.py`; unusual wording can still miss (LLM-assisted fallback = P2) |
| KI-009 | Scanned/image-only PDFs cannot be indexed (no OCR) | 🟡 | RAG | Open |
| KI-010 | Lexical RAG: synonyms ("remote work" vs "work from home") may not match | 🟠 | RAG | Open |
| KI-013 | Settings → "Company Policy" tab shows hard-coded values duplicated from `policies.json` | 🟡 | Frontend | Open |
| KI-017 | `httpx2` in requirements looks odd but is imported by Starlette's TestClient here | 🟡 | Dependencies | Documented |
| KI-018 | Clickable table rows are not keyboard-focusable (row action buttons are) | 🟡 | Accessibility | Fixed in `DataTable` (rows with `onRowClick` are focusable, Enter/Space activate) — verified on Employees; other tables get it automatically |
| KI-019 | Check-in/out uses the server's local clock; no timezone setting | 🟡 | Attendance | Open |
| KI-021 | Manager `/leaves` list includes the manager's own leaves | 🟡 | Leave | Mitigated (UI hides actions + explains, API 403 — D-022) |
| KI-022 | `uvicorn --reload` never restarts its worker when launched from a console-less shell (agent tools) | 🟡 | Dev tooling | Workaround |
| KI-023 | Payroll: working days without any attendance record are paid (not LOP) | 🟡 | Payroll | By design — confirmed by the product owner 2026-10-06 (D-038) |
| KI-024 | Payroll for the current month is provisional and changes as attendance is recorded | 🟡 | Payroll | By design (flagged `provisional` in API + UI) |
| KI-025 | Orphan files stay in `documents/` after a manual seed reset or archive | 🟡 | Documents | Open |
| KI-026 | `test_rag.py` chat-source check passes for either the test or the real "Work From Home Policy.txt" (same file name) | 🟡 | Tests | Open |
| KI-031 | Rate limits live in process memory: reset on restart, per uvicorn worker | 🟡 | Security | By design for one worker (D-031); multi-worker needs Redis or similar |
| KI-032 | Approving a correction, declaring/removing a holiday does not regenerate payroll already generated for unpaid months | 🟡 | Payroll | By design — HR re-runs "Generate payroll" (D-033, D-034); paid months are locked |
| KI-033 | Google sign-in auto-provisions any unknown Google account as an active `employee` (no domain allow-list, `email_verified` not checked) | 🟠 | Auth / Security | Open — needs an owner decision (allow-list domain? invite-only?) |
| KI-034 | `app/api/users.py` queries the DB in route handlers instead of a service (AGENTS §2.1) | 🟡 | Architecture | Fixed 2026-10-07 — `app/services/user_service.py` |
| KI-035 | Chat `confidence` stays `document_grounded` even when the LLM answers "I could not find this information…" | 🟡 | AI | Fixed 2026-10-07 — `_confidence` post-checks the answer text → `not_found` |
| KI-036 | `/chat` requests rejected with 400/422/429 are not written to `chat_logs` (PRD §28 logs interactions that reached the assistant) | 🟡 | AI / Logging | By design for now — note for audits Retrieval/DB failures **are** logged since 2026-10-07 (D-043) |
| KI-037 | `frontend/package.json` lists `axios`, which nothing imports | 🟡 | Dependencies | Fixed 2026-10-07 — removed from `package.json` / `bun.lock` |
| KI-038 | Chat: an unknown person written in lower case ("was bruce present") is not recognised as a person; an employee then gets their own record (with the "no person was named" note), other roles a clarification | 🟡 | AI | Open — names are detected by capitalisation (D-043) |
| KI-039 | Chat group questions only cover overtime / late / absence thresholds and lists, department-wise overtime, rankings, headcount, on leave, company payroll; others (department attendance %, department payroll) get a clarification | 🟡 | AI | By design for now (D-043) — add a tool + question-bank case per new group question |
| KI-040 | `PROJECT_DECISIONS.md` has no D-042 entry although CHANGELOG / STATUS / PLAN cite D-042 (session-7 code-splitting + pagination) | 🟡 | Docs | Open — the session-7 author should write it from CHANGELOG 2026-10-07 |

---

## Details

### KI-001 — Demo data goes stale
- **Cause:** The seed (`app/data/seed_data.json`) is Aug–Sep 2024; real demo usage needs current-month data.
- **Fix in place:** `python scripts/generate_demo_month.py` (idempotent) creates realistic attendance + a few leaves for the
  current month; `--month YYYY-MM` back-fills a past month. Run on 2026-10-05 for 2026-09 and 2026-10.
- **Residual:** Run it again at the start of each month you demo (and optionally `POST /salary/generate` for the previous month).

### KI-002 — Tests use the dev database
- Since D-023 a full run leaves all 8 tables + `documents/` byte-identical (verified with `scripts/db_snapshot.py`).
- **Residual risk:** If a test process is killed mid-run its `finally` cleanup does not run; leftovers carry obvious
  markers (`T-*` codes, `@hrtest.dev`, `RAGTEST*`, `TS-EMP*`). **Proposed:** `TEST_DATABASE_URL` + a dedicated schema.
- **Gotcha:** MySQL REPEATABLE READ — a test's own session keeps an old snapshot; call `db.commit()`/`db.rollback()`
  before re-reading rows written through the API.

### KI-004 — Google OAuth flow
- Since session 5 the SPA button navigates to `/api/auth/google/login?next=frontend` (through the Bun proxy, so it also works
  in Docker where the backend is not published; verified: 302 to Google + `Set-Cookie: session=…` pass through the proxy).
  `GOOGLE_REDIRECT_URI` is now `http://localhost:3000/api/auth/google/callback` (D-041, 2026-10-06; verified: login 302 to Google
  carries that redirect_uri in the Docker stack). The URI must also be added to the OAuth client in Google Cloud Console.
  Earlier: the SPA button called `http://localhost:8000/auth/google/login?next=frontend`; the callback redirects to
  `FRONTEND_URL/login#token=…` (D-014). Verified in the browser on 2026-10-05: opening `/login#token=<valid JWT>` signs in,
  stores the token, strips the fragment and lands on `/dashboard`. Not verified: the real Google consent round-trip.

### KI-005 — Bun dev server and new files (root cause found 2026-10-05)
- **Symptom:** Browser shows "Build Failed — Could not resolve `@/components/X`" right after a new file `X` is created and
  imported, while `bun run build` and `tsc` succeed.
- **Root cause:** Bun's dev bundler (`bun --hot`, and also `bun --watch`) caches tsconfig `paths`-alias lookups; files
  created after the server started are not found via `@/...` until the process restarts. Saving the importer or the new
  file does not help. A **relative** import of the same new file resolves immediately (probe-tested).
- **Workaround:** Restart `bun dev` after adding new files (keep using `@/` imports — the convention). A server left in
  this state keeps serving the error overlay to already-open tabs.

### KI-008 — Intent router limitations
- `app/ai/router.py` is keyword-based. UNKNOWN questions are tried against documents (D-009) but data questions with
  unusual wording may get a generic answer.
- **Fixed 2026-10-06:** the hard-coded 2024 year default and the ignored "this month" (D-029); rankings, headcount, unnamed
  colleagues and company payroll questions (D-030). `tests/test_question_bank.py` is the regression bank — add a failing
  question there first when a new phrasing is reported.
- **Fixed 2026-10-07 (session 8, D-043):** the "nobody named → the caller" fallback (group, employee-ID and threshold questions
  were answered with the caller's own record); thresholds, department-wise overtime, on leave today, last week, PF, overtime
  amount, hours worked, attendance %, employee ID lookup.
- **Still open:** LLM-assisted intent/entity extraction fallback (P2); multi-turn follow-ups ("and in August?"). Lower-case unknown names: KI-038.

### KI-010 — Lexical retrieval
- BM25 matches stemmed words, not meaning. **Proposed:** synonym map for common HR terms, or dense embeddings
  (replace `app/rag/embeddings.py` + `retriever.py`; schema unchanged).

### KI-017 — `httpx2`
- Starlette's `TestClient` in this environment imports `httpx2` (seen in tracebacks); removing it breaks the tests.

### KI-022 — uvicorn `--reload` hang from console-less shells
- **Symptom:** log shows `StatReload detected changes … Reloading...` but never `Started server process`; the OLD worker
  keeps serving old code (new routes 405/404). Reproduced 3× on 2026-10-05 when uvicorn was started from the agent's
  background Bash; `--timeout-graceful-shutdown` does not help. When the product owner ran `--reload` from a normal
  terminal, reloads worked.
- **Likely cause:** on Windows the reloader stops its worker with a console Ctrl-C event, which cannot be delivered when
  the process tree has no console.
- **Workaround (agents):** start uvicorn **without** `--reload` and restart it after backend edits; kill leftover
  `multiprocessing.spawn` children (they keep port 8000 bound).

### KI-023 / KI-024 — Payroll assumptions
- Unrecorded working days are paid; only recorded absences, half days and approved unpaid leave reduce pay (D-021,
  confirmed D-038). Generating the current month marks the result `provisional`. Paid rows (`paid_at`) are locked; since
  session 5 HR/Admin set it with `POST /salary/mark-paid` (D-036, irreversible).

### KI-025 — Orphan files in `documents/`
- `scripts/seed_db.py` reset and archive keep stored files for audit. **Proposed:** an admin "purge archived files" task.

### KI-031 — In-memory rate limits
- `app/utils/rate_limit.py` keeps hit timestamps in a dict per process. Restarting the backend clears them; with several
  uvicorn workers each worker counts separately (limits effectively multiplied). Docker runs one worker. **Proposed if
  scaling out:** move the counters to Redis (same `RateLimiter` interface).

### KI-032 — Payroll is not regenerated automatically
- Payroll rows are a snapshot from the last "Generate payroll" run. Approving an attendance correction, editing a record or
  declaring/removing a holiday changes what the engine *would* compute, but existing unpaid rows change only when HR runs
  generation again (idempotent). Paid rows never change (D-036).

---

## Resolved

| ID | Issue | Resolved | Fix |
|---|---|---|---|
| R-001 | `tests/test_rbac_matrix.py` expected ≥ 7 employees, seed has 6 | 2026-10-05 | Assertion matched to seed |
| R-002 | Managers could approve/reject **any** leave | 2026-10-05 | Team-only + no self-approval (D-010, D-022) |
| R-003 | Bun proxy forwarded only `/auth`, `/chat`, `/dashboard`, `/reports` | 2026-10-05 | Single `/api/*` proxy (D-003) |
| R-004 | `requirements.txt` UTF-16/BOM; missing `python-multipart`, `pypdf`, `pytest` | 2026-10-05 | Rewritten as UTF-8, deps added |
| R-005 | No prompt-injection protection (PRD §18) | 2026-10-05 | `detect_prompt_injection` (D-011) |
| R-006 | RAG modules were empty stubs; `retrievers.py` misnamed | 2026-10-05 | Implemented `app/rag/*`, `retriever.py`; re-verified session 2: no imports of `retrievers` remain, all `app.*` modules import |
| R-007 | `get_attendance_summary` returned `Decimal`s | 2026-10-05 | Cast to `int` |
| R-008 | Reports lacked PRD §22 summary columns and a Leave report | 2026-10-05 | Summary sheets + `/reports/leave` (D-013) |
| R-009 | Seed reset failed with FK error once documents existed | 2026-10-05 | D-019 |
| KI-014 | No payroll engine (seeded salary rows only) | 2026-10-05 s2 | `generate_payroll` + `POST /salary/generate` + UI (D-021) |
| KI-015 | Overtime report OT Amount used whole-month payroll rows | 2026-10-05 s2 | Per-record minutes × monthly OT rate (D-021) |
| KI-016 | No in-browser visual QA | 2026-10-05 s2 | `scripts/ui_qa.py`: 4 roles × 1400/1280/390 px × 14 routes → 0 issues; interactive flows checked; defects below fixed |
| KI-020 | AI router printed leave length in calendar days | 2026-10-05 s2 | Uses `count_leave_days` (working days) |
| KI-003 | JWT secret in local `.env` shorter than 32 bytes | 2026-10-06 s5 | `load_secret` refuses < 32 bytes / placeholders; dev secrets rotated (D-031) |
| KI-011 | `SessionMiddleware` fell back to a hard-coded secret | 2026-10-06 s5 | Fallback removed; `SESSION_SECRET_KEY` required (D-031) |
| KI-012 | HR could not edit/correct an attendance record | 2026-10-06 s5 | Correction requests + HR direct edit (D-033) |
| KI-027 | Redesign Part 2 pending (10 pages on the dark-mode legacy bridge) | 2026-10-06 s5 | All 10 pages redesigned; bridge + legacy aliases deleted; axe clean light+dark (D-040) |
| KI-028 | Pagination not browser-verified | 2026-10-06 s5 | Attendance → Records (276 rows, 25/page) at 1440 + 390 px: range text, `offset` API calls, Prev/Next by mouse + keyboard, last page |
| KI-029 | Managers could not ask for team rankings in chat | 2026-10-06 s5 | Team-scoped rankings, owner-approved (D-032) |
| R-010 | Chat "What is my leave balance?" → "not available in the provided context" | 2026-10-05 s2 | LEAVE tool now includes the Python-calculated balance |
| R-011 | 390 px: tables widened the page (sr-only `position:absolute` header escaped `overflow-x-auto`) | 2026-10-05 s2 | Scroll containers made `relative` |
| R-012 | 1400 px: admin menu hid "AI Assistant"/"Settings" off-screen with no cue | 2026-10-05 s2 | D-025 breakpoints + scroll arrows |
| R-013 | Profile header: name text drawn over the navy banner | 2026-10-05 s2 | Name block starts below the banner |
| R-014 | My Profile showed "Reporting manager #492" (`/employees/me` lacked `manager_name`) | 2026-10-05 s2 | `/employees/me` returns the detail schema |
| R-015 | Employee form allowed empty department/designation/date → API 422; PUT with nulls → 500 risk | 2026-10-05 s2 | Client validation + API ignores nulls for NOT NULL fields |
| R-016 | Admin/HR saw a "Deactivate" button on their own row (API refuses) | 2026-10-05 s2 | Hidden on own row |
| R-017 | Phone dashboard stat labels truncated; leave-balance card said "Current calendar year" for 2024 data | 2026-10-05 s2 | Labels wrap (2 lines); subtitle shows the actual year |
| R-018 | Test suite wiped demo data, uploaded documents and chat logs | 2026-10-05 s2 | D-023 |
| R-019 | Chat "What is the total payroll for September 2024?" (HR) → 500 `TypeError` (router read non-existent summary keys) | 2026-10-06 | Correct keys; payroll summary covered by `test_question_bank.py` |
| R-020 | "What is another employee's salary?" (PRD demo 2) / "Show all salaries" answered with the caller's own salary | 2026-10-06 | Refused for non-HR roles (D-030) |
| R-021 | "What is my attendance this month?" / "…most overtime this month?" (PRD demos 1, 4) answered with all-time totals | 2026-10-06 | `resolve_period` (D-029) |
| R-022 | "Who was late the most?", "How many employees are in Engineering?", "Show all employee personal information" → UNKNOWN | 2026-10-06 | Ranking, headcount and directory tools (D-030) |
| R-023 | Chat answered group / employee-ID questions with the caller's own record (HR: "Who is employee 1025?" → own profile; "Show department-wise overtime", "How many employees are on leave today?" → own attendance/leave) | 2026-10-07 | No caller fallback; group tools (D-043) |
| R-024 | Chat: "How much PF was deducted?", "How many hours did Aman work?" → UNKNOWN; "What was the total overtime amount?" → the caller's attendance | 2026-10-07 | SALARY/ATTENDANCE cues + company summary (D-043) |
| R-025 | Chat: LLM failure on a data question labelled `data_verified`; a DB/retrieval failure → 500 without a `chat_logs` row | 2026-10-07 | Confidence `unavailable`, retrieval errors caught and logged (D-043) |
