# REDESIGN_NOTES.md — working notes for the frontend redesign

> Persistent memory for the multi-session redesign (Part 1 = foundation + Login/Dashboard/Employees; Part 2 = the other
> 10 pages + quality pass). Written in Part 1 (2026-10-05) so Part 2 starts with the full audit. Design rules: `DESIGN.md`.
> Decision log: `PROJECT_DECISIONS.md` D-026 (design), D-027 (dependencies), D-028 (legacy bridge).

## 0. Status

| Item | State |
|---|---|
| Phase A — tokens, dark mode, primitives, shell, palette | ✅ done, browser-verified |
| Phase B — Login, Dashboard (4 role layouts), Employees | ✅ done, browser-verified at 1440/1024/390, light + dark |
| **Checkpoint** | ⏸ **waiting for the owner's approval of the direction** before Part 2 |
| Phase C — remaining 10 pages | 🔴 not started (they already render inside the new shell, restyled through shared components + the legacy bridge) |
| Phase D — quality pass + docs finalisation | 🔴 not started |

Screenshots (git-ignored, on disk): `frontend/.redesign/before/` (original design, 90 shots: 4 roles × 14 routes × 1440/390
+ login), `frontend/.redesign/after-part1/` (Login, Dashboard, Employees pages × roles × 1440/1024/390 × light/dark),
`frontend/.redesign/qa-part1/` (every route × role × 1440/1024/390 from `scripts/ui_qa.py`, light). Capture script: see §6.

## 1. Page audit (all 13 pages)

Roles: **E** employee, **M** manager, **H** hr, **A** admin. "Redesigned" = rebuilt in Part 1; otherwise the page still has
its original structure and only inherits the new shell/tokens/shared components.

