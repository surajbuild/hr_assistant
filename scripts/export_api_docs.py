"""
scripts/export_api_docs.py
--------------------------
Generate docs/API.md from the live FastAPI application (PRD §33 "Document every API").

    python scripts/export_api_docs.py            # writes docs/API.md
    python scripts/export_api_docs.py --check    # exit 1 if docs/API.md is out of date

How it works
------------
1. Imports `app.main.app` (needs `.env` with valid >= 32-byte JWT_SECRET_KEY / SESSION_SECRET_KEY, like the
   backend itself). Importing does not open a database connection or touch any data.
2. Walks every route (also inside included routers) and reads `app.openapi()` for summaries, parameters,
   request bodies, response models and status codes.
3. Derives the **required roles** from each route's dependency tree:
     - a `require_role(...)` closure (app/utils/dependencies.py) -> its `allowed_roles`
     - `get_current_user` only                                  -> any authenticated user
     - neither                                                  -> public
4. Derives **error status codes** from the route function's source (and the module-level helper functions it
   calls): every `status.HTTP_4xx/5xx` constant, plus 429 when it calls `rate_limit.enforce`, plus 401/403 from
   the auth dependencies and 422 from FastAPI request validation.
5. Adds the hand-written ownership/scope notes in ROUTE_NOTES (data scope rules can't be read from a decorator).
   Every key in ROUTE_NOTES / RESPONSE_OVERRIDES must match a real route, otherwise the script fails — so the
   notes cannot silently drift from the code.

The output is deterministic (sorted tags and routes, no timestamps), so re-running it on unchanged code
produces an identical file.
"""

import argparse
import inspect
import os
import re
import sys
import warnings
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # app.ai.llm / dotenv read ./.env

warnings.filterwarnings("ignore")  # GET+HEAD /auth/google/login share an operation id

from fastapi.routing import APIRoute  # noqa: E402

from app.main import app  # noqa: E402
from app.utils.dependencies import get_current_user  # noqa: E402

OUTPUT = os.path.join(ROOT, "docs", "API.md")
METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
ROLE_ORDER = ["employee", "manager", "hr", "admin"]

STATUS_TEXT = {
    200: "OK", 201: "Created", 204: "No Content", 302: "Found (redirect)", 400: "Bad Request",
    401: "Unauthorized", 403: "Forbidden", 404: "Not Found", 409: "Conflict",
    422: "Unprocessable Entity", 429: "Too Many Requests", 502: "Bad Gateway",
}

# ---------------------------------------------------------------------------
# Hand-maintained notes (verified against app/api/*.py and app/services/*.py)
# Key: "METHOD /path" exactly as FastAPI registers it.
# ---------------------------------------------------------------------------

ROUTE_NOTES: Dict[str, str] = {
    "GET /": "Health check used by the Docker healthcheck.",
    # Authentication
    "POST /auth/login": (
        "Rate limited (D-031): all attempts per client IP (default 30/min) and failed attempts per "
        "(client IP, email) (default 5 per 15 min) -> 429 + `Retry-After`. A wrong email and a wrong password "
        "both return the same generic 401 `Invalid email or password.`; an inactive account gets 403."
    ),
    "GET /auth/me": "Identity of the caller. The role is read from the `users` row on every request, not trusted from the JWT.",
    "GET /auth/google/login": (
        "302 to Google's consent screen (Authlib stores the OAuth state in the session cookie). "
        "`?next=frontend` makes the callback redirect to the SPA instead of returning JSON. "
        "The SPA opens it through the proxy: `/api/auth/google/login?next=frontend`."
    ),
    "GET /auth/google/callback": (
        "Exchanges the Google code, then: known `google_id` -> that user; known email without a Google id -> "
        "links it (409 if the email is linked to a different Google account); otherwise provisions a new "
        "`employee` user + employee profile (department `General`). Returns the JSON below, or 302 to "
        "`FRONTEND_URL/login#token=<jwt>` when the login was started with `?next=frontend` (D-014)."
    ),
    # Employees
    "GET /employees/me": "The caller's own profile, including their own `monthly_gross_salary`.",
    "GET /employees": (
        "Scope: HR/Admin -> everyone; manager -> self + direct reports (`employees.manager_id`). "
        "`monthly_gross_salary` is returned only to HR/Admin (managers get `null`). "
        "Without `limit` every matching row is returned (`X-Total-Count` is still set)."
    ),
    "GET /employees/{employee_id}": (
        "Employee -> only themself; manager -> self + direct reports; HR/Admin -> anyone (else 403). "
        "`monthly_gross_salary` only for HR/Admin or the employee themself (D-021)."
    ),
    "POST /employees": (
        "Supplying `email` + `password` also creates a login (`role`). Only an admin may create an `admin` login (403)."
    ),
    "PUT /employees/{employee_id}": "Partial update: only sent fields change; `null` is ignored except for `manager_id` (clears it).",
    "DELETE /employees/{employee_id}": (
        "Soft delete (D-006): employee status -> `inactive`, linked login -> `inactive`. You cannot deactivate yourself (400)."
    ),
    # Departments
    "GET /departments": "Derived from `employees.department` (D-005). Manager -> only departments of self + direct reports.",
    # Attendance
    "GET /attendance/me": "The caller's own records.",
    "POST /attendance": "HR/Admin create a record for any employee; 409 if that employee already has a record for the date.",
    "GET /attendance/summary": "The caller's own aggregated counts (calculated in SQL/Python, PRD §20).",
    "GET /attendance/today": "The caller's record for today, or `null`.",
    "POST /attendance/check-in": "Creates today's record with the server clock; late when after 09:15 (D-007). 409 if already checked in.",
    "POST /attendance/check-out": (
        "Server computes working / overtime / late minutes and present vs half day (D-007). "
        "409 if not checked in or already checked out."
    ),
    "GET /attendance/daily": (
        "One row per in-scope active employee for a date (default: today, or the latest date with data -> "
        "`is_fallback_date`). Manager -> self + direct reports."
    ),
    "GET /attendance/records": (
        "Manager -> self + direct reports; an `employee_id` outside the scope -> 403. Newest first."
    ),
    "PUT /attendance/records/{record_id}": (
        "HR/Admin direct edit (D-033). Not your own record (403); not in a month whose salary is paid (409). "
        "`present`/`half_day` need `in_time` and `out_time`; status and minutes are recomputed by the server."
    ),
    "POST /attendance/corrections": (
        "Correction request for one of the caller's own days (D-033). Future date / before joining / out <= in -> 422; "
        "a pending request for the same date or a paid month -> 409."
    ),
    "GET /attendance/corrections/me": "The caller's own correction requests.",
    "GET /attendance/corrections": "Requests to review. HR/Admin -> everyone's; manager -> direct reports'. The caller's own requests are excluded.",
    "POST /attendance/corrections/{correction_id}/approve": (
        "Applies the requested times to the attendance row. Never your own request (403); manager -> team only (403); "
        "not pending (409); month already paid (409)."
    ),
    "POST /attendance/corrections/{correction_id}/reject": "Never your own request (403); manager -> team only (403); not pending (409).",
    "POST /attendance/corrections/{correction_id}/cancel": "Withdraw your own pending request (someone else's -> 404).",
    "GET /attendance/{employee_id}": "Any employee's records (HR/Admin).",
    # Leaves
    "POST /leaves": "Creates a `pending` request for the caller.",
    "GET /leaves/me": "The caller's own requests.",
    "GET /leaves/balance/me": (
        "Entitled / used / pending / remaining **working days** per type for a calendar year (default: current). "
        "Weekends and holidays are not charged (D-008, D-034)."
    ),
    "GET /leaves": "HR/Admin -> all requests; manager -> self + direct reports (includes the manager's own, KI-021).",
    "PATCH /leaves/{leave_id}/status": (
        "Nobody approves their own leave, any role (403, D-022). Manager -> direct reports only (403). "
        "Only `pending` requests can change (400)."
    ),
    "POST /leaves/{leave_id}/cancel": "Cancel your own pending request (not yours -> 404; not pending -> 400).",
    "GET /leaves/{employee_id}": "Any employee's leave records (HR/Admin).",
    # Salary
    "GET /salary/me": "The caller's own payslips.",
    "GET /salary": "Payroll register for one month (default: latest month with salary rows).",
    "GET /salary/summary": "Totals for a month / year / all time.",
    "POST /salary/generate": (
        "Payroll engine (D-021): LOP for absences / half days / approved unpaid leave, PF 12 % of earned basic, "
        "overtime at 1.5x. Idempotent: unpaid rows are updated, paid rows are skipped (locked). "
        "Future month -> 400; current month -> `provisional: true`."
    ),
    "POST /salary/mark-paid": (
        "Sets `paid_at` on unpaid rows (D-036). **Irreversible**: paid rows are skipped by payroll generation and "
        "attendance of that month can no longer be corrected or edited."
    ),
    "GET /salary/{employee_id}": "Any employee's salary rows (HR/Admin only — never managers, D-010).",
    # Holidays
    "GET /holidays": "National holidays (defined in code) + company holidays declared by HR, for one year (default: current) (D-034).",
    "POST /holidays": "Weekend date -> 422; national holiday or already declared -> 409. Excluded from payroll working days and leave counting.",
    "DELETE /holidays/{holiday_id}": "Removes a declared company holiday. National holidays have no id and cannot be removed.",
    # Documents
    "POST /documents/upload": (
        "Multipart. Only `.pdf`, `.docx`, `.txt`, max 10 MB (else 400); stored under a random file name. "
        "Same display name as an existing document -> new version, older versions archived (D-017). "
        "A file that cannot be parsed is still stored, with `status: failed` and `error_message`."
    ),
    "GET /documents": "Active documents for everyone; `include_archived=true` is honoured only for HR/Admin.",
    "POST /documents/{document_id}/reindex": "Re-parses and re-chunks the stored file.",
    "DELETE /documents/{document_id}": "Archive (not a delete): chunks are removed from the AI index; the row and file are kept (D-017).",
    "GET /documents/{document_id}/download": "Original file. Archived documents are 404 for non-HR roles.",
    # Chat
    "POST /chat": (
        "Rate limited per user (default 20/min, D-031) -> 429. Send `message` (or legacy `question`), max 1000 "
        "characters; blank -> 400. Refusals (prompt injection, RBAC) are returned as 200 with "
        "`confidence: access_denied` and never reach the LLM. Every call writes a `chat_logs` row. See docs/AI.md."
    ),
    "GET /chat/history": "The caller's own last `limit` questions and answers (oldest first).",
    "GET /chat/logs": "Audit log of every chat interaction, newest first; `search` matches question or user email.",
    # Dashboard
    "GET /dashboard/summary": "Company-wide KPIs; `date` defaults to today, or the latest date with attendance (`is_fallback_date`).",
    "GET /dashboard/me": (
        "Own overview. Managers also get `team` (direct reports: size, present today, on leave, pending leaves, members)."
    ),
    # Reports
    "GET /reports/attendance": "Period: `month`+`year`, or `year`, or `date_from`/`date_to`; `month` without `year` -> 422 (D-013).",
    "GET /reports/overtime": "Same period filters as the attendance report. OT amount uses the payroll engine's hourly OT rate (D-021).",
    "GET /reports/leave": "Same period filters; leave days are working days.",
    # Users
    "GET /users": "All login accounts with linked employee.",
    "PATCH /users/{user_id}": "Change role and/or status. An admin cannot change their own role or deactivate themself (400).",
}

# Responses that have no Pydantic response model (files, redirects, untyped dicts).
RESPONSE_OVERRIDES: Dict[str, str] = {
    "GET /documents/{document_id}/download": "The file (`application/pdf`, `.docx` or `text/plain`) with `Content-Disposition: attachment`.",
    "GET /reports/attendance": "`.xlsx` file (`Content-Disposition: attachment; filename=\"attendance_report_<period>.xlsx\"`): Summary sheet + daily records.",
    "GET /reports/overtime": "`.xlsx` file: Summary sheet (OT hours, OT amount per employee) + overtime sessions.",
    "GET /reports/leave": "`.xlsx` file: employee, leave type, working days, status.",
    "GET /dashboard/me": (
        "object: `employee` {id, employee_code, name, department, designation} | null, `month_label`, "
        "`today` {status, in_time, out_time} | null, `attendance` {present_days, absent_days, late_days, half_day_days, "
        "leave_days, total_working_minutes, total_overtime_minutes, attendance_percentage}, `leave_balance` [..], "
        "`latest_salary` {month, year, gross_salary, net_salary, pf, deductions, overtime_amount} | null, "
        "`team` (managers) {size, reference_date, present_today, on_leave_today, pending_leaves, members[]} | null"
    ),
}

# Non-JSON success responses that the OpenAPI schema cannot describe.
SUCCESS_OVERRIDES: Dict[str, str] = {
    "GET /": "200 `{\"message\": \"AI HR Assistant is Running\"}`",
    "GET /auth/google/login": "302 redirect to Google's consent screen (no body)",
    "GET /auth/google/callback": (
        "302 to `FRONTEND_URL/login#token=<jwt>` instead of the JSON above when the login was started with "
        "`?next=frontend`"
    ),
}

