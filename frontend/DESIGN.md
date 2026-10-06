# DESIGN.md — Frontend design system v2

> Source of truth for how the UI looks and is built. Supersedes the visual/navigation part of D-002 (see
> `PROJECT_DECISIONS.md` D-026). Tokens live in `frontend/styles/globals.css` — **never put a hex colour in a component.**
> Status: **Part 1 of the redesign** (tokens, primitives, shell, Login/Dashboard/Employees). Sections marked 🔧 may still be
> extended by Part 2 (the other 10 pages); everything else is settled unless the owner asks for changes.

## 1. Principles

1. **Calm, confident, information-dense but not crowded.** Restraint over decoration: no gradients on surfaces, no
   glassmorphism, no blobs, no shadow stacks. Flat cards with a 1px border.
2. **One accent (indigo), semantic colour only for status.** Green/amber/red/sky/violet always *mean* a status.
3. **Real data only.** A widget with no existing endpoint is derived client-side from existing endpoints or hidden
   (see `REDESIGN_NOTES.md` §2). Never invent numbers, never mock.
4. **Every data view has loading (skeleton), empty (with next action) and error (with retry).** Every mutation toasts.
5. **The backend is the source of truth for permissions.** The UI hides what a role can't do and explains why when it
   isn't obvious. Menu items/commands are role-filtered with the same role sets the backend enforces.
6. **Accessible by default:** keyboard reachable, visible focus, AA contrast, `prefers-reduced-motion`, focus trapping.

## 2. Tokens (`styles/globals.css`)

Raw tokens are CSS variables on `:root` (light) and `.dark` (dark); `@theme inline` maps them to Tailwind utilities.

| Role | Token → utility | Light | Dark |
|---|---|---|---|
| Page background | `--background` → `bg-background` | `#f8fafc` | `#0a0e17` |
| Card / surface | `--surface` → `bg-surface` / `bg-card` | `#ffffff` | `#111726` |
| Subtle fill (inputs hover, table head, tiles) | `--surface-muted` → `bg-surface-muted` | `#f1f5f9` | `#182033` |
| Hover fill | `--accent` → `bg-accent` | `#f1f5f9` | `#1a2336` |
| Floating layer | `--popover` → `bg-popover` | `#ffffff` | `#151c2e` |
| Border / strong border | `--border`, `--border-strong` | `#e2e8f0` / `#cbd5e1` | `#232d42` / `#33415c` |
| Input border (≥3:1) | `--input` → `border-input` | `#8493a8` | `#5b6a86` |
| Text / muted text | `--foreground`, `--muted-foreground` | `#0f172a` / `#5b6b82` | `#e8ecf4` / `#9aa6bb` |
| Brand (indigo) | `--brand`, `--brand-hover`, `--brand-foreground` | `#4f46e5`, `#4338ca`, `#fff` | `#818cf8`, `#a5b4fc`, `#0a0e17` |
| Brand tint | `--brand-subtle`, `--brand-subtle-foreground` | `#eef2ff`, `#4338ca` | `#818cf829`, `#c7d2fe` |
| Focus ring | `--ring` | = brand | = brand |
| Shadow (floating only) | `--shadow-float` → `shadow-float` | soft | deeper |
| Overlay scrim | `--overlay` | `rgb(15 23 42/.45)` | `rgb(2 6 15/.65)` |
| Login brand panel | `--brand-panel`(`-foreground`) | `#1e1b4b` | `#151538` |

**Usage rules**
- Use `bg-brand text-brand-foreground`, **never `text-white`** (`brand-foreground` flips correctly in dark mode; raw palette
  classes don't). Text on a solid amber fill uses `text-[var(--on-late)]`.
- A **filled** success surface with text (the `success` button) uses `bg-status-present-solid text-brand-foreground`
  (`#047857` light / `#34d399` dark): white on the plain present green `#059669` is only 3.8:1. Keep `status-present` for
  dots, bars, rings, charts and calendars (no text on them).
- Text sizes: `text-foreground` for content, `text-muted-foreground` for meta. Don't use opacity to dim text (fails AA).

### Status colours — one fixed colour per status
Tokens `--status-{present|absent|late|half|leave|neutral}` (solid, for charts/dots/cells) plus `-bg` (tint) and `-fg`
(readable text). The **same** token is used in `StatusBadge`, charts (`ATTENDANCE_SERIES`), the heat-map and the donut.

| Status | Token | Statuses it covers |
|---|---|---|
| green | `present` | present · approved · active · paid |
| red | `absent` | absent · rejected · failed · terminated |
| amber | `late` | late · pending · on_notice · unpaid |
| sky | `half` | half_day · processing |
| violet | `leave` | leave · on_leave |
| slate | `neutral` | holiday · weekend · inactive · cancelled · archived · not_marked |

Semantic aliases: `success`=present, `warning`=late, `danger`=absent, `info`=half. Roles: `RoleBadge` (admin = brand,
hr = violet, manager = sky, employee = slate). Leave types have fixed chart colours in `LeaveBalanceGrid.leaveTypeColor`.

### Chart rules
- Recharts only; colours via `var(--status-*)` / `var(--chart-*)` (they follow the theme). Axis/tooltip styles are in
  `components/charts.tsx` (`AXIS_TICK`, `GRID_STROKE`, `TOOLTIP_STYLE`). Series order for attendance: present, leave, late,
  half day, absent. Gridlines horizontal only. Max bar width ~20–44px, rounded top on the last stack.
- Single-series lists use `BarList`; rings `RingProgress`; segmented totals `Donut`; trend hints `Sparkline` (≥3 real points).
- Always give charts an accessible name (`role="img"` + `aria-label` on rings/donuts) and a text alternative nearby.

## 3. Typography, spacing, radius, motion

| Style | Spec |
|---|---|
| Font | Inter (400/500/600/700), `font-feature-settings: "cv11","ss01"` |
| Page title (`PageHeader`) | 24/600 (22 on phones), tracking-tight |
| Section title (`Panel`) | 16/600 |
| Body | 14/400 |
| Meta / labels | 12/500, `text-muted-foreground` |
| KPI value | 28/600, **tabular numerals** (`tabular-nums` on every metric) |

- **Spacing:** 8px grid (Tailwind multiples of 2). Content gutters 16 / 24 / 32px (`sm` / `lg`); card padding 16–20px; grid gap 20px.
- **Radius:** 8px controls (`rounded-md`/`rounded-lg`), 12px cards (`rounded-xl`), 16px dialogs (`rounded-2xl`), full for pills/avatars.
- **Borders/shadows:** 1px `border-border`. The only shadow is `shadow-float` on menus, popovers, dialogs, toasts.
- **Motion:** 150–250ms. `animate-page-in` (route change, 220ms), `animate-pop-in` (menus/tooltips, 150ms),
  `animate-dialog-in` / `animate-sheet-up` / `animate-drawer-*` (dialogs, 200–220ms), `animate-toast-in`, skeleton shimmer,
  `card-interactive` hover lift, stat count-up (`useCountUp`, 700ms). All are disabled under `prefers-reduced-motion`
  (global rule in `globals.css`; `useCountUp` returns the final value immediately).

## 4. Components (reuse before inventing) 🔧

**Primitives — `components/ui/`**: `button` (variants default/destructive/success/outline/secondary/ghost/subtle/link; sizes
default/sm/lg/icon*; `loading` prop), `card`, `input`, `textarea`, `label`, `select` (Radix, shadcn), `badge`, `skeleton`,
`separator`, `switch`, `tooltip` (+`Hint`), `dropdown-menu`, `popover`, `dialog` (+`DrawerContent`).

**Shared — `components/`**: `PageHeader` + `Panel`, `StatCard` (count-up, delta, sparkline), `DataTable` (+`Pagination`),
`StatusBadge`/`RoleBadge`, `Toast` (`useToast`), `States` (`LoadingState`, `CardSkeletons`, `EmptyState`, `ErrorState`,
`AsyncContent`, `Notice`), `Modal`/`ConfirmDialog` (Radix Dialog), `Tabs` (keyboard-navigable), `Segmented`, `Field`
(`Field`, `NativeSelect`, `SearchInput`, `MonthSelect`, `YearSelect`), `Avatar`, `charts` (`BarList`, `RingProgress`,
`Donut`, `Sparkline`, `Legend`), `AttendanceHeatmap`, `LeaveBalanceGrid`, `TodayAttendanceCard` (check-in hero).
**Layout — `components/layout/`**: `AppShell`, `Sidebar`/`SidebarNav`, `CommandPalette`, `NotificationBell`, `ThemeMenu`,
`ProfileMenu`, `BrandMark`.

**Rules**
- **DataTable:** sticky header, hover rows, `sortValue` on a column makes it sortable, `pageSize` paginates, rows with
  `onRowClick` are keyboard-activatable (Enter/Space), `mobileCard` renders a card list below 768px. Tables scroll
  *inside* their card (`relative` scroller) — never widen the page.
- **Dialogs/drawers:** always Radix (`Modal`, `ConfirmDialog`, `DialogContent`, `DrawerContent`). Focus is trapped, Escape
  closes, and **focus returns to the opener** (`useRestoreFocus` in `ui/dialog.tsx` — Radix only does this for `<Trigger>`).
  Confirm dialogs focus **Cancel** first. Pass `description` only if you have one.
- **Forms:** `Field` for label/hint/error (`role="alert"` errors), inline validation, `aria-invalid`, loading/disabled
  submit (`Button loading`). Do not change backend validation contracts.
- **Icons:** `lucide-react` only. Decorative icons get `aria-hidden`; icon-only buttons need `aria-label`.
- **Avatars:** initials, colour from `--avatar-1..8` chosen by hashing the name (or `seed`, e.g. user id).
- **New shared component?** Add it here with its props; add page-specific visuals only with a strong reason.

## 5. App shell & navigation

- **Desktop ≥1280px:** left sidebar, 248px, collapsible to a 68px icon rail (choice saved in `localStorage` `hr_sidebar`).
  **Tablet 768–1279px:** icon rail (tooltips on hover/focus). **Phone <768px:** no sidebar; hamburger opens a left drawer
  (Radix Dialog → focus trap, Escape, scrim click, closes on navigation).
- Sidebar groups (order preserved from the old menu): *Overview* Dashboard · My Profile — *People* Employees · Departments —
  *Workspace* Attendance · Leave · Payroll · Documents — *Insights* Reports · AI Assistant — *Admin* Settings.
  Active item = tinted pill + 3px brand bar. Role filtering comes from `lib/nav.ts` (`groupedNavForRole`).
- **Top bar 56px (sticky):** breadcrumb (group › page [› New/Edit/Profile]) — search/⌘K — notification bell — theme —
  profile menu. On phones: hamburger + mark + current page name.
- **⌘/Ctrl+K command palette:** pages the role may open, "Add employee" (hr/admin), theme + sign-out actions, and employee
  search for staff roles (`GET /employees?search=`, scoped server-side). ↑/↓/Enter/Esc.
- **Notification bell:** approver roles only (admin/hr/manager); shows pending leave requests this user may decide
  (`GET /leaves?status=pending`, own excluded). Employees have no bell — there is no endpoint for them.
- "Skip to content" link, `<main id="main">`, route-change fade.
- Menu items must never show an action the backend will refuse (own-leave approval, deactivating yourself, …).

## 6. Responsive
Design for 390 / 1024 / 1440. No horizontal page scroll at any width; tables scroll inside cards; dialogs become bottom
sheets on phones; KPI grids are 2 → 3 → 6 columns; dashboards stack to one column below `lg`.

## 7. Dark mode
`ThemeProvider` (`lib/theme.tsx`): Light / Dark / **System (default)**, toggle in the top bar (and on Login), persisted in
`localStorage` `hr_theme` (try/catch). An inline script in `index.html` sets `.dark` before first paint (no flash).
Every token has a deliberate dark value; shadows deepen, status tints become translucent, brand lightens.
The temporary **legacy bridge** (D-028) and the legacy aliases (`navy`, `ink`, `page`, `brand-light`) were **deleted** on
2026-10-06 when Part 2 finished: nothing remaps raw palette classes any more, so a `bg-white`/`slate-*` class in new code
renders wrongly in dark mode. Check with `grep -rE "bg-white|text-white|slate-|emerald-|navy" src` (expect only `translate-*`
false positives and the `StatCard` tone aliases).

## 8. Accessibility checklist (verify on every page)
- AA contrast (axe-core `wcag2a/2aa/21aa` clean in light **and** dark); input borders ≥3:1.
- Keyboard: every control reachable, visible `:focus-visible` ring, logical order, Escape closes layers, rows/cards activatable.
- Dialogs trap focus and restore it; menus/tabs/segmented controls are keyboard-operable (`Tabs`: ←/→/Home/End).
- Loading regions `role="status"`; errors `role="alert"`; charts have text alternatives; reduced-motion honoured.

## 9. Don'ts
No hex in components · no `text-white`/`bg-white` in new code · no new colour that isn't a token · no per-page visual
system · no fake data · no `any` · no dependency without a decision-log entry (`PROJECT_DECISIONS.md` D-027).