| # | Route · file | Roles | API calls (reads) | Mutations | States today | Key actions / notes | Redesigned |
|---|---|---|---|---|---|---|---|
| 1 | `/login` · `LoginPage` | public | — | `POST /auth/login` (via `AuthProvider.login`); Google = redirect to `GOOGLE_LOGIN_URL` (backend, `?next=frontend`) | inline field errors, error banner, loading button | email/password, show/hide, generic error "Invalid email or password.", demo chips (fill email, focus password; password is typed — not hard-coded) | ✅ Part 1 |
| 2 | `/dashboard` · `DashboardPage` + `pages/dashboard/*` | all (4 layouts) | A/H: `/dashboard/summary`, `/attendance/records?from_date&to_date` (month of reference date), `/leaves?status=pending`; H: `/salary`; A: `/users`, `/chat/logs?limit=100`; M/E: `/dashboard/me`; E: `/attendance/me`; M: `/leaves?status=pending`; hero: `/attendance/today` | check-in/out (`POST /attendance/check-in\|check-out`) from the hero card | skeletons per region, empty + error with retry in each widget | greeting wording unchanged (Admin/HR/Manager/"Welcome back, <first name>!"); fallback-date notice; refresh | ✅ Part 1 |
| 3 | `/employees` · `EmployeesPage` | A H M | `/employees?search&department&status` (manager → team), `/departments` | `DELETE /employees/{id}` (soft, confirm) | skeleton, empty (filtered vs none, with action), error+retry | filters synced to URL; table⇄card (saved `hr_employees_view`); sort; pagination (10 table / 12 cards); row menu; CSV export; no deactivate on own row; manager has no edit/deactivate/add | ✅ Part 1 |
| 4 | `/employees/add`, `/employees/:id/edit` · `EmployeeFormPage` | A H | `/employees/{id}` (edit), `/employees` (manager list), `/departments` | `POST /employees`, `PUT /employees/{id}` | loading/error, client validation (code, name, department, designation, joining date, email/password when creating login) | fields: employee_code, name, department (existing or new), designation, joining_date, status, manager_id, monthly_gross_salary (confidential), optional login (email, password ≥8, role). HR cannot create admin accounts (backend) | 🔴 Part 2 |
| 5 | `/employees/:id`, `/my-profile` · `EmployeeDetailPage` | `:id` A H M (team); `/my-profile` all | `/employees/{id}` or `/employees/me`; tabs: `/attendance/{id}` or `/attendance/me`; `/leaves/me` \| `/leaves` (manager, filtered) \| `/leaves/{id}`; `/salary/me` \| `/salary/{id}` | — | per-tab loading/empty/error | tabs Attendance / Leaves / **Salary only for self or HR/Admin**; edit button HR/Admin; "not linked to employee" message for `/my-profile` 404 | 🔴 Part 2 (spec: cover header, avatar, key facts, tabs Overview/Attendance/Leave/Payroll) |
| 6 | `/departments` · `DepartmentsPage` | A H M | `/departments` | — | loading/empty/error, search | cards: headcount, active, managers, designations | 🔴 Part 2 |
| 7 | `/attendance` · `AttendancePage` | all (tabs by role) | `/attendance/me`, `/attendance/summary?from_date&to_date`, `/attendance/today`; staff: `/attendance/daily?date`, `/attendance/records?…`, `/employees`, `/employees?status=active` | check-in/out (hero); H/A: `POST /attendance` (Mark attendance modal) | per-tab states | tabs My / Daily View / Records; month filter; CSV export; manager sees team only; `AttendanceHeatmap` + `TodayAttendanceCard` already exist for the Part 2 hero/calendar | 🔴 Part 2 |
| 8 | `/leave` · `LeavePage` | all (tabs by role) | `/leaves/balance/me`, `/leaves/me`; approvers: `/leaves?status=pending`, `/leaves?status=…` | `POST /leaves` (apply), `POST /leaves/{id}/cancel`, `PATCH /leaves/{id}/status` {status} | per-tab states | **own requests never get Approve/Reject (D-022)** + notice; manager = team only; cancel only pending; apply shows balance + working days; `LeaveBalanceGrid` is already ring-based | 🔴 Part 2 (spec: apply drawer, timeline, confirm dialogs, clear message instead of raw 403) |
| 9 | `/payroll` · `PayrollPage` | A H = register; E M = "My Payslips" | A/H: `/salary?month&year`, `/salary/summary?month&year`; E/M: `/salary/me` | A/H: `POST /salary/generate` (modal; disabled for future months; current month = provisional) | loading/empty/error | month/year selector, search, payslip modal (printable: `.print-area`, `.no-print` rules in globals.css), **salary visibility unchanged** | 🔴 Part 2 (do NOT add payroll actions beyond generate) |
| 10 | `/documents` · `DocumentsPage` | all view; A H manage | `/documents` | A/H: `POST /documents/upload` (multipart: file, name?; pdf/docx/txt ≤10MB), `DELETE /documents/{id}` (archive, confirm) | loading/empty/error | columns: name, type, version, status, uploader, date, indexed chunks. API also has download/reindex but the page doesn't expose them yet | 🔴 Part 2 |
| 11 | `/reports` · `ReportsPage` | A H | `/dashboard/summary` (default month), `/departments` | downloads `GET /reports/{attendance\|overtime\|leave}?month&year&department` (xlsx via `api.download`) | per-card busy state | month/year/department filters; no preview API exists → no preview | 🔴 Part 2 |
| 12 | `/assistant` · `ChatPage` (full height) | all | `/chat/history` (own, oldest first) | `POST /chat` {message} | history loading/error, typing state, error bubble | markdown (`Markdown` component), intent/confidence/source chips (`sources[]`), suggested prompts per role, Enter/Shift+Enter. ⚠ layout height calc is `100dvh-56px-…` (adjusted for the new 56px top bar) | 🔴 Part 2 (spec: avatars, copy button, typing indicator, history using existing endpoint) |
| 13 | `/settings` · `SettingsPage` | A only | `/users`, `/chat/logs?limit=100` | `PATCH /users/{id}` {role?, status?} (confirm for deactivate/role change; not self) | per-tab states | tabs: Users & Roles, AI Chat Audit Log (filters, expandable rows), Company Policy (**hard-coded copy, KI-013**) | 🔴 Part 2 |

