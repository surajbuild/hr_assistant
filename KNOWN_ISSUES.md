# KNOWN_ISSUES.md

> Every significant known problem, so nobody wastes time rediscovering it. Update the status instead of deleting entries;
> move fixed issues to the "Resolved" section with the date.

Severity: 🔴 high · 🟠 medium · 🟡 low

| ID | Issue | Severity | Area | Status |
|---|---|---|---|---|
| KI-001 | Demo data goes stale every month (dashboard falls back to the last date with data) | 🟡 | Seed / Dashboard | Mitigated — run `scripts/generate_demo_month.py` monthly (D-024) |
| KI-002 | Tests run against the dev database (no separate test DB) | 🟡 | Tests | Mitigated — tests leave it byte-identical (D-023); separate DB still P2 |
| KI-003 | JWT secret in local `.env` is shorter than 32 bytes (PyJWT warning) | 🟠 | Security | Open |
| KI-004 | Google OAuth browser flow not verified with a real Google account | 🟡 | Auth | Partially tested (token hand-off `#token=` verified in browser) |
| KI-005 | Bun dev server can't resolve **new** files imported via the `@/` alias until restarted | 🟡 | Frontend DX | Root cause found — restart `bun dev` after adding a file |
| KI-006 | Frontend bundle ≈ 780 KB minified, no code-splitting | 🟡 | Frontend perf | Open |
| KI-007 | No pagination on list endpoints/tables | 🟡 | API / UI | Open |
| KI-008 | Rule-based intent router misses some phrasings; month without year defaults to 2024 | 🟠 | AI | Open |
| KI-009 | Scanned/image-only PDFs cannot be indexed (no OCR) | 🟡 | RAG | Open |
| KI-010 | Lexical RAG: synonyms ("remote work" vs "work from home") may not match | 🟠 | RAG | Open |
| KI-011 | `SessionMiddleware` falls back to a hard-coded secret if env vars are missing | 🟠 | Security | Open |
| KI-012 | HR cannot edit/correct an existing attendance record (create only) | 🟡 | Attendance | Open |
| KI-013 | Settings → "Company Policy" tab shows hard-coded values duplicated from `policies.json` | 🟡 | Frontend | Open |
| KI-017 | `httpx2` in requirements looks odd but is imported by Starlette's TestClient here | 🟡 | Dependencies | Documented |
| KI-018 | Clickable table rows are not keyboard-focusable (row action buttons are) | 🟡 | Accessibility | Fixed in `DataTable` (rows with `onRowClick` are focusable, Enter/Space activate) — verified on Employees; other tables get it automatically |
| KI-019 | Check-in/out uses the server's local clock; no timezone setting | 🟡 | Attendance | Open |
| KI-021 | Manager `/leaves` list includes the manager's own leaves | 🟡 | Leave | Mitigated (UI hides actions + explains, API 403 — D-022) |
| KI-022 | `uvicorn --reload` never restarts its worker when launched from a console-less shell (agent tools) | 🟡 | Dev tooling | Workaround |
| KI-023 | Payroll: working days without any attendance record are paid (not LOP) | 🟡 | Payroll | By design (D-021) — revisit with HR |
| KI-024 | Payroll for the current month is provisional and changes as attendance is recorded | 🟡 | Payroll | By design (flagged `provisional` in API + UI) |
| KI-025 | Orphan files stay in `documents/` after a manual seed reset or archive | 🟡 | Documents | Open |
| KI-027 | Redesign Part 2 pending: 10 pages still use their original layout inside the new shell (restyled via shared components + dark-mode legacy bridge, D-028); some wide tables scroll inside their card at 1280–1440px (sidebar takes 248px) | 🟠 | Frontend | Open — Part 2 (`frontend/REDESIGN_NOTES.md` §4–5) |
| KI-028 | `DataTable`/card pagination is not browser-verified (demo data < page size) | 🟡 | Frontend | Open — verify in Part 2 |
| KI-026 | `test_rag.py` chat-source check passes for either the test or the real "Work From Home Policy.txt" (same file name) | 🟡 | Tests | Open |

---

## Details

### KI-027 / KI-028 — Redesign Part 1 leftovers
- See `frontend/REDESIGN_NOTES.md` §5 for the full list (legacy bridge, wide tables beside the sidebar, ChatPage `bg-navy` chips in dark mode, pagination unverified, check-in POSTs not exercised).

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

### KI-003 — Short JWT secret
- **Symptom:** `InsecureKeyLengthWarning: The HMAC key is 12 bytes long`.
- **Fix:** Set a ≥ 32-byte random `JWT_SECRET_KEY` in `.env` (`python -c "import secrets;print(secrets.token_urlsafe(48))"`).
  Changing it logs everyone out.

### KI-004 — Google OAuth flow
- The SPA button calls `http://localhost:8000/auth/google/login?next=frontend`; the callback redirects to
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
  unusual wording may get a generic answer. `extract_month_and_year` defaults the year to **2024** when only a month is
  given (demo dataset). **Proposed:** default year = latest year with data; LLM-assisted entity extraction fallback (P2).

### KI-010 — Lexical retrieval
- BM25 matches stemmed words, not meaning. **Proposed:** synonym map for common HR terms, or dense embeddings
  (replace `app/rag/embeddings.py` + `retriever.py`; schema unchanged).

### KI-011 — Session secret fallback
- `app/main.py` uses `SESSION_SECRET_KEY` → `JWT_SECRET_KEY` → `"default-session-secret-key"`. **Proposed:** fail fast.

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
- Unrecorded working days are paid; only recorded absences, half days and approved unpaid leave reduce pay (D-021).
  Generating the current month marks the result `provisional`. Paid rows (`paid_at`) are locked; there is no
  "mark as paid" action in the UI yet (P2).

### KI-025 — Orphan files in `documents/`
- `scripts/seed_db.py` reset and archive keep stored files for audit. **Proposed:** an admin "purge archived files" task.

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
| R-010 | Chat "What is my leave balance?" → "not available in the provided context" | 2026-10-05 s2 | LEAVE tool now includes the Python-calculated balance |
| R-011 | 390 px: tables widened the page (sr-only `position:absolute` header escaped `overflow-x-auto`) | 2026-10-05 s2 | Scroll containers made `relative` |
| R-012 | 1400 px: admin menu hid "AI Assistant"/"Settings" off-screen with no cue | 2026-10-05 s2 | D-025 breakpoints + scroll arrows |
| R-013 | Profile header: name text drawn over the navy banner | 2026-10-05 s2 | Name block starts below the banner |
| R-014 | My Profile showed "Reporting manager #492" (`/employees/me` lacked `manager_name`) | 2026-10-05 s2 | `/employees/me` returns the detail schema |
| R-015 | Employee form allowed empty department/designation/date → API 422; PUT with nulls → 500 risk | 2026-10-05 s2 | Client validation + API ignores nulls for NOT NULL fields |
| R-016 | Admin/HR saw a "Deactivate" button on their own row (API refuses) | 2026-10-05 s2 | Hidden on own row |
| R-017 | Phone dashboard stat labels truncated; leave-balance card said "Current calendar year" for 2024 data | 2026-10-05 s2 | Labels wrap (2 lines); subtitle shows the actual year |
| R-018 | Test suite wiped demo data, uploaded documents and chat logs | 2026-10-05 s2 | D-023 |