# Error codes a route can return that are not visible in its own source.
EXTRA_CODES: Dict[str, Set[int]] = {}


# ---------------------------------------------------------------------------
# Route discovery
# ---------------------------------------------------------------------------

def iter_api_routes(routes: Iterable[Any]) -> Iterable[APIRoute]:
    """Yield APIRoutes, descending into included routers (FastAPI wraps them in _IncludedRouter)."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from iter_api_routes(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from iter_api_routes(route.routes)


def walk_calls(dependant: Any) -> Iterable[Any]:
    for dep in getattr(dependant, "dependencies", []) or []:
        if dep.call is not None:
            yield dep.call
        yield from walk_calls(dep)


def access_for(route: APIRoute) -> Tuple[str, Optional[Tuple[str, ...]]]:
    """('public' | 'authenticated' | 'roles', allowed_roles)."""
    roles: Optional[Tuple[str, ...]] = None
    authenticated = False
    for call in walk_calls(route.dependant):
        if call is get_current_user:
            authenticated = True
        code = getattr(call, "__code__", None)
        if code is not None and "allowed_roles" in code.co_freevars and call.__closure__:
            cell = call.__closure__[code.co_freevars.index("allowed_roles")]
            roles = tuple(cell.cell_contents)
    if roles is not None:
        return "roles", roles
    return ("authenticated", None) if authenticated else ("public", None)


def format_access(kind: str, roles: Optional[Tuple[str, ...]]) -> str:
    if kind == "public":
        return "Public (no token)"
    if kind == "authenticated":
        return "Any authenticated user"
    ordered = sorted(roles or (), key=lambda r: ROLE_ORDER.index(r) if r in ROLE_ORDER else 99)
    return ", ".join(f"`{r}`" for r in ordered)


# ---------------------------------------------------------------------------
# Status codes from source
# ---------------------------------------------------------------------------

_HTTP_CONST = re.compile(r"HTTP_(\d{3})_")
_NAME = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _source_with_helpers(func: Any, depth: int = 3) -> str:
    """Source of `func` plus module-level helper functions it calls (same module), recursively."""
    module = sys.modules.get(func.__module__)
    seen: Set[str] = set()
    parts: List[str] = []

    def visit(fn: Any, level: int) -> None:
        if fn.__name__ in seen:
            return
        seen.add(fn.__name__)
        try:
            src = inspect.getsource(fn)
        except (OSError, TypeError):
            return
        parts.append(src)
        if level >= depth or module is None:
            return
        for name in sorted(set(_NAME.findall(src))):
            helper = getattr(module, name, None)
            if inspect.isfunction(helper) and helper.__module__ == func.__module__ and helper is not fn:
                visit(helper, level + 1)

    visit(func, 0)
    return "\n".join(parts)


def error_codes(route: APIRoute, key: str, kind: str, has_validation: bool) -> List[int]:
    src = _source_with_helpers(route.endpoint)
    # Ignore the decorator's success status_code
    body = src.split("def ", 1)[1] if "def " in src else src
    codes = {int(c) for c in _HTTP_CONST.findall(body) if int(c) >= 400}
    if "rate_limit.enforce" in src:
        codes.add(429)
    if kind != "public":
        codes.update({401, 403})  # missing/invalid token; inactive account or wrong role
    if has_validation:
        codes.add(422)
    codes |= EXTRA_CODES.get(key, set())
    return sorted(codes)


# ---------------------------------------------------------------------------
# OpenAPI schema rendering
# ---------------------------------------------------------------------------

SCHEMA: Dict[str, Any] = {}


def resolve(schema: Dict[str, Any]) -> Dict[str, Any]:
    ref = schema.get("$ref")
    if ref:
        return SCHEMA["components"]["schemas"][ref.split("/")[-1]]
    return schema


def type_str(schema: Dict[str, Any]) -> str:
    if not schema:
        return "any"
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        target = resolve(schema)
        if "enum" in target:  # spell out enum values, e.g. AttendanceStatus ("present" | "absent" | ...)
            return f"{name} (" + " \\| ".join(f'"{v}"' for v in target["enum"]) + ")"
        return name
    if "anyOf" in schema or "oneOf" in schema:
        options = schema.get("anyOf") or schema.get("oneOf")
        return " \\| ".join(type_str(o) for o in options)
    if "enum" in schema:
        return " \\| ".join(f'"{v}"' for v in schema["enum"])
    if "const" in schema:
        return f'"{schema["const"]}"'
    t = schema.get("type")
    if t == "string" and "contentMediaType" in schema:  # multipart file upload (OpenAPI 3.1)
        return "file"
    if t == "array":
        return f"array<{type_str(schema.get('items', {}))}>"
    if t == "string" and schema.get("format") in ("date", "date-time", "time", "email", "binary"):
        return {"date-time": "datetime", "binary": "file"}.get(schema["format"], schema["format"])
    if t == "object" and "additionalProperties" in schema:
        return f"map<string, {type_str(schema['additionalProperties'])}>"
    return t or "any"


def constraints(schema: Dict[str, Any]) -> str:
    flat = dict(schema)
    for option in schema.get("anyOf", []):
        if option.get("type") != "null":
            flat.update(option)
    out = []
    for key, label in (("minLength", "min length"), ("maxLength", "max length"), ("minimum", ">="),
                       ("maximum", "<="), ("minItems", "min items"), ("maxItems", "max items")):
        if key in flat:
            value = flat[key]
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            out.append(f"{label} {value}")
    if "default" in schema and schema["default"] is not None:
        out.append(f"default `{schema['default']}`")
    return ", ".join(out)


def model_fields(schema: Dict[str, Any]) -> List[Tuple[str, str, bool, str]]:
    # Optional body (`Model | None`) -> document the model's fields
    for option in schema.get("anyOf", []):
        if "$ref" in option:
            schema = option
            break
    target = resolve(schema)
    required = set(target.get("required", []))
    rows = []
    for name, prop in target.get("properties", {}).items():
        rows.append((name, type_str(prop), name in required, constraints(prop) or prop.get("description", "")))
    return rows


def response_shape(schema: Dict[str, Any]) -> str:
    """One-line description of a response body: top-level fields (and the item fields of arrays)."""
    if "anyOf" in schema:
        non_null = [o for o in schema["anyOf"] if o.get("type") != "null"]
        nullable = len(non_null) != len(schema["anyOf"])
        if len(non_null) == 1:
            return response_shape(non_null[0]) + (" — or `null`" if nullable else "")
    if schema.get("type") == "array":
        items = schema.get("items", {})
        inner = resolve(items)
        if inner.get("properties"):
            return f"array of `{type_str(items)}`: " + ", ".join(f"`{n}`" for n in inner["properties"])
        return f"array<{type_str(items)}>"
    target = resolve(schema)
    if target.get("properties"):
        fields = []
        for name, prop in target["properties"].items():
            t = type_str(prop)
            fields.append(f"`{name}` ({t})")
        name = schema["$ref"].split("/")[-1] if "$ref" in schema else "object"
        return f"`{name}`: " + ", ".join(fields)
    return type_str(schema)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

HEADER = """# API Reference

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
"""


def render() -> str:
    global SCHEMA
    SCHEMA = app.openapi()
    paths = SCHEMA["paths"]

    entries = []
    seen_keys: Set[str] = set()
    for route in iter_api_routes(app.routes):
        if not route.include_in_schema:
            continue
        methods = sorted(m for m in route.methods if m != "HEAD")
        for method in methods:
            key = f"{method} {route.path}"
            seen_keys.add(key)
            op = paths.get(route.path, {}).get(method.lower())
            if op is None:
                continue
            tag = (op.get("tags") or ["Other"])[0]
            entries.append((tag, route, method, key, op, "HEAD" in route.methods))

    stale = sorted(
        (set(ROUTE_NOTES) | set(RESPONSE_OVERRIDES) | set(SUCCESS_OVERRIDES) | set(EXTRA_CODES)) - seen_keys
    )
    if stale:
        raise SystemExit(f"ERROR: notes refer to routes that no longer exist: {stale}")

    entries.sort(key=lambda e: (e[0].lower(), e[1].path, METHOD_ORDER.get(e[2], 9)))
    tags = sorted({e[0] for e in entries}, key=str.lower)

    out: List[str] = [HEADER]

    # Index
    out.append("## Endpoint index\n")
    out.append(f"{len(entries)} operations in {len(tags)} groups.\n")
    out.append("| Group | Method | Path | Access | Summary |")
    out.append("|---|---|---|---|---|")
    for tag, route, method, key, op, _ in entries:
        kind, roles = access_for(route)
        # GitHub-style heading anchor: lowercase, punctuation except "-" / "_" removed, spaces -> "-"
        anchor = re.sub(r"[^a-z0-9 _-]", "", f"{method} {route.path}".lower()).replace(" ", "-")
        out.append(
            f"| {tag} | `{method}` | [`{route.path}`](#{anchor}) | {format_access(kind, roles)} | {op.get('summary', '')} |"
        )
    out.append("")

    for tag in tags:
        out.append(f"## {tag}\n")
        for etag, route, method, key, op, has_head in entries:
            if etag != tag:
                continue
            kind, roles = access_for(route)
            out.append(f"### {method} {route.path}\n")
            summary = op.get("summary", "")
            description = (op.get("description") or "").strip()
            line = f"**{summary}**" if summary else ""
            if description and description != summary:
                line += (" — " if line else "") + " ".join(description.split())
            if line:
                out.append(line + "\n")

            out.append(f"- **Access:** {format_access(kind, roles)}")
            if has_head:
                out.append("- **Also answers:** `HEAD`")
            src = _source_with_helpers(route.endpoint)
            if "set_total_count" in src:
                out.append("- **Paginated (D-035):** `limit` / `offset`, total in the `X-Total-Count` header")
            if key in ROUTE_NOTES:
                out.append(f"- **Rules:** {ROUTE_NOTES[key]}")

            params = op.get("parameters", [])
            if params:
                out.append("- **Parameters:**")
                for p in sorted(params, key=lambda p: ({"path": 0, "query": 1, "header": 2}.get(p["in"], 3), p["name"])):
                    schema = p.get("schema", {})
                    bits = [p["in"], type_str(schema), "required" if p.get("required") else "optional"]
                    extra = constraints(schema)
                    desc = p.get("description") or schema.get("description") or ""
                    detail = "; ".join(x for x in (extra, desc) if x)
                    out.append(f"  - `{p['name']}` ({', '.join(bits)}){' — ' + detail if detail else ''}")

            body = op.get("requestBody")
            if body:
                content_type, media = sorted(body["content"].items())[0]
                out.append(f"- **Request body** (`{content_type}`{', required' if body.get('required') else ''}):")
                fields = model_fields(media.get("schema", {}))
                if fields:
                    for name, t, req, extra in fields:
                        out.append(f"  - `{name}`: {t}{' (required)' if req else ''}{' — ' + extra if extra else ''}")
                else:
                    out.append(f"  - {type_str(media.get('schema', {}))}")

            responses = op.get("responses", {})
            success = sorted(c for c in responses if c.startswith("2"))
            if key in RESPONSE_OVERRIDES:
                out.append(f"- **Response {success[0] if success else '200'}:** {RESPONSE_OVERRIDES[key]}")
            elif key in SUCCESS_OVERRIDES and not any(
                responses[c].get("content", {}).get("application/json", {}).get("schema") for c in success
            ):
                out.append(f"- **Response:** {SUCCESS_OVERRIDES[key]}")
            else:
                for code in success:
                    content = responses[code].get("content", {}).get("application/json")
                    if content and content.get("schema"):
                        out.append(f"- **Response {code}:** {response_shape(content['schema'])}")
                    else:
                        out.append(f"- **Response {code}:** no body")
                if key in SUCCESS_OVERRIDES:
                    out.append(f"- **Alternative response:** {SUCCESS_OVERRIDES[key]}")

            has_validation = "422" in responses
            errs = error_codes(route, key, kind, has_validation)
            if errs:
                out.append("- **Errors:** " + ", ".join(f"{c} {STATUS_TEXT.get(c, '')}".strip() for c in errs))
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/API.md from the FastAPI app.")
    parser.add_argument("--check", action="store_true", help="Fail if docs/API.md is not up to date.")
    args = parser.parse_args()

    content = render()
    if args.check:
        try:
            with open(OUTPUT, "r", encoding="utf-8") as fh:
                current = fh.read()
        except FileNotFoundError:
            current = ""
        if current != content:
            print("docs/API.md is out of date — run: python scripts/export_api_docs.py")
            return 1
        print("docs/API.md is up to date.")
        return 0

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    print(f"Wrote {os.path.relpath(OUTPUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