Unchanged cross-cutting behaviour that Part 2 must preserve: `api.ts` 401 → logout/redirect; role route guards in `App.tsx`;
`GOOGLE_LOGIN_URL` points at the backend (OAuth redirect flow, not the proxy); `#token=` hash hand-off in `auth.tsx`.

## 2. Widget availability (no fake data)

| Requested widget | Real data? | What was built |
|---|---|---|
| Notifications | **No endpoint.** Derivable for approvers only | Bell for A/H/M = pending leave requests they may decide (`GET /leaves?status=pending`, own excluded). **Hidden for employees.** |
| Trend deltas | Only attendance-rate between months (`monthly_attendance`) | Delta chip on the HR/Admin "Attendance trend" panel (vs previous month). No deltas on today-only KPIs (no history) — omitted. `StatCard` supports `delta` for future real data. |
| Sparklines | Derivable: daily "attending" counts from `/attendance/records` | Sparkline on the "Present" KPI (HR/Admin) — hidden unless ≥3 real points (Oct 2026 demo month has only 2 recorded days, so it is currently hidden). |
| Attendance trend | Yes (derived) | Daily stacked bars for the reference month from `/attendance/records`, plus the monthly rates. |
| Recent activity | Yes: `recent_leaves`; admin: `/chat/logs` | "Recent activity" (leave requests) + admin "AI assistant activity". |
| Conversation history | Yes: `GET /chat/history` | Existing on ChatPage; Part 2 may enlarge it. No threads/sessions exist → no conversation list. |
| Global search | Yes for staff (`/employees?search=`); pages for everyone | ⌘K palette: pages + actions for all; employee search for A/H/M only. |
| Payroll snapshot (HR) | Yes (`/salary` latest month, totalled client-side) | HR dashboard panel. |
| Access overview (admin) | Yes (`/users`) | Admin dashboard panel (counts by role, inactive). |

## 3. What Part 1 changed (inventory)

**Tokens/CSS**: `styles/globals.css` rewritten (tokens light+dark, status colours, avatar palette, motion keyframes + utilities
`animate-*`, `.skeleton`, `.hr-card` flat, `.hr-select`, legacy bridge, print rules). `src/index.html` pre-paint theme script.
**Libs**: `lib/theme.tsx` (ThemeProvider/useTheme), `lib/useMediaQuery.ts`, `lib/useCountUp.ts`, `lib/nav.ts` (+`group`,
`groupedNavForRole`). `App.tsx` wraps `ThemeProvider`.
**New primitives** `components/ui/`: `badge`, `skeleton`, `separator`, `switch`, `tooltip` (+`Hint`), `dropdown-menu`,
`popover`, `dialog` (+`DrawerContent`, `useRestoreFocus`). **Restyled**: `button` (+`loading`, variants `success|subtle`),
`card`, `input`, `textarea`, `label`.
**Shared** `components/`: rewritten `Modal`/`ConfirmDialog` (Radix, same API), `States` (skeletons, `CardSkeletons`),
`StatusBadge`, `Avatar` (+`seed`, `xs`), `Tabs` (arrow keys), `Toast`, `StatCard` (`numeric`/`format`/`delta`/`spark`/`loading`),
`PageHeader`/`Panel`, `DataTable` (+`Pagination`, sort, `mobileCard`, keyboard rows), `Field`, `charts` (CSS-token colours;
`Sparkline`, `RingProgress`, `Donut`), `LeaveBalanceGrid` (rings, `leaveTypeColor`), `TodayAttendanceCard` (hero + live clock).
New: `Segmented`, `AttendanceHeatmap`, `layout/{BrandMark,Sidebar,ThemeMenu,ProfileMenu,NotificationBell,CommandPalette}`;
`layout/AppShell` rewritten.
**Pages**: `LoginPage`, `DashboardPage` + `pages/dashboard/{data.ts,widgets.tsx}`, `EmployeesPage`.
**Other**: `scripts/ui_qa.py` updated for the new shell; `pages/ChatPage.tsx` one-line height calc (52px → 56px).

