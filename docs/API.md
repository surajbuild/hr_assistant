# API Reference

> **Generated** by `python scripts/export_api_docs.py` from the live FastAPI app (`app.openapi()` + the route
> dependencies). Do not edit by hand — change the code (or the notes in the script) and re-run it.
> Interactive version: `http://localhost:8000/docs` (Swagger UI) while the backend runs.

## Conventions

| Topic | Rule |
|---|---|
| Base URL | Backend: `http://localhost:8000`. The React app calls the same paths under **`/api`** (e.g. `/api/employees`); the Bun server (`frontend/src/index.ts`) strips `/api` and forwards the request (D-003). In Docker only the `/api` route through the frontend is reachable. |
| Authentication | `Authorization: Bearer <JWT>` from `POST /auth/login` (or the Google OAuth callback). HS256, expires after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 60). Missing/invalid/expired token -> **401**; deactivated account -> **403** (on every authenticated route). |
| Roles | `employee`, `manager`, `hr`, `admin` (lowercase). "Access" below is the role check (`require_role`); data scope (own data, manager's direct reports) is enforced inside the route and described in the notes. A wrong role -> **403** `You do not have permission to perform this action.` |
| Errors | JSON `{"detail": "<message>"}`. Request validation errors (422) return `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. The "Errors" line of each endpoint lists every status its handler (and the helpers it calls) can raise, plus 401/403 on authenticated routes and 422 where input is validated. |
| Pagination (D-035) | List endpoints that support it take `limit` / `offset` and return a plain JSON array; the total number of matching rows is in the **`X-Total-Count`** response header (exposed via `Access-Control-Expose-Headers`). Marked "Paginated" below. |
| Rate limits (D-031) | `POST /auth/login`: per client IP (default 30/min) and failed attempts per (IP, email) (default 5 per 15 min). `POST /chat`: per user (default 20/min). Over the limit -> **429** with a `Retry-After` header (seconds). In-memory, per backend process. |
| Dates | `YYYY-MM-DD`; times `HH:MM[:SS]`; datetimes ISO 8601. Money values are rupees as numbers. |
| Proxy errors | When the backend is unreachable the Bun proxy answers **502** `{"detail": "Unable to connect to server. ..."}`. |

## Endpoint index

61 operations in 13 groups.

| Group | Method | Path | Access | Summary |
|---|---|---|---|---|
| AI Chat | `POST` | [`/chat`](#post-chat) | Any authenticated user | Ask a question to the AI HR Assistant |
| AI Chat | `GET` | [`/chat/history`](#get-chathistory) | Any authenticated user | My chat history |
| AI Chat | `GET` | [`/chat/logs`](#get-chatlogs) | `admin` | Chat audit log (Admin) |
| Attendance | `POST` | [`/attendance`](#post-attendance) | `hr`, `admin` | Create Attendance Record |
| Attendance | `POST` | [`/attendance/check-in`](#post-attendancecheck-in) | Any authenticated user | Check In |
| Attendance | `POST` | [`/attendance/check-out`](#post-attendancecheck-out) | Any authenticated user | Check Out |
| Attendance | `GET` | [`/attendance/corrections`](#get-attendancecorrections) | `manager`, `hr`, `admin` | Correction Requests To Review |
| Attendance | `POST` | [`/attendance/corrections`](#post-attendancecorrections) | Any authenticated user | Request Attendance Correction |
| Attendance | `GET` | [`/attendance/corrections/me`](#get-attendancecorrectionsme) | Any authenticated user | My Correction Requests |
| Attendance | `POST` | [`/attendance/corrections/{correction_id}/approve`](#post-attendancecorrectionscorrection_idapprove) | `manager`, `hr`, `admin` | Approve Correction |
| Attendance | `POST` | [`/attendance/corrections/{correction_id}/cancel`](#post-attendancecorrectionscorrection_idcancel) | Any authenticated user | Cancel My Correction Request |
| Attendance | `POST` | [`/attendance/corrections/{correction_id}/reject`](#post-attendancecorrectionscorrection_idreject) | `manager`, `hr`, `admin` | Reject Correction |
| Attendance | `GET` | [`/attendance/daily`](#get-attendancedaily) | `manager`, `hr`, `admin` | Daily Attendance Sheet |
| Attendance | `GET` | [`/attendance/me`](#get-attendanceme) | Any authenticated user | Get My Attendance |
| Attendance | `GET` | [`/attendance/records`](#get-attendancerecords) | `manager`, `hr`, `admin` | Search Attendance Records |
| Attendance | `PUT` | [`/attendance/records/{record_id}`](#put-attendancerecordsrecord_id) | `hr`, `admin` | Edit Attendance Record |
| Attendance | `GET` | [`/attendance/summary`](#get-attendancesummary) | Any authenticated user | Get My Attendance Summary |
| Attendance | `GET` | [`/attendance/today`](#get-attendancetoday) | Any authenticated user | Get My Attendance For Today |
| Attendance | `GET` | [`/attendance/{employee_id}`](#get-attendanceemployee_id) | `hr`, `admin` | Get Employee Attendance |
| Authentication | `GET` | [`/auth/google/callback`](#get-authgooglecallback) | Public (no token) | Google OAuth callback |
| Authentication | `GET` | [`/auth/google/login`](#get-authgooglelogin) | Public (no token) | Google OAuth login |
| Authentication | `POST` | [`/auth/login`](#post-authlogin) | Public (no token) | Email / password login |
| Authentication | `GET` | [`/auth/me`](#get-authme) | Any authenticated user | Current user |
| Dashboard | `GET` | [`/dashboard/me`](#get-dashboardme) | Any authenticated user | Get My Dashboard |
| Dashboard | `GET` | [`/dashboard/summary`](#get-dashboardsummary) | `hr`, `admin` | Get HR Dashboard Summary |
| Departments | `GET` | [`/departments`](#get-departments) | `manager`, `hr`, `admin` | List Departments |
| Documents | `GET` | [`/documents`](#get-documents) | Any authenticated user | List Documents |
| Documents | `POST` | [`/documents/upload`](#post-documentsupload) | `hr`, `admin` | Upload HR Document |
| Documents | `DELETE` | [`/documents/{document_id}`](#delete-documentsdocument_id) | `hr`, `admin` | Archive Document |
| Documents | `GET` | [`/documents/{document_id}/download`](#get-documentsdocument_iddownload) | Any authenticated user | Download Document |
| Documents | `POST` | [`/documents/{document_id}/reindex`](#post-documentsdocument_idreindex) | `hr`, `admin` | Re-index Document |
| Employees | `GET` | [`/employees`](#get-employees) | `manager`, `hr`, `admin` | List Employees |
| Employees | `POST` | [`/employees`](#post-employees) | `hr`, `admin` | Create Employee |
| Employees | `GET` | [`/employees/me`](#get-employeesme) | Any authenticated user | Get Current Employee Profile |
| Employees | `GET` | [`/employees/{employee_id}`](#get-employeesemployee_id) | Any authenticated user | Get Employee By ID |
| Employees | `PUT` | [`/employees/{employee_id}`](#put-employeesemployee_id) | `hr`, `admin` | Update Employee |
| Employees | `DELETE` | [`/employees/{employee_id}`](#delete-employeesemployee_id) | `hr`, `admin` | Deactivate Employee (soft delete) |
| Health | `GET` | [`/`](#get-) | Public (no token) | Root |
| Health | `GET` | [`/health`](#get-health) | Public (no token) | Liveness |
| Health | `GET` | [`/health/ready`](#get-healthready) | Public (no token) | Readiness (database reachable) |
| Holidays | `GET` | [`/holidays`](#get-holidays) | Any authenticated user | Holiday Calendar |
| Holidays | `POST` | [`/holidays`](#post-holidays) | `hr`, `admin` | Declare Company Holiday |
| Holidays | `DELETE` | [`/holidays/{holiday_id}`](#delete-holidaysholiday_id) | `hr`, `admin` | Remove Company Holiday |
| Leaves | `GET` | [`/leaves`](#get-leaves) | `manager`, `hr`, `admin` | List Leave Requests |
| Leaves | `POST` | [`/leaves`](#post-leaves) | Any authenticated user | Create a Leave Request |
| Leaves | `GET` | [`/leaves/balance/me`](#get-leavesbalanceme) | Any authenticated user | Get My Leave Balance |
| Leaves | `GET` | [`/leaves/me`](#get-leavesme) | Any authenticated user | Get My Leaves |
| Leaves | `GET` | [`/leaves/{employee_id}`](#get-leavesemployee_id) | `hr`, `admin` | Get Employee Leaves |
| Leaves | `POST` | [`/leaves/{leave_id}/cancel`](#post-leavesleave_idcancel) | Any authenticated user | Cancel My Pending Leave |
| Leaves | `PATCH` | [`/leaves/{leave_id}/status`](#patch-leavesleave_idstatus) | `manager`, `hr`, `admin` | Approve or Reject Leave |
| Reports | `GET` | [`/reports/attendance`](#get-reportsattendance) | `hr`, `admin` | Export Attendance Report (Excel) |
| Reports | `GET` | [`/reports/leave`](#get-reportsleave) | `hr`, `admin` | Export Leave Report (Excel) |
| Reports | `GET` | [`/reports/overtime`](#get-reportsovertime) | `hr`, `admin` | Export Overtime Report (Excel) |
| Salary | `GET` | [`/salary`](#get-salary) | `hr`, `admin` | Get Payroll Sheet |
| Salary | `POST` | [`/salary/generate`](#post-salarygenerate) | `hr`, `admin` | Generate Payroll |
| Salary | `POST` | [`/salary/mark-paid`](#post-salarymark-paid) | `hr`, `admin` | Mark Salaries As Paid |
| Salary | `GET` | [`/salary/me`](#get-salaryme) | Any authenticated user | Get My Salary |
| Salary | `GET` | [`/salary/summary`](#get-salarysummary) | `hr`, `admin` | Get Salary Summary |
| Salary | `GET` | [`/salary/{employee_id}`](#get-salaryemployee_id) | `hr`, `admin` | Get Employee Salary |
| Users | `GET` | [`/users`](#get-users) | `admin` | List Users |
| Users | `PATCH` | [`/users/{user_id}`](#patch-usersuser_id) | `admin` | Update User Role / Status |

## AI Chat

### POST /chat

**Ask a question to the AI HR Assistant** — Process a natural language HR inquiry with controlled data access and grounded LLM synthesis.

- **Access:** Any authenticated user
- **Rules:** Rate limited per user (default 20/min, D-031) -> 429. Send `message` (or legacy `question`), max 1000 characters; blank -> 400. Refusals (prompt injection, RBAC) are returned as 200 with `confidence: access_denied` and never reach the LLM. Every call writes a `chat_logs` row. See docs/AI.md.
- **Request body** (`application/json`, required):
  - `message`: string \| null — max length 1000
  - `question`: string \| null — max length 1000
- **Response 200:** `ChatResponse`: `question` (string), `intent` (string), `answer` (string), `source` (string), `confidence` (string), `page` (integer \| null), `sources` (array<ChatSource>)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity, 429 Too Many Requests

### GET /chat/history

**My chat history**

- **Access:** Any authenticated user
- **Rules:** The caller's own last `limit` questions and answers (oldest first).
- **Parameters:**
  - `limit` (query, integer, optional) — >= 1, <= 200, default `30`
- **Response 200:** array of `ChatHistoryItem`: `id`, `question`, `response`, `detected_intent`, `data_source`, `timestamp`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /chat/logs

**Chat audit log (Admin)**

- **Access:** `admin`
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** Audit log of every chat interaction, newest first; `search` matches question or user email.
- **Parameters:**
  - `limit` (query, integer, optional) — >= 1, <= 1000, default `100`
  - `offset` (query, integer, optional) — >= 0, default `0`
  - `search` (query, string \| null, optional) — max length 200; Filter by question or user email
- **Response 200:** array of `ChatLogItem`: `id`, `question`, `response`, `detected_intent`, `data_source`, `timestamp`, `user_id`, `user_email`, `response_time_ms`, `error`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

## Attendance

### POST /attendance

**Create Attendance Record** — Allows HR or Admin to create a new attendance record for an employee.

- **Access:** `hr`, `admin`
- **Rules:** HR/Admin create a record for any employee; 409 if that employee already has a record for the date.
- **Request body** (`application/json`, required):
  - `employee_id`: integer (required)
  - `attendance_date`: date (required)
  - `in_time`: time \| null
  - `out_time`: time \| null
  - `status`: AttendanceStatus ("present" \| "absent" \| "half_day" \| "leave" \| "holiday" \| "weekend") (required)
  - `working_minutes`: integer — default `0`
  - `late_minutes`: integer — default `0`
  - `overtime_minutes`: integer — default `0`
- **Response 201:** `AttendanceResponse`: `id` (integer), `employee_id` (integer), `attendance_date` (date), `in_time` (time \| null), `out_time` (time \| null), `working_minutes` (integer \| null), `status` (string), `late_minutes` (integer), `overtime_minutes` (integer)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### POST /attendance/check-in

**Check In** — Self-service check-in. Arrivals after 9:15 are recorded as late.

- **Access:** Any authenticated user
- **Rules:** Creates today's record with the server clock; late when after 09:15 (D-007). 409 if already checked in.
- **Response 201:** `AttendanceResponse`: `id` (integer), `employee_id` (integer), `attendance_date` (date), `in_time` (time \| null), `out_time` (time \| null), `working_minutes` (integer \| null), `status` (string), `late_minutes` (integer), `overtime_minutes` (integer)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict

### POST /attendance/check-out

**Check Out** — Self-service check-out. Working and overtime minutes are calculated by the server.

- **Access:** Any authenticated user
- **Rules:** Server computes working / overtime / late minutes and present vs half day (D-007). 409 if not checked in or already checked out.
- **Response 200:** `AttendanceResponse`: `id` (integer), `employee_id` (integer), `attendance_date` (date), `in_time` (time \| null), `out_time` (time \| null), `working_minutes` (integer \| null), `status` (string), `late_minutes` (integer), `overtime_minutes` (integer)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict

### GET /attendance/corrections

**Correction Requests To Review** — HR / Admin: everyone's; Manager: direct reports'. Your own requests are not listed here.

- **Access:** `manager`, `hr`, `admin`
- **Rules:** Requests to review. HR/Admin -> everyone's; manager -> direct reports'. The caller's own requests are excluded.
- **Parameters:**
  - `status` (query, CorrectionStatus ("pending" \| "approved" \| "rejected" \| "cancelled") \| null, optional)
- **Response 200:** array of `CorrectionItem`: `id`, `employee_id`, `employee_name`, `employee_code`, `department`, `attendance_date`, `requested_in_time`, `requested_out_time`, `reason`, `status`, `requested_at`, `reviewed_by_name`, `reviewed_at`, `review_note`, `current_status`, `current_in_time`, `current_out_time`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /attendance/corrections

**Request Attendance Correction** — Ask your manager / HR to set the in and out time of one of your days.

- **Access:** Any authenticated user
- **Rules:** Correction request for one of the caller's own days (D-033). Future date / before joining / out <= in -> 422; a pending request for the same date or a paid month -> 409.
- **Request body** (`application/json`, required):
  - `attendance_date`: date (required)
  - `in_time`: time (required)
  - `out_time`: time (required)
  - `reason`: string (required) — min length 1, max length 1000
- **Response 201:** `CorrectionItem`: `id` (integer), `employee_id` (integer), `employee_name` (string), `employee_code` (string), `department` (string), `attendance_date` (date), `requested_in_time` (time), `requested_out_time` (time), `reason` (string), `status` (string), `requested_at` (datetime), `reviewed_by_name` (string \| null), `reviewed_at` (datetime \| null), `review_note` (string \| null), `current_status` (string \| null), `current_in_time` (time \| null), `current_out_time` (time \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### GET /attendance/corrections/me

**My Correction Requests**

- **Access:** Any authenticated user
- **Rules:** The caller's own correction requests.
- **Response 200:** array of `CorrectionItem`: `id`, `employee_id`, `employee_name`, `employee_code`, `department`, `attendance_date`, `requested_in_time`, `requested_out_time`, `reason`, `status`, `requested_at`, `reviewed_by_name`, `reviewed_at`, `review_note`, `current_status`, `current_in_time`, `current_out_time`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### POST /attendance/corrections/{correction_id}/approve

**Approve Correction** — Applies the requested times to the attendance record (manager → team only; never your own).

- **Access:** `manager`, `hr`, `admin`
- **Rules:** Applies the requested times to the attendance row. Never your own request (403); manager -> team only (403); not pending (409); month already paid (409).
- **Parameters:**
  - `correction_id` (path, integer, required)
- **Request body** (`application/json`):
  - `note`: string \| null — max length 1000
- **Response 200:** `CorrectionItem`: `id` (integer), `employee_id` (integer), `employee_name` (string), `employee_code` (string), `department` (string), `attendance_date` (date), `requested_in_time` (time), `requested_out_time` (time), `reason` (string), `status` (string), `requested_at` (datetime), `reviewed_by_name` (string \| null), `reviewed_at` (datetime \| null), `review_note` (string \| null), `current_status` (string \| null), `current_in_time` (time \| null), `current_out_time` (time \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### POST /attendance/corrections/{correction_id}/cancel

**Cancel My Correction Request**

- **Access:** Any authenticated user
- **Rules:** Withdraw your own pending request (someone else's -> 404).
- **Parameters:**
  - `correction_id` (path, integer, required)
- **Response 200:** `CorrectionItem`: `id` (integer), `employee_id` (integer), `employee_name` (string), `employee_code` (string), `department` (string), `attendance_date` (date), `requested_in_time` (time), `requested_out_time` (time), `reason` (string), `status` (string), `requested_at` (datetime), `reviewed_by_name` (string \| null), `reviewed_at` (datetime \| null), `review_note` (string \| null), `current_status` (string \| null), `current_in_time` (time \| null), `current_out_time` (time \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### POST /attendance/corrections/{correction_id}/reject

**Reject Correction**

- **Access:** `manager`, `hr`, `admin`
- **Rules:** Never your own request (403); manager -> team only (403); not pending (409).
- **Parameters:**
  - `correction_id` (path, integer, required)
- **Request body** (`application/json`):
  - `note`: string \| null — max length 1000
- **Response 200:** `CorrectionItem`: `id` (integer), `employee_id` (integer), `employee_name` (string), `employee_code` (string), `department` (string), `attendance_date` (date), `requested_in_time` (time), `requested_out_time` (time), `reason` (string), `status` (string), `requested_at` (datetime), `reviewed_by_name` (string \| null), `reviewed_at` (datetime \| null), `review_note` (string \| null), `current_status` (string \| null), `current_in_time` (time \| null), `current_out_time` (time \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### GET /attendance/daily

**Daily Attendance Sheet** — Attendance of every in-scope active employee for one date (default: today or latest with data).

- **Access:** `manager`, `hr`, `admin`
- **Rules:** One row per in-scope active employee for a date (default: today, or the latest date with data -> `is_fallback_date`). Manager -> self + direct reports.
- **Parameters:**
  - `date` (query, date \| null, optional)
- **Response 200:** `DailyAttendanceResponse`: `date` (date), `is_fallback_date` (boolean), `counts` (map<string, integer>), `rows` (array<DailyAttendanceRow>)
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /attendance/me

**Get My Attendance** — Returns all attendance records for the authenticated employee.

- **Access:** Any authenticated user
- **Rules:** The caller's own records.
- **Response 200:** array of `AttendanceResponse`: `id`, `employee_id`, `attendance_date`, `in_time`, `out_time`, `working_minutes`, `status`, `late_minutes`, `overtime_minutes`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### GET /attendance/records

**Search Attendance Records** — Filtered attendance records, newest first. Managers are limited to their team. Paginated with `limit` / `offset`; the total is returned in the `X-Total-Count` header.

- **Access:** `manager`, `hr`, `admin`
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** Manager -> self + direct reports; an `employee_id` outside the scope -> 403. Newest first.
- **Parameters:**
  - `employee_id` (query, integer \| null, optional)
  - `from_date` (query, date \| null, optional)
  - `limit` (query, integer, optional) — >= 1, <= 1000, default `1000`
  - `offset` (query, integer, optional) — >= 0, default `0`
  - `status` (query, AttendanceStatus ("present" \| "absent" \| "half_day" \| "leave" \| "holiday" \| "weekend") \| null, optional)
  - `to_date` (query, date \| null, optional)
- **Response 200:** array of `AttendanceRecordRow`: `id`, `employee_id`, `employee_code`, `employee_name`, `department`, `attendance_date`, `in_time`, `out_time`, `working_minutes`, `status`, `late_minutes`, `overtime_minutes`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### PUT /attendance/records/{record_id}

**Edit Attendance Record** — HR / Admin. Worked days (present / half day) need in and out time; status and minutes are computed by the server. Not allowed on your own record or in a month whose salary is paid.

- **Access:** `hr`, `admin`
- **Rules:** HR/Admin direct edit (D-033). Not your own record (403); not in a month whose salary is paid (409). `present`/`half_day` need `in_time` and `out_time`; status and minutes are recomputed by the server.
- **Parameters:**
  - `record_id` (path, integer, required)
- **Request body** (`application/json`, required):
  - `status`: AttendanceStatus ("present" \| "absent" \| "half_day" \| "leave" \| "holiday" \| "weekend") (required)
  - `in_time`: time \| null
  - `out_time`: time \| null
- **Response 200:** `AttendanceResponse`: `id` (integer), `employee_id` (integer), `attendance_date` (date), `in_time` (time \| null), `out_time` (time \| null), `working_minutes` (integer \| null), `status` (string), `late_minutes` (integer), `overtime_minutes` (integer)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### GET /attendance/summary

**Get My Attendance Summary** — Returns aggregated attendance statistics for the authenticated employee.

- **Access:** Any authenticated user
- **Rules:** The caller's own aggregated counts (calculated in SQL/Python, PRD §20).
- **Parameters:**
  - `end_date` (query, date \| null, optional)
  - `from_date` (query, date \| null, optional)
  - `start_date` (query, date \| null, optional)
  - `to_date` (query, date \| null, optional)
- **Response 200:** `AttendanceSummaryResponse`: `total_days` (integer), `present_days` (integer), `absent_days` (integer), `half_day_days` (integer), `leave_days` (integer), `holiday_days` (integer), `weekend_days` (integer), `late_days` (integer), `overtime_days` (integer), `total_working_minutes` (integer), `total_overtime_minutes` (integer)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### GET /attendance/today

**Get My Attendance For Today** — Returns today's attendance record for the authenticated employee, or null.

- **Access:** Any authenticated user
- **Rules:** The caller's record for today, or `null`.
- **Response 200:** `AttendanceResponse`: `id` (integer), `employee_id` (integer), `attendance_date` (date), `in_time` (time \| null), `out_time` (time \| null), `working_minutes` (integer \| null), `status` (string), `late_minutes` (integer), `overtime_minutes` (integer) — or `null`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### GET /attendance/{employee_id}

**Get Employee Attendance** — Allows HR or Admin to fetch attendance records for a specific employee.

- **Access:** `hr`, `admin`
- **Rules:** Any employee's records (HR/Admin).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Response 200:** array of `AttendanceResponse`: `id`, `employee_id`, `attendance_date`, `in_time`, `out_time`, `working_minutes`, `status`, `late_minutes`, `overtime_minutes`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

## Authentication

### GET /auth/google/callback

**Google OAuth callback** — Handles Google OAuth redirect, verifies token/claims, and issues application JWT.

- **Access:** Public (no token)
- **Rules:** Exchanges the Google code, then: known `google_id` -> that user; known email without a Google id -> links it (409 if the email is linked to a different Google account); otherwise provisions a new `employee` user + employee profile (department `General`). Returns the JSON below, or 302 to `FRONTEND_URL/login#token=<jwt>` when the login was started with `?next=frontend` (D-014).
- **Response 200:** `GoogleAuthResponse`: `access_token` (string), `token_type` (string), `user_id` (integer), `email` (string), `role` (string)
- **Alternative response:** 302 to `FRONTEND_URL/login#token=<jwt>` instead of the JSON above when the login was started with `?next=frontend`
- **Errors:** 400 Bad Request, 403 Forbidden, 409 Conflict

### GET /auth/google/login

**Google OAuth login** — Redirects user to Google OAuth 2.0 authorization screen.

- **Access:** Public (no token)
- **Also answers:** `HEAD`
- **Rules:** 302 to Google's consent screen (Authlib stores the OAuth state in the session cookie). `?next=frontend` makes the callback redirect to the SPA instead of returning JSON. The SPA opens it through the proxy: `/api/auth/google/login?next=frontend`.
- **Response:** 302 redirect to Google's consent screen (no body)

### POST /auth/login

**Email / password login** — Authenticate with email and password. Returns a Bearer JWT access token on success.

- **Access:** Public (no token)
- **Rules:** Rate limited (D-031): all attempts per client IP (default 30/min) and failed attempts per (client IP, email) (default 5 per 15 min) -> 429 + `Retry-After`. A wrong email and a wrong password both return the same generic 401 `Invalid email or password.`; an inactive account gets 403.
- **Request body** (`application/json`, required):
  - `email`: email (required)
  - `password`: string (required)
- **Response 200:** `TokenResponse`: `access_token` (string), `token_type` (string)
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity, 429 Too Many Requests

### GET /auth/me

**Current user** — Return the authenticated user's identity, role and linked employee profile.

- **Access:** Any authenticated user
- **Rules:** Identity of the caller. The role is read from the `users` row on every request, not trusted from the JWT.
- **Response 200:** `MeResponse`: `user_id` (integer), `email` (string), `role` (string), `status` (string), `employee` (MeEmployee \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden

## Dashboard

### GET /dashboard/me

**Get My Dashboard** — Personal overview: today's attendance, month stats, leave balance, latest payslip; managers also get a team snapshot.

- **Access:** Any authenticated user
- **Rules:** Own overview. Managers also get `team` (direct reports: size, present today, on leave, pending leaves, members).
- **Response 200:** object: `employee` {id, employee_code, name, department, designation} | null, `month_label`, `today` {status, in_time, out_time} | null, `attendance` {present_days, absent_days, late_days, half_day_days, leave_days, total_working_minutes, total_overtime_minutes, attendance_percentage}, `leave_balance` [..], `latest_salary` {month, year, gross_salary, net_salary, pf, deductions, overtime_amount} | null, `team` (managers) {size, reference_date, present_today, on_leave_today, pending_leaves, members[]} | null
- **Errors:** 401 Unauthorized, 403 Forbidden

### GET /dashboard/summary

**Get HR Dashboard Summary** — Retrieve company-wide attendance, leave, overtime, and department metrics for the dashboard.

- **Access:** `hr`, `admin`
- **Rules:** Company-wide KPIs; `date` defaults to today, or the latest date with attendance (`is_fallback_date`).
- **Parameters:**
  - `date` (query, date \| null, optional) — Optional date to compute daily metrics for (YYYY-MM-DD). Defaults to today or latest record.
- **Response 200:** `DashboardSummaryResponse`: `reference_date` (string), `is_fallback_date` (boolean), `month` (string), `kpis` (KpiMetrics), `department_attendance` (array<DepartmentAttendanceItem>), `overtime_leaders` (array<OvertimeLeaderItem>), `late_leaders` (array<LateLeaderItem>), `leave_breakdown` (array<LeaveBreakdownItem>), `recent_leaves` (array<RecentLeaveItem>), `monthly_attendance` (array<MonthlyAttendanceItem>)
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

## Departments

### GET /departments

**List Departments**

- **Access:** `manager`, `hr`, `admin`
- **Rules:** Derived from `employees.department` (D-005). Manager -> only departments of self + direct reports.
- **Response 200:** array of `DepartmentResponse`: `name`, `employee_count`, `active_count`, `designations`, `managers`
- **Errors:** 401 Unauthorized, 403 Forbidden

## Documents

### GET /documents

**List Documents** — Optional `limit` / `offset` pagination; the total is in the `X-Total-Count` header.

- **Access:** Any authenticated user
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** Active documents for everyone; `include_archived=true` is honoured only for HR/Admin.
- **Parameters:**
  - `include_archived` (query, boolean, optional) — default `False`
  - `limit` (query, integer \| null, optional) — >= 1, <= 500
  - `offset` (query, integer, optional) — >= 0, default `0`
- **Response 200:** array of `DocumentResponse`: `id`, `name`, `file_name`, `file_type`, `version`, `status`, `uploaded_by`, `uploaded_by_name`, `upload_date`, `chunk_count`, `error_message`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /documents/upload

**Upload HR Document** — Upload a PDF, DOCX or TXT (max 10 MB). It is parsed, chunked and indexed for the AI assistant.

- **Access:** `hr`, `admin`
- **Rules:** Multipart. Only `.pdf`, `.docx`, `.txt`, max 10 MB (else 400); stored under a random file name. Same display name as an existing document -> new version, older versions archived (D-017). A file that cannot be parsed is still stored, with `status: failed` and `error_message`.
- **Request body** (`multipart/form-data`, required):
  - `file`: file (required)
  - `name`: string \| null
- **Response 201:** `DocumentResponse`: `id` (integer), `name` (string), `file_name` (string), `file_type` (string), `version` (integer), `status` (string), `uploaded_by` (integer), `uploaded_by_name` (string \| null), `upload_date` (datetime \| null), `chunk_count` (integer \| null), `error_message` (string \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### DELETE /documents/{document_id}

**Archive Document** — Removes the document from the AI index. The record and file are kept for audit.

- **Access:** `hr`, `admin`
- **Rules:** Archive (not a delete): chunks are removed from the AI index; the row and file are kept (D-017).
- **Parameters:**
  - `document_id` (path, integer, required)
- **Response 200:** `DocumentResponse`: `id` (integer), `name` (string), `file_name` (string), `file_type` (string), `version` (integer), `status` (string), `uploaded_by` (integer), `uploaded_by_name` (string \| null), `upload_date` (datetime \| null), `chunk_count` (integer \| null), `error_message` (string \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### GET /documents/{document_id}/download

**Download Document**

- **Access:** Any authenticated user
- **Rules:** Original file. Archived documents are 404 for non-HR roles.
- **Parameters:**
  - `document_id` (path, integer, required)
- **Response 200:** The file (`application/pdf`, `.docx` or `text/plain`) with `Content-Disposition: attachment`.
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### POST /documents/{document_id}/reindex

**Re-index Document**

- **Access:** `hr`, `admin`
- **Rules:** Re-parses and re-chunks the stored file.
- **Parameters:**
  - `document_id` (path, integer, required)
- **Response 200:** `DocumentResponse`: `id` (integer), `name` (string), `file_name` (string), `file_type` (string), `version` (integer), `status` (string), `uploaded_by` (integer), `uploaded_by_name` (string \| null), `upload_date` (datetime \| null), `chunk_count` (integer \| null), `error_message` (string \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

## Employees

### GET /employees

**List Employees** — Employee directory. HR/Admin see everyone; managers see themselves and their direct reports. Optional `limit` / `offset` pagination; the total is in the `X-Total-Count` header.

- **Access:** `manager`, `hr`, `admin`
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** Scope: HR/Admin -> everyone; manager -> self + direct reports (`employees.manager_id`). `monthly_gross_salary` is returned only to HR/Admin (managers get `null`). Without `limit` every matching row is returned (`X-Total-Count` is still set).
- **Parameters:**
  - `department` (query, string \| null, optional) — max length 100
  - `limit` (query, integer \| null, optional) — >= 1, <= 500
  - `offset` (query, integer, optional) — >= 0, default `0`
  - `search` (query, string \| null, optional) — max length 100
  - `status` (query, "active" \| "inactive" \| "terminated" \| "on_notice" \| null, optional)
- **Response 200:** array of `EmployeeDetailResponse`: `id`, `employee_code`, `name`, `department`, `designation`, `joining_date`, `status`, `manager_id`, `manager_name`, `email`, `role`, `monthly_gross_salary`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /employees

**Create Employee** — Create an employee profile. Supplying email + password also creates a login account.

- **Access:** `hr`, `admin`
- **Rules:** Supplying `email` + `password` also creates a login (`role`). Only an admin may create an `admin` login (403).
- **Request body** (`application/json`, required):
  - `employee_code`: string (required) — min length 1, max length 50
  - `name`: string (required) — min length 1, max length 255
  - `department`: string (required) — min length 1, max length 100
  - `designation`: string (required) — min length 1, max length 100
  - `joining_date`: date (required)
  - `status`: "active" \| "inactive" \| "terminated" \| "on_notice" — default `active`
  - `manager_id`: integer \| null
  - `email`: email \| null
  - `password`: string \| null — min length 8, max length 128
  - `role`: "employee" \| "manager" \| "hr" \| "admin" — default `employee`
  - `monthly_gross_salary`: number \| null — >= 0, <= 100000000
- **Response 201:** `EmployeeDetailResponse`: `id` (integer), `employee_code` (string), `name` (string), `department` (string), `designation` (string), `joining_date` (date), `status` (string), `manager_id` (integer \| null), `manager_name` (string \| null), `email` (string \| null), `role` (string \| null), `monthly_gross_salary` (number \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### GET /employees/me

**Get Current Employee Profile** — Returns the employee profile of the currently authenticated user (incl. manager name).

- **Access:** Any authenticated user
- **Rules:** The caller's own profile, including their own `monthly_gross_salary`.
- **Response 200:** `EmployeeDetailResponse`: `id` (integer), `employee_code` (string), `name` (string), `department` (string), `designation` (string), `joining_date` (date), `status` (string), `manager_id` (integer \| null), `manager_name` (string \| null), `email` (string \| null), `role` (string \| null), `monthly_gross_salary` (number \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### GET /employees/{employee_id}

**Get Employee By ID** — Employees may view only themselves, managers their team, HR/Admin anyone.

- **Access:** Any authenticated user
- **Rules:** Employee -> only themself; manager -> self + direct reports; HR/Admin -> anyone (else 403). `monthly_gross_salary` only for HR/Admin or the employee themself (D-021).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Response 200:** `EmployeeDetailResponse`: `id` (integer), `employee_code` (string), `name` (string), `department` (string), `designation` (string), `joining_date` (date), `status` (string), `manager_id` (integer \| null), `manager_name` (string \| null), `email` (string \| null), `role` (string \| null), `monthly_gross_salary` (number \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### PUT /employees/{employee_id}

**Update Employee**

- **Access:** `hr`, `admin`
- **Rules:** Partial update: only sent fields change; `null` is ignored except for `manager_id` (clears it).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Request body** (`application/json`, required):
  - `employee_code`: string \| null — min length 1, max length 50
  - `name`: string \| null — min length 1, max length 255
  - `department`: string \| null — min length 1, max length 100
  - `designation`: string \| null — min length 1, max length 100
  - `joining_date`: date \| null
  - `status`: "active" \| "inactive" \| "terminated" \| "on_notice" \| null
  - `manager_id`: integer \| null
  - `monthly_gross_salary`: number \| null — >= 0, <= 100000000
- **Response 200:** `EmployeeDetailResponse`: `id` (integer), `employee_code` (string), `name` (string), `department` (string), `designation` (string), `joining_date` (date), `status` (string), `manager_id` (integer \| null), `manager_name` (string \| null), `email` (string \| null), `role` (string \| null), `monthly_gross_salary` (number \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

### DELETE /employees/{employee_id}

**Deactivate Employee (soft delete)**

- **Access:** `hr`, `admin`
- **Rules:** Soft delete (D-006): employee status -> `inactive`, linked login -> `inactive`. You cannot deactivate yourself (400).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Response 200:** `EmployeeDetailResponse`: `id` (integer), `employee_code` (string), `name` (string), `department` (string), `designation` (string), `joining_date` (date), `status` (string), `manager_id` (integer \| null), `manager_name` (string \| null), `email` (string \| null), `role` (string \| null), `monthly_gross_salary` (number \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity

## Health

### GET /

**Root**

- **Access:** Public (no token)
- **Rules:** Health check used by the Docker healthcheck.
- **Response:** 200 `{"message": "AI HR Assistant is Running"}`

### GET /health

**Liveness**

- **Access:** Public (no token)
- **Response 200:** no body

### GET /health/ready

**Readiness (database reachable)**

- **Access:** Public (no token)
- **Response 200:** no body

## Holidays

### GET /holidays

**Holiday Calendar** — National and company holidays of one calendar year (default: current year).

- **Access:** Any authenticated user
- **Rules:** National holidays (defined in code) + company holidays declared by HR, for one year (default: current) (D-034).
- **Parameters:**
  - `year` (query, integer \| null, optional) — >= 2000, <= 2100
- **Response 200:** `HolidayListResponse`: `year` (integer), `items` (array<HolidayItem>)
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /holidays

**Declare Company Holiday** — HR / Admin. Weekends and national holidays are rejected. Payroll and leave counting exclude the date.

- **Access:** `hr`, `admin`
- **Rules:** Weekend date -> 422; national holiday or already declared -> 409. Excluded from payroll working days and leave counting.
- **Request body** (`application/json`, required):
  - `holiday_date`: date (required)
  - `name`: string (required) — min length 1, max length 255
- **Response 201:** `HolidayItem`: `id` (integer \| null), `date` (date), `name` (string), `kind` (string), `weekday` (string)
- **Errors:** 401 Unauthorized, 403 Forbidden, 409 Conflict, 422 Unprocessable Entity

### DELETE /holidays/{holiday_id}

**Remove Company Holiday**

- **Access:** `hr`, `admin`
- **Rules:** Removes a declared company holiday. National holidays have no id and cannot be removed.
- **Parameters:**
  - `holiday_id` (path, integer, required)
- **Response 204:** no body
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

## Leaves

### GET /leaves

**List Leave Requests** — HR/Admin see all requests; managers see their team's requests. Optional `limit` / `offset` pagination; the total is in the `X-Total-Count` header.

- **Access:** `manager`, `hr`, `admin`
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** HR/Admin -> all requests; manager -> self + direct reports (includes the manager's own, KI-021).
- **Parameters:**
  - `employee_id` (query, integer \| null, optional)
  - `limit` (query, integer \| null, optional) — >= 1, <= 500
  - `offset` (query, integer, optional) — >= 0, default `0`
  - `status` (query, "pending" \| "approved" \| "rejected" \| "cancelled" \| null, optional)
- **Response 200:** array of `LeaveListItem`: `id`, `employee_id`, `employee_name`, `employee_code`, `department`, `leave_type`, `from_date`, `to_date`, `days`, `status`, `reason`, `applied_at`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /leaves

**Create a Leave Request** — Submits a new leave request for the authenticated employee.

- **Access:** Any authenticated user
- **Rules:** Creates a `pending` request for the caller.
- **Request body** (`application/json`, required):
  - `leave_type`: LeaveType ("casual" \| "sick" \| "earned" \| "unpaid" \| "maternity" \| "paternity") (required)
  - `start_date`: date (required)
  - `end_date`: date (required)
  - `reason`: string \| null
- **Response 201:** `LeaveResponse`: `id` (integer), `employee_id` (integer), `leave_type` (string), `from_date` (date), `to_date` (date), `status` (string), `reason` (string \| null)
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### GET /leaves/balance/me

**Get My Leave Balance** — Entitled / used / pending / remaining working days per leave type for a calendar year.

- **Access:** Any authenticated user
- **Rules:** Entitled / used / pending / remaining **working days** per type for a calendar year (default: current). Weekends and holidays are not charged (D-008, D-034).
- **Parameters:**
  - `year` (query, integer \| null, optional) — >= 2000, <= 2100
- **Response 200:** array of `LeaveBalanceItem`: `leave_type`, `year`, `entitled`, `used`, `pending`, `remaining`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### GET /leaves/me

**Get My Leaves** — Returns all leave requests for the authenticated employee.

- **Access:** Any authenticated user
- **Rules:** The caller's own requests.
- **Response 200:** array of `LeaveResponse`: `id`, `employee_id`, `leave_type`, `from_date`, `to_date`, `status`, `reason`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### GET /leaves/{employee_id}

**Get Employee Leaves** — Allows HR or Admin to fetch leave records for a specific employee.

- **Access:** `hr`, `admin`
- **Rules:** Any employee's leave records (HR/Admin).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Response 200:** array of `LeaveResponse`: `id`, `employee_id`, `leave_type`, `from_date`, `to_date`, `status`, `reason`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### POST /leaves/{leave_id}/cancel

**Cancel My Pending Leave**

- **Access:** Any authenticated user
- **Rules:** Cancel your own pending request (not yours -> 404; not pending -> 400).
- **Parameters:**
  - `leave_id` (path, integer, required)
- **Response 200:** `LeaveResponse`: `id` (integer), `employee_id` (integer), `leave_type` (string), `from_date` (date), `to_date` (date), `status` (string), `reason` (string \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

### PATCH /leaves/{leave_id}/status

**Approve or Reject Leave** — Allows HR, Managers, or Admins to approve or reject a pending leave request.

- **Access:** `manager`, `hr`, `admin`
- **Rules:** Nobody approves their own leave, any role (403, D-022). Manager -> direct reports only (403). Only `pending` requests can change (400).
- **Parameters:**
  - `leave_id` (path, integer, required)
- **Request body** (`application/json`, required):
  - `status`: "approved" \| "rejected" (required)
- **Response 200:** `LeaveResponse`: `id` (integer), `employee_id` (integer), `leave_type` (string), `from_date` (date), `to_date` (date), `status` (string), `reason` (string \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

## Reports

### GET /reports/attendance

**Export Attendance Report (Excel)** — Summary sheet (Present/Absent/Half Day/Late Count/Working & OT minutes per employee) + daily records. HR & Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Period: `month`+`year`, or `year`, or `date_from`/`date_to`; `month` without `year` -> 422 (D-013).
- **Parameters:**
  - `date_from` (query, date \| null, optional) — Start date (YYYY-MM-DD)
  - `date_to` (query, date \| null, optional) — End date (YYYY-MM-DD)
  - `department` (query, string \| null, optional) — max length 100
  - `month` (query, integer \| null, optional) — >= 1, <= 12
  - `year` (query, integer \| null, optional) — >= 2000, <= 2100
- **Response 200:** `.xlsx` file (`Content-Disposition: attachment; filename="attendance_report_<period>.xlsx"`): Summary sheet + daily records.
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /reports/leave

**Export Leave Report (Excel)** — Employee, leave type, leave days (working days) and status for leaves overlapping the period. HR & Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Same period filters; leave days are working days.
- **Parameters:**
  - `date_from` (query, date \| null, optional) — Start date (YYYY-MM-DD)
  - `date_to` (query, date \| null, optional) — End date (YYYY-MM-DD)
  - `department` (query, string \| null, optional) — max length 100
  - `month` (query, integer \| null, optional) — >= 1, <= 12
  - `year` (query, integer \| null, optional) — >= 2000, <= 2100
- **Response 200:** `.xlsx` file: employee, leave type, working days, status.
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /reports/overtime

**Export Overtime Report (Excel)** — Summary sheet (OT hours + OT amount per employee) + overtime sessions. HR & Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Same period filters as the attendance report. OT amount uses the payroll engine's hourly OT rate (D-021).
- **Parameters:**
  - `date_from` (query, date \| null, optional) — Start date (YYYY-MM-DD)
  - `date_to` (query, date \| null, optional) — End date (YYYY-MM-DD)
  - `department` (query, string \| null, optional) — max length 100
  - `month` (query, integer \| null, optional) — >= 1, <= 12
  - `year` (query, integer \| null, optional) — >= 2000, <= 2100
- **Response 200:** `.xlsx` file: Summary sheet (OT hours, OT amount per employee) + overtime sessions.
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

## Salary

### GET /salary

**Get Payroll Sheet** — Salary records for one month (default: latest month with data). HR / Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Payroll register for one month (default: latest month with salary rows).
- **Parameters:**
  - `month` (query, integer \| null, optional) — Month (1-12)
  - `year` (query, integer \| null, optional) — Year
- **Response 200:** `PayrollResponse`: `month` (integer \| null), `year` (integer \| null), `items` (array<PayrollItem>)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /salary/generate

**Generate Payroll** — Compute salary rows for a month from each employee's monthly gross salary, attendance and leave (LOP for absences / half days / unpaid leave, PF, overtime pay). Idempotent: unpaid rows are updated, paid rows are locked. HR / Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Payroll engine (D-021): LOP for absences / half days / approved unpaid leave, PF 12 % of earned basic, overtime at 1.5x. Idempotent: unpaid rows are updated, paid rows are skipped (locked). Future month -> 400; current month -> `provisional: true`.
- **Request body** (`application/json`, required):
  - `month`: integer (required) — >= 1, <= 12
  - `year`: integer (required) — >= 2000, <= 2100
  - `employee_ids`: array<integer> \| null — Limit generation to these employees (default: all active employees).
- **Response 200:** `PayrollGenerateResponse`: `month` (integer), `year` (integer), `working_days` (integer), `provisional` (boolean), `created` (integer), `updated` (integer), `skipped` (array<PayrollSkipItem>), `items` (array<PayrollLineItem>)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### POST /salary/mark-paid

**Mark Salaries As Paid** — Sets paid_at on the given unpaid salary rows. Paid rows are locked: payroll generation skips them and attendance for that month can no longer be corrected. Irreversible. HR / Admin only.

- **Access:** `hr`, `admin`
- **Rules:** Sets `paid_at` on unpaid rows (D-036). **Irreversible**: paid rows are skipped by payroll generation and attendance of that month can no longer be corrected or edited.
- **Request body** (`application/json`, required):
  - `salary_ids`: array<integer> (required) — min items 1, max items 1000
- **Response 200:** `MarkPaidResponse`: `marked` (array<integer>), `already_paid` (array<integer>), `not_found` (array<integer>), `paid_at` (datetime)
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /salary/me

**Get My Salary** — Returns all salary records for the authenticated employee.

- **Access:** Any authenticated user
- **Rules:** The caller's own payslips.
- **Response 200:** array of `SalaryResponse`: `id`, `employee_id`, `month`, `year`, `gross_salary`, `pf`, `deductions`, `overtime_amount`, `net_salary`, `paid_at`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found

### GET /salary/summary

**Get Salary Summary** — Allows HR or Admin to retrieve aggregated salary statistics with optional month and year filtering.

- **Access:** `hr`, `admin`
- **Rules:** Totals for a month / year / all time.
- **Parameters:**
  - `month` (query, integer \| null, optional) — Month (1-12) to filter by
  - `year` (query, integer \| null, optional) — Year to filter by
- **Response 200:** `SalarySummaryResponse`: `month` (integer \| null), `year` (integer \| null), `total_records` (integer), `total_employees` (integer), `record_count` (integer), `employee_count` (integer), `total_gross_salary` (number), `total_pf` (number), `total_deductions` (number), `total_overtime_amount` (number), `total_net_salary` (number)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### GET /salary/{employee_id}

**Get Employee Salary** — Allows HR or Admin to fetch salary records for a specific employee.

- **Access:** `hr`, `admin`
- **Rules:** Any employee's salary rows (HR/Admin only — never managers, D-010).
- **Parameters:**
  - `employee_id` (path, integer, required)
- **Response 200:** array of `SalaryResponse`: `id`, `employee_id`, `month`, `year`, `gross_salary`, `pf`, `deductions`, `overtime_amount`, `net_salary`, `paid_at`
- **Errors:** 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity

## Users

### GET /users

**List Users**

- **Access:** `admin`
- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header
- **Rules:** All login accounts with linked employee.
- **Parameters:**
  - `limit` (query, integer \| null, optional) — >= 1, <= 500
  - `offset` (query, integer, optional) — >= 0, default `0`
- **Response 200:** array of `UserResponse`: `id`, `email`, `role`, `status`, `employee_id`, `employee_name`, `employee_code`, `has_password`, `has_google`, `created_at`
- **Errors:** 401 Unauthorized, 403 Forbidden, 422 Unprocessable Entity

### PATCH /users/{user_id}

**Update User Role / Status**

- **Access:** `admin`
- **Rules:** Change role and/or status. An admin cannot change their own role or deactivate themself (400).
- **Parameters:**
  - `user_id` (path, integer, required)
- **Request body** (`application/json`, required):
  - `role`: "employee" \| "manager" \| "hr" \| "admin" \| null
  - `status`: "active" \| "inactive" \| null
- **Response 200:** `UserResponse`: `id` (integer), `email` (string), `role` (string), `status` (string), `employee_id` (integer), `employee_name` (string \| null), `employee_code` (string \| null), `has_password` (boolean), `has_google` (boolean), `created_at` (datetime \| null)
- **Errors:** 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity
