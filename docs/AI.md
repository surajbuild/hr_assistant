# AI Assistant

> PRD §33 "AI Documentation": prompts, intent classification, tool calling, RAG, guardrails and hallucination
> handling — plus logging, rate limiting, configuration, extension and testing. Answers the review question
> *"How does the AI decide which data source to use?"* (PRD §34). Code: `app/api/chat.py`, `app/ai/*`, `app/rag/*`.
> Architecture overview and the request sequence diagram: [`ARCHITECTURE.md` §5](ARCHITECTURE.md#5-ai-assistant-request-flow).

---

## 1. Design in one paragraph

The assistant is **not** an autonomous agent. A deterministic Python pipeline decides *what* the user is asking
(rule-based intent), *whose* data and *which period* it concerns, checks the permission, and calls an existing service
function ("controlled tool") that queries MySQL and **computes the numbers in Python**. The result is turned into a
short, plain-text **verified context**. Only then is the LLM called — with a system prompt that allows it to answer
**only** from that context. Refusals (prompt injection, permission denied) are produced in Python and the LLM is never
called for them. The LLM therefore never sees the database, never writes SQL (PRD §16), never calculates (PRD §20), and
never receives data the user is not allowed to see.

```
question ─► sanitize ─► injection guardrail ─► classify_intent ─► [POLICY/UNKNOWN: RAG search]
         ─► retrieve_hr_context (target, period, RBAC, service call) ─► denial? ─► LLM(system + context + question)
         ─► chat_logs ─► {answer, intent, source, confidence, page, sources}
```

---

## 2. Prompts

### 2.1 System prompt (`app/ai/prompts.py` -> `SYSTEM_HR_ASSISTANT_PROMPT`)

```text
You are the AI HR Assistant for our company.
Your role is to answer employee and HR inquiries accurately, politely, and concisely based strictly on the provided Context.

STRICT OPERATIONAL RULES:
1. GROUNDING: Answer the user's question using ONLY the provided HR Context or Policy Information.
2. ANTI-HALLUCINATION: Do NOT guess, assume, extrapolate, or invent any information. If the provided context states
   that a record does not exist, an employee was not found, data is unavailable, or access is denied, state that
   directly and clearly to the user.
3. FACTUAL INTEGRITY: Never invent employee names, numbers of days present/absent, late minutes, overtime hours,
   salary numbers, leave balances, or company policies.
4. ROLE & PRIVACY: If the context indicates an authorization or access restriction, communicate the restriction
   clearly without revealing sensitive data.
5. CONCISENESS: Provide a clear, natural, direct answer without conversational filler or unnecessary repetition.
```

### 2.2 User prompt (`build_chat_prompt(question, context, intent)`)

Example (numbers illustrative):

```text
Detected Intent: ATTENDANCE
--- HR CONTEXT (VERIFIED DATA) ---
Attendance summary for Aman Gupta (EMP004) for August 2024:
- Total Days Recorded: 24
- Present Days: 22
...
-----------------------------------

User Question: How many days was Aman present in August 2024?

Please provide a clear and direct answer using only the verified context above.
```

For `POLICY` questions `app/api/chat.py` appends:
`If the excerpts do not contain the answer, reply exactly: "I could not find this information in the available HR documents."`
(PRD §19, D-009).

### 2.3 How the context is built

The context is plain text assembled by `app/ai/router.py` from service results — never raw rows:

| Data | Context format (excerpt) |
|---|---|
| Attendance | `Attendance summary for <name> (<code>) for <period>:` + total / present / absent / half / leave days, late clock-ins, overtime days, `Total Overtime: 1115 minutes (18 hours 35 minutes)`, total working minutes |
| Ranking | `Employees ranked by overtime for September 2024, company-wide (calculated by the HR system; equal values share a rank):` + `1. Rahul Sharma (EMP005, Engineering): total overtime ...` |
| Leave | `Leave balance for <name> ... for calendar year <y> (working days; calculated by the HR system):` + per type `entitled / used / pending approval / remaining`, then each application with working days and status |
| Salary | `Salary records for <name> (<code>):` + per month `Gross / PF / Deductions / Overtime Amount / Net` in ₹ |
| Payroll summary | `Company Payroll Summary for <period>:` record count, totals of gross, PF, deductions, overtime, net |
| Headcount | `Department headcount from the HR system (company-wide | limited to you and your direct reports):` |
| Profile | code, name, department, designation, joining date, status, reporting manager |
| Documents (RAG) | `The following excerpts were retrieved from the company's uploaded HR documents. Answer only from them and mention the document name you used.` + `[Source i: <document> (<file>, page n)]` blocks |
| Policy fallback | the matching JSON section of `app/data/policies.json` |
| Holidays | `Company holiday calendar for <year> (from the HR system):` + date, weekday, name, `[national|company]` |
| Assumptions | a `Note:` line, e.g. `Note: there are no records yet for October 2026; the figures are for September 2026, the most recent month with data.` |

LLM call parameters (`app/ai/llm.py`): `messages = [system, user]`, `temperature = 0.2`, `max_tokens = 500`.

---

## 3. Intent classification

`router.classify_intent(question)` lowercases the question and tests **regex groups in a fixed order**; the first group
with a match wins. Order matters: *"What is the leave policy?"* contains both "leave" and "policy" and must be POLICY.

| # | Intent | Example patterns (word-bounded regexes) | Why this position |
|---|---|---|---|
| 1 | `POLICY` | policy/policies, rule(s), guideline(s), handbook, working/office hours, office timing, shift time, grace period, lunch break, public/national holiday, holiday list/calendar, upcoming holidays, "which/what are the company holidays", annual leave entitlement, entitled to, "how many leaves are allowed" | Rule questions mention leave/attendance words too |
| 2 | `SALARY` | salary/salaries, payslip, pay slip, payroll, compensation, ctc, pf, provident fund, overtime/ot amount/pay/payment/paid, net/gross pay, net/gross salary, deductions, allowance(s), wage, earnings, "how much do I earn", "how much does X earn" | Most sensitive data — must not be mis-routed to a weaker rule |
| 3 | `ATTENDANCE` | attendance, present, absent, absences, clock in/out, late, latecomer(s), late entry/arrival/mark, overtime, ot hours, working minutes, hours worked, "hours … work(ed)", days present/absent, "was X present", "who worked the highest overtime" | |
| 4 | `LEAVE` | leave(s), sick/casual/earned leave, time off, pto, vacation, leave balance/status/history, my leaves | |
| 5 | `EMPLOYEE` | designation, department(s), manager, reporting/reports to, who is, employee code, joining date, joined, profile, team member, all employees, list employees, employee directory, personal information, how many employees/people/staff, headcount | |
| 6 | `GENERAL` | starts with hi/hello/hey, who are you, what can you do, help, good morning/afternoon, thanks | |
| 7 | `UNKNOWN` | nothing matched | |

**UNKNOWN -> RAG re-route (D-009):** for `UNKNOWN` (and `POLICY`) questions the chat endpoint first searches the uploaded
documents. If a chunk passes the relevance thresholds, the intent becomes `POLICY` and the answer is document-grounded —
this is how *"How many days can I work from home?"* (no keyword) is answered from "Work From Home Policy.txt". An
`UNKNOWN` question without a document hit gets an "outside the scope of company HR" context and the LLM politely
declines (`source = general`).

**Why rules and not an LLM classifier:** deterministic, free, instant, unit-testable, and a misclassification can never
bypass a permission check (every branch applies its own RBAC). Limitation: unusual wording may be missed (KI-008); the
fix path is a failing case in `tests/test_question_bank.py` first, then a pattern.

### 3.1 Entity extraction

| Entity | Function | Rules |
|---|---|---|
| Target employee | `find_target_employee(db, question, user)` -> `(employee, is_other, note)` | **D-043 — the caller's own record is never a fallback.** 1) `find_named_employee`: employee code substring (`EMP004`), employee ID ("employee 4", "employee ID 4", "emp #4" = the number of the code, EMP004 = 4), or first / full name -> that employee; a code or ID that matches nobody -> unknown person; 2) "another employee", "someone else", "a colleague", "co-worker", "peer" -> *unnamed other*; 3) a group (team, members, reports, employees, staff, people, everyone, company, departments, department-wise, or a department name from the data) -> no target (group); 4) self words (my, me, I, mine, myself) -> the caller; 5) "of / for / about / who is / was / regarding / does <Capitalised Name>" not a stopword -> unknown person; 6) nothing named: role `employee` and no aggregate word (total, average, most, who, which, …) -> the caller **with a note the answer must state** ("no person was named, so these are your records"); every other case -> **no target -> clarification** (`Clarification needed: …`, no records loaded). |
| Month / year | `extract_month_and_year` | Full or short month names (`sep`, `sept`); "may" only counts after in/of/for/during/since/until/from/to or before a year (so "May I…" is not May); year = first `20xx`. A missing part is `None`. |
| Period | `resolve_period`, `resolve_date_range` | See §5. |
| Group question | `refers_to_group`, `named_departments`, `_parse_threshold` | "more than / over / above / at least / >= N [hours|minutes]", "N or more"; overtime thresholds are hours unless "minutes" is written. |
| Ranking metric | `detect_ranking_metric` | "most/highest/top … overtime", "late the most", "latecomers", "absent the most" -> `overtime` / `late` / `absent`. |

---

## 4. Tool calling (controlled tools)

"Tool calling" here means: **the router calls a fixed, reviewed Python service function per question type**. The LLM
does not choose tools and cannot pass arguments; it never generates SQL. Every tool returns
`(context, data_source, denial_or_None)` from `router.retrieve_hr_context` (or `retrieve_policy_context` for documents).

| Question type (intent -> branch) | Service function(s) called | Roles allowed | Data returned to the LLM |
|---|---|---|---|
| Policy from documents (POLICY, or UNKNOWN with a hit) | `app.rag.retriever.search` | all | top 4 chunks + document/file/page |
| Policy fallback (POLICY, no document hit) | `router.load_policies` (`app/data/policies.json`) | all | matching section (leave / working hours / overtime / attendance rules / holidays) or the whole file |
| Holiday calendar (any POLICY question containing "holiday") | `holiday_service.list_holidays(year)` | all | national + declared holidays of the named year (default: current) |
| Company payroll ("total payroll", "all salaries", "total PF", "total overtime amount", "payroll for 2024" with nobody named; not for one department) | `salary_service.get_salary_summary`, `get_latest_payroll_period` | `hr`, `admin` (others: denied) | totals only (gross, PF, other deductions, overtime paid, net) — never a per-person table (AGENTS.md §3.6, D-030) |
| One person's salary / payslip / PF / overtime amount | `salary_service.get_salary_for_employee` (+ month/year filter) | self; `hr`, `admin` for anyone. **Managers and employees: never another person** | gross, PF, deductions, overtime amount, net per month + a Python-computed totals line when several months are listed |
| Ranking: most overtime / late / absent | `attendance_service.rank_employees(metric, period, scope_ids, limit=5)` | `hr`, `admin` company-wide; `manager` self + direct reports (D-032); "my team" -> self + direct reports for any role; `employee` denied | top 5, ties share a rank |
| Threshold / list: "employees with more than 5 late entries", "more than 10 hours overtime", "which members of my team worked overtime last week", "who was absent yesterday" | `attendance_service.rank_employees(..., limit=None)` + threshold filter | same as rankings | count + every matching employee with the figure; "No employees had …" when none |
| Department-wise overtime | `attendance_service.get_overtime_by_department(period, scope_ids)` | same as rankings | per department: total overtime, employees with overtime / with records; total |
| Who is on leave today / yesterday / tomorrow | `leave_service.get_employees_on_leave(date, scope_ids)` (approved leave covering the date — the dashboard rule) | `hr`, `admin` company-wide; `manager` own team; `employee` denied | count + name, type and dates per employee |
| One person's attendance | `attendance_service.get_attendance_summary(employee, start, end)`, `attendance_service.attendance_percentage` | self; manager for direct reports; `hr`, `admin` for anyone | day counts, late days, overtime, working minutes, **hours worked**, **attendance %** (present + 0.5 × half days ÷ recorded working days; weekends/holidays excluded, leave and absence count as not attended) |
| One person's leave | `leave_service.get_leave_balance(year)`, `leave_service.get_leave_days_in_range` (when a period is asked), `leave_service.get_leaves_for_employee`, `leave_service.count_leave_days` + `holiday_service.get_declared_holiday_dates` | self; manager for direct reports; `hr`, `admin` | balance per type (working days), leave taken in the asked period, application history |
| Department headcount | `employee_service.list_departments(scope_ids)` | `hr`, `admin` company-wide; `manager` own team; `employee` denied (same as `GET /departments`) | per department: count, active, managers; total |
| Employee directory / "all employees' personal information" | `employee_service.get_all_employees` | `hr`, `admin` (others: denied) | code, name, department, designation |
| One person's profile | `find_target_employee` result | self: all roles; others: HR/Admin any, manager direct reports, employee refused (D-039, below) | code, name, department, designation, joining date, status, manager — no salary, email or role |
| Greeting / capabilities (GENERAL) | — | all | fixed capability description |
| Out of scope (UNKNOWN, no document hit) | — | all | fixed "outside the scope" instruction |

**Unnamed other person (D-030):** "What is another employee's salary?" -> refused for every role that may not see other
people's salary (everyone except HR/Admin); "another employee's attendance/leave" -> refused for employees; for roles that
*could* see it, the context tells the LLM to ask which employee is meant instead of guessing.

**No target, or an unsupported group question (D-043):** "How many days present in August?" asked by HR, or "Show the
attendance of the Engineering department" (no tool for that) -> no records are loaded; the context starts with
`Clarification needed:` and tells the LLM to ask whose records are meant / to suggest a supported group question;
confidence `clarification_needed`. Roles that may not see that data for others (employees; salary: everyone but HR/Admin)
get the usual access-denied refusal instead.

**Calculations stay in Python (PRD §20):** attendance counts are SQL aggregates; late/overtime minutes come from
`attendance_service.calculate_day_metrics` (D-007); leave days are working days excluding weekends and holidays (D-008,
D-034); payroll figures come from the payroll engine (D-021); minutes are pre-converted to hours in the context
(`1115 minutes (18 hours 35 minutes)`) so the LLM does not need to divide.

**Profiles of other people (D-039):** the profile tool applies `check_rbac_access` with the same rule as
`GET /employees/{id}` — HR/Admin anyone, managers their direct reports, employees only themselves. *"Who is Rahul?"* asked
by an employee is refused before the LLM is called (question bank C15–C18).

---

## 5. Period resolution (D-029)

`router.resolve_period(db, question, source)` returns `(month, year, note)`; `source="salary"` uses payroll months
(`salary_service.get_payroll_periods`), otherwise attendance months (`attendance_service.get_months_with_data`).

| Question says | Resolved period | Note added to the context |
|---|---|---|
| "August 2024" | Aug 2024 | — |
| "September" (no year) | the most recent September (not in the future) **that has records**; none -> most recent past September by calendar | `Note: no year was given, so the most recent September (2026) is used.` |
| "this month" / "current month" | the current month; if it has no records yet, the latest month with data | `Note: there are no records yet for October 2026; the figures are for September 2026, ...` |
| "last month" / "previous month" | previous calendar month | — |
| "2024" | the whole year | — |
| nothing | all recorded dates (company payroll summary: latest payroll month, with a note) | payroll only |

`router.resolve_date_range(db, question, source)` (attendance questions, rankings, thresholds, department overtime, leave
taken) adds day/week ranges before falling back to `resolve_period`: "today", "yesterday", "this week" (Monday -> today),
"last/previous/past week" (the previous Monday -> Sunday); the label carries the dates (`last week (2026-09-28 to 2026-10-04)`).

Leave balances use the calendar year (written year, else the current year). "Leave taken this month / last week" uses the
calendar (`source="leave"`: "this month" is always the current month).

---

## 6. Guardrails

Applied in this order in `POST /chat`:

| # | Guardrail | Code | Behaviour |
|---|---|---|---|
| 1 | Authentication | `get_current_user` | No/invalid token -> 401; inactive user -> 403 |
| 2 | Rate limit | `rate_limit.enforce(chat_limiter, "user:<id>")` | > 20 messages/min per user -> 429 (not logged, LLM not called) — D-031 |
| 3 | Input sanitising | Pydantic `max_length=1000` (422), `sanitize_question` (strip NUL bytes, trim, clamp 1000) | Blank -> 400 |
| 4 | **Prompt-injection filter** | `guardrails.detect_prompt_injection` | Runs **before** intent detection for **every role**. Regexes for: instruction override ("ignore / disregard / forget / override / bypass / skip … instructions / rules / guardrails / prompt / restrictions / policies / permissions"; "previous/system instructions … ignore"), role-play ("you are now", "pretend to be", "act as admin/hr/root/developer"), privilege escalation ("give / grant / make / elevate me … admin / hr / root / full … access / rights / role / privileges"), prompt extraction ("reveal / show / print / repeat / leak … system prompt / your instructions"), jailbreak keywords ("jailbreak", "developer mode", "DAN mode", "sudo mode", "god mode"), SQL ("drop / delete / truncate / alter / update table", "select … from <word>", `; --`). On a match: fixed refusal `I can't help with that request. I only answer HR questions using the data your role is permitted to access, and I can't change my instructions or your permissions.`, intent `UNKNOWN`, source `guardrail`, confidence `access_denied`, log error `PROMPT_INJECTION_BLOCKED`. **No data is read and the LLM is not called** (D-011). |
| 5 | **RBAC before data** | `guardrails.check_rbac_access` + role checks in each router branch | Self -> allowed. HR/Admin -> allowed. Manager -> attendance / leave / profile of direct reports only; **salary of others never**. Employee -> others' salary / leave / attendance denied. Company payroll, directory: HR/Admin only. Rankings, headcount: HR/Admin, managers scoped to their team. A denial returns `Access denied: ...` as the answer, source = the data source, confidence `access_denied`, log error `RBAC_ACCESS_DENIED`, **LLM not called** — the denied data was never loaded. |
| 6 | Salary confidentiality | SALARY branch | Per-person salary only for self or HR/Admin; company questions return totals only, never a per-person table. |
| 7 | Grounded generation | system prompt §2.1 | The LLM may only use the verified context. |
| 8 | Failure safety | `chat.py` | Retrieval / database failure (document search, any router tool) -> session rolled back, `I could not retrieve the HR data needed to answer this right now. Please try again later.`, source `error`, **LLM not called**, log error `RETRIEVAL_ERROR: <type>: <message>`. `LLMError` -> `The AI service is temporarily unavailable. Please try again.` (D-015); any other exception in the LLM call -> `An unexpected error occurred while processing your request.`. All three: confidence `unavailable` (never `data_verified`), logged with the error text. A failing log write (e.g. the database itself is down) never breaks the response. |

Because the permission check happens in Python on data the LLM has not seen, even a successful prompt injection that
slipped past the regexes could not make the model reveal another person's salary: it is simply not in its context.

---

## 7. RAG

Full pipeline (upload -> parse -> chunk -> term vectors -> BM25 -> sources) and the reasons for lexical retrieval:
[`ARCHITECTURE.md` §6](ARCHITECTURE.md#6-rag-documents---answers). Chat-specific behaviour:

- **When it runs:** for `POLICY` and `UNKNOWN` intents only, before any database tool. A hit overrides the
  `policies.json` fallback (uploaded documents are the company's current truth; D-009).
- **Search:** `retriever.search(db, question)` over chunks of `active` documents (archived / failed / processing are
  excluded), Okapi BM25 (`k1 = 1.5`, `b = 0.75`), relevance gate: ≥ 34 % of distinct query terms present **and**
  (score ≥ 1.0 **or** ≥ 50 % of terms with ≥ 2 matches), top 4.
- **Context:** numbered excerpts with document name, file name and page, plus the holiday calendar when the question
  mentions holidays.
- **Response:** `source` = file name of the best chunk (e.g. `Work From Home Policy.txt`), `page` = its page (PDF only),
  `sources[]` = every chunk used `{document, file_name, page, score}`, `confidence = document_grounded`. The chat UI shows
  these as chips.
- **No hit:** `policies.json` section, `source = policies.json`, `confidence = policy_reference`.

---

## 8. Hallucination handling

| Technique | Where |
|---|---|
| The LLM gets only verified, permission-checked context; it has no tools, no DB, no browsing | `router.py`, `chat.py` |
| Every number is computed in Python and written into the context in its final form (units, hours/minutes, ₹) | services + `router.py` |
| Missing data is stated explicitly instead of leaving a gap the model might fill: `No employee record found for the requested name.`, `No attendance records found for <name> (<code>) for <period>. Attendance data is not available for the requested period.`, `No salary records found for <name> for <period>.`, `No overtime records found for <period> (...)` | `router.py` (PRD §29) |
| Assumptions are disclosed with a `Note:` line (which month was used) | `resolve_period` |
| Ambiguous person -> the model is told to ask which employee is meant "instead of guessing" | `_missing_target_response` |
| Document questions: exact fallback sentence `I could not find this information in the available HR documents.` | `chat.py` (PRD §19) |
| System prompt rules: grounding, no guessing, never invent names/numbers/policies | `prompts.py` |
| Low temperature `0.2`, `max_tokens = 500` | `llm.py` |
| Source, page and confidence returned with every answer so the user can verify | `ChatResponse` |

### Confidence values (`chat._confidence`)

`confidence` is a **deterministic label describing where the context came from**, not a model probability:

| Value | Rule (checked in this order) |
|---|---|
| `unavailable` | no answer was produced: data retrieval failed, or the LLM call failed (`LLMError` or another exception) |
| `access_denied` | prompt injection blocked, or RBAC denial |
| `not_found` | the LLM answered with the exact "I could not find this information…" sentence (KI-035) |
| `document_grounded` | context from uploaded documents (`data_source == "document_rag"`) |
| `policy_reference` | context from `policies.json` |
| `general` | GENERAL or out-of-scope UNKNOWN question |
| `clarification_needed` | the context starts with `Clarification needed:` — nobody / no supported group could be identified, so nothing was retrieved (D-043) |
| `not_found` | the database context starts with "No " or contains "not found" / "no employee record" (e.g. unknown person or employee ID, empty period, "No employees had more than 5 late entries") |
| `data_verified` | anything else — numbers computed from MySQL |

**Known gap:** the LLM's answer is not post-checked against the context (a model could still mis-copy a number).

---

## 9. Logging

Every `POST /chat` that passes authentication, the rate limit and input validation writes one `chat_logs` row (PRD §28),
including refusals and LLM failures:

| Column | Value |
|---|---|
| `user_id` | caller |
| `question` | the question as sent (before sanitising) |
| `detected_intent` | final intent (`POLICY` after an UNKNOWN re-route; `UNKNOWN` for blocked injections) |
| `data_source` | RAG: file name of the best chunk; otherwise `guardrail`, `attendance_database`, `salary_database`, `leave_database`, `employee_database`, `policies.json`, `general`, or `error` (retrieval failed) |
| `response` | the answer returned (refusal text for denials) |
| `timestamp` | server time (DB default) |
| `response_time_ms` | from after the rate-limit check to just before logging (includes the LLM call) |
| `error` | `PROMPT_INJECTION_BLOCKED`, `RBAC_ACCESS_DENIED`, `RETRIEVAL_ERROR: <type>: <message>`, the LLM error text, `Unexpected error: ...`, or `NULL` |

A retrieval failure rolls the session back before the log row is written, so a failed query no longer turns into a 500
without a log row. Only when the database itself is unreachable can the log write fail too (a warning is printed; the user
still gets the "could not retrieve" answer).

Reading the log: `GET /chat/history` (own last N, used by the chat page) and `GET /chat/logs` (admin audit: search by
question or email, `limit`/`offset`, `X-Total-Count`; Settings -> AI audit log). Rows are never deleted by the app.
Requests rejected with 400 / 422 / 429 are not logged.

---

## 10. Rate limiting and configuration

**Rate limit (D-031):** `RATE_LIMIT_CHAT_PER_MINUTE` (default 20) per user, sliding 60 s window, 429 + `Retry-After`,
checked before any work so a flood never reaches the LLM. In-memory per backend process (`RATE_LIMIT_ENABLED=false`
disables it). See [`ARCHITECTURE.md` §7.7](ARCHITECTURE.md#77-rate-limiting-d-031).

**LLM configuration** (`app/ai/llm.py`, read on every call from the process environment, falling back to `.env`):

| Variable | Default in code | Purpose |
|---|---|---|
| `LLM_API_KEY` | — (required) | Bearer key for the provider. Missing -> every allowed question answers "The AI service is temporarily unavailable." and logs the configuration error. |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint; the client posts to `<base>/chat/completions`. |
| `LLM_MODEL` | `openai/gpt-4o-mini` | Model name as the provider expects it (OpenRouter: `vendor/model`; OpenAI directly: `gpt-4o-mini`). |
| `LLM_TIMEOUT` | `30.0` seconds | httpx timeout. |

The request also sends `HTTP-Referer: http://localhost:8000` and `X-Title: AI HR Assistant` (OpenRouter attribution
headers; ignored by other providers). Environment variables are loaded from `.env` at start-up — restart the backend
after changing them. RAG has no configuration besides `DOCUMENTS_DIR` (upload folder); its thresholds are constants in
`app/rag/retriever.py` and `app/rag/chunker.py`.

---

## 11. Testing

The LLM is **always mocked** in tests (`unittest.mock.patch("app.api.chat.generate_response")`); assertions look at the
verified context the router passed to the mock (that is where the numbers come from) and at whether the mock was called.

| Test file | What it covers |
|---|---|
| `tests/test_question_bank.py` | **PRD §30 question bank** through `POST /chat`: **[A] 23 normal** questions (every role and intent, holiday calendar), **[B] 11 incorrect** (unknown people, empty periods, off-topic, gibberish, blank), **[C] 14 permission/security** (prompt injection, other people's salary/attendance, directory, rankings, manager rankings limited to the team — D-032), **[D] 14 calculation** (expected numbers computed independently from MySQL in the test), **[F] 21 PRD capability** questions (thresholds on late entries / overtime hours / minutes, department-wise overtime, on leave today, "which members of my team worked overtime last week", PF, overtime amount, hours worked, attendance %, employee ID lookup, leave taken this month — expected numbers again from raw SQL), **[G] 13 no-substitution regressions + 8 direct `find_target_employee` checks** (ambiguous / group / department questions never return the caller's record — D-043), **[E] 11 RAG** (PDF with pages, DOCX, TXT upload -> answer + source; archive; new version). Refusals are checked with "LLM not called", not just the answer text. |
| `tests/test_ai_router.py` | `classify_intent`, `extract_month_and_year`, `find_target_employee`, `retrieve_hr_context` |
| `tests/test_chat_api.py` | 401, blank input 400, grounding, RBAC isolation, policies.json context, missing records, provider failure, chat logging; **[10] failures**: LLM failure / unexpected error / DB failure / document-search failure -> confidence `unavailable`, LLM not called after a retrieval failure, `chat_logs` row with the error |
| `tests/test_rag.py` | chunker/embeddings, upload validation + RBAC, BM25 thresholds, document-grounded chat with source/page, injection refusal, archive, versioning |
| `tests/test_llm.py` | LLM client configuration and error handling |
| `tests/test_security_hardening.py` | secrets, rate limiter, trusted-proxy IP, login and chat 429 (blocked message reaches neither the LLM nor `chat_logs`) |

Chat tests use `tests/helpers.TrackingClient`, which deletes exactly the `chat_logs` rows they caused (D-023). Run:
`python scripts/run_tests.py question_bank rag chat ai_router`. Manual end-to-end check with the real LLM:
`python scripts/smoke_test_chat.py` (logs in to the backend running on `127.0.0.1:8000` with demo accounts and calls
the real provider; not part of the test suite).

---

## 12. How to extend (add a new question type / tool)

1. **Write the failing case first** in `tests/test_question_bank.py` (right category; expected numbers derived from the
   database, never hard-coded demo counts; for refusals assert `llm: False` and `confidence: access_denied`).
2. **Service function:** reuse or add a framework-free function in `app/services/` that does the query and the
   calculation and accepts a scope (`scope_ids` from `employee_service.get_scope_employee_ids`). If the same data has a
   REST endpoint, use the **same** function and the **same** permission rule.
3. **Router:** add patterns to `classify_intent` (mind the order of §3) or a sub-detector inside an intent branch (like
   `detect_ranking_metric`). In `retrieve_hr_context`, resolve target and period, apply the permission check
   (`check_rbac_access` or an explicit role check) **before** calling the service, and return
   `(context, data_source, denial)`. Put final numbers with units in the context; say explicitly when nothing was found.
4. **New data source label?** Use an existing one if possible; otherwise check `_confidence` in `app/api/chat.py`.
5. **Permissions:** never widen access without the product owner (AGENTS.md §8) and record the decision in
   `PROJECT_DECISIONS.md` (example: team rankings for managers, D-032).
6. Run `python scripts/run_tests.py question_bank chat ai_router rag`, then update this document.