## 4. Part 2 todo (in this order)

1. Re-read `DESIGN.md`; if the owner left feedback on the Part 1 direction, change tokens/shared components first.
2. Pages 4–13 (§1), reusing `Panel`, `DataTable`, `StatCard`, `Segmented`, `Dialog`/`DrawerContent`, `AttendanceHeatmap`,
   `RingProgress`. Suggested batches: (a) EmployeeForm + EmployeeDetail + Departments, (b) Attendance + Leave,
   (c) Payroll + Documents + Reports, (d) Chat + Settings.
3. Replace remaining raw palette usage (`bg-white`, `bg-slate-*`, `text-slate-*`, `bg-emerald-50`…, `text-navy`, `hr-card`
   inline gradients in ChatPage `bg-navy`) → tokens; then **delete the legacy bridge** in `globals.css` and the `--legacy-navy`
   / `--color-navy*` / `--color-ink*` / `--color-page` aliases. Verify with `grep -rE "bg-white|slate-|emerald-|navy|text-ink" src`.
4. Apply-leave as a drawer (`DrawerContent side="right"`), payslip modal polish (keep print rules), drag-and-drop upload with
   progress, report cards, chat bubbles/copy/typing, settings tabs. Keep every existing action and permission (§1 table).
5. Delete the `mobileCard`-less tables' horizontal-scroll reliance where cards read better on phones.
6. Quality pass (DESIGN §8) for all roles × pages × widths × themes; `python scripts/ui_qa.py` must be `0 issue(s)`;
   `bunx tsc --noEmit -p . && bun run build`; update `DESIGN.md`, `AGENTS.md`, `PROJECT_STATUS.md`, `CHANGELOG.md`, `README.md`.

## 5. Known interim issues (legacy pages inside the new shell)

- Sidebar takes 248px, so wide legacy tables (Leave approvals, Payroll register, Attendance records) can scroll horizontally
  inside their card at 1280–1440px; shared table padding was tightened to compensate. Part 2 redesigns those layouts.
- Legacy pages still use raw palette classes; dark mode renders them through the legacy bridge (looks right, but it is a bridge).
- ChatPage avatar chips use `bg-navy` (mapped to a light indigo in dark mode, white-on-light icon) — Part 2 rebuilds the bubbles.
- Pagination (`DataTable pageSize`, cards `Pagination`) is code-reviewed but **not browser-verified**: the demo DB has only
  6 employees (< page size). Verify in Part 2 on a table that exceeds its page size (e.g. attendance records) or with test rows
  that you create and delete (AGENTS.md §5, D-023).
- Check-in/out buttons were verified by state only (the demo employee already checked out today); the POSTs were not exercised
  in Part 1 to keep the dev DB unchanged.

## 6. Handy commands

```powershell
# servers (agent shells: no --reload, see KI-022; restart bun dev after adding files, KI-005)
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
cd frontend; bun dev
# type-check + prod build
cd frontend; bunx tsc --noEmit -p .; bun run build
# browser QA (repo harness)
.venv\Scripts\python.exe scripts\ui_qa.py --out frontend\.redesign\qa
```
Screenshot/verification helper scripts used in Part 1 lived in the agent scratchpad (not committed): log in via
`POST /api/auth/login`, inject `hr_token` into localStorage, visit pages with Playwright + Edge (`channel="msedge"`),
`color_scheme="light|dark"`, viewports 1440/1024/390. axe-core 4.10 was loaded from cdnjs for the contrast scan.
