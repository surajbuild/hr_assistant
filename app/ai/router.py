"""
app/ai/router.py
----------------
Rule-based Intent Classifier and Controlled HR Data Access Router for AI Chat MVP.

Detects basic intents:
- EMPLOYEE
- ATTENDANCE
- LEAVE
- SALARY
- POLICY
- GENERAL
- UNKNOWN

Fetches verified data directly via existing services:
- app.services.employee_service   (profiles, directory, department headcount)
- app.services.attendance_service (summaries, rankings: overtime / late / absent)
- app.services.leave_service      (applications, balances)
- app.services.salary_service     (payslips, payroll summary)
- app/data/policies.json

Time periods (resolve_period, D-029): "August 2024" is used as given; a month without a year means the
most recent such month that has records; "this month" falls back to the latest month with data when
the current month has none; "last month" is the previous calendar month.

Enforces RBAC and data isolation rules before passing context to the LLM.
No arbitrary SQL is generated or executed by the LLM, and this module runs no queries of its own.
"""

import calendar
import json
import os
import re
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai.guardrails import check_rbac_access
from app.database.models import Employee, User, UserRole
from app.services import attendance_service, employee_service, leave_service, salary_service


# ---------------------------------------------------------------------------
# Supported Intents
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    ATTENDANCE = "ATTENDANCE"
    LEAVE = "LEAVE"
    SALARY = "SALARY"
    POLICY = "POLICY"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"


COMPANY_WIDE_ROLES = (UserRole.ADMIN.value, UserRole.HR.value)


# ---------------------------------------------------------------------------
# Policies Loader
# ---------------------------------------------------------------------------

POLICIES_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "policies.json")


def load_policies() -> dict:
    """Load local company policy data from app/data/policies.json."""
    if not os.path.exists(POLICIES_FILE_PATH):
        return {}
    try:
        with open(POLICIES_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Intent Classifier
# ---------------------------------------------------------------------------

def classify_intent(question: str) -> Intent:
    """
    Deterministic rule-based intent classification for the MVP.
    """
    q_lower = question.lower().strip()

    # 1. Policy cues (highest priority for company rule questions)
    policy_patterns = [
        r"\bpolicy\b",
        r"\bpolicies\b",
        r"\brule\b",
        r"\brules\b",
        r"\bguideline\b",
        r"\bguidelines\b",
        r"\bhandbook\b",
        r"\bworking hour",
        r"\bwork hour",
        r"\boffice hour",
        r"\boffice timing",
        r"\bshift time",
        r"\bgrace period\b",
        r"\blunch break\b",
        r"\bpublic holiday",
        r"\bnational holiday",
        r"\bholiday list\b",
        r"\bannual leave entitlement",
        r"\bentitled to\b",
        r"\bhow many leaves are allowed\b",
    ]
    if any(re.search(pat, q_lower) for pat in policy_patterns):
        return Intent.POLICY

    # 2. Salary cues
    salary_patterns = [
        r"\bsalary\b",
        r"\bsalaries\b",
        r"\bpayslip\b",
        r"\bpay slip\b",
        r"\bpayroll\b",
        r"\bcompensation\b",
        r"\bctc\b",
        r"\bpf deduction",
        r"\bnet pay\b",
        r"\bgross pay\b",
        r"\bnet salary\b",
        r"\bgross salary\b",
        r"\bdeductions\b",
        r"\ballowance\b",
        r"\ballowances\b",
        r"\bwage\b",
        r"\bearnings\b",
        r"\bhow much do i earn\b",
        r"\bhow much does .* earn\b",
    ]
    if any(re.search(pat, q_lower) for pat in salary_patterns):
        return Intent.SALARY

    # 3. Attendance cues (attendance, present days, clock in/out, overtime, late arrival)
    attendance_patterns = [
        r"\battendance\b",
        r"\bpresent\b",
        r"\babsent\b",
        r"\babsences\b",
        r"\bclock in\b",
        r"\bclock-in\b",
        r"\bclock out\b",
        r"\bclock-out\b",
        r"\blate\b",
        r"\blatecomers?\b",
        r"\blate entry\b",
        r"\blate entries\b",
        r"\blate arrival\b",
        r"\blate mark\b",
        r"\blate clock\b",
        r"\bovertime\b",
        r"\bot hours\b",
        r"\bworking minutes\b",
        r"\bhours worked\b",
        r"\bworked hours\b",
        r"\bdays present\b",
        r"\bdays absent\b",
        r"\bhow many days was .* present\b",
        r"\bwas .* present\b",
        r"\bwho worked the highest overtime\b",
    ]
    if any(re.search(pat, q_lower) for pat in attendance_patterns):
        return Intent.ATTENDANCE

    # 4. Leave cues (applications, balances, status, sick/casual leave)
    leave_patterns = [
        r"\bleave\b",
        r"\bleaves\b",
        r"\bsick leave\b",
        r"\bcasual leave\b",
        r"\bearned leave\b",
        r"\btime off\b",
        r"\bpto\b",
        r"\bvacation\b",
        r"\bapplied for leave\b",
        r"\bleave balance\b",
        r"\bleave status\b",
        r"\bleave history\b",
        r"\bmy leaves\b",
    ]
    if any(re.search(pat, q_lower) for pat in leave_patterns):
        return Intent.LEAVE

    # 5. Employee cues (designation, department, manager, profile, directory, headcount)
    employee_patterns = [
        r"\bdesignation\b",
        r"\bdepartment\b",
        r"\bdepartments\b",
        r"\bmanager\b",
        r"\breporting to\b",
        r"\breports to\b",
        r"\bwho is\b",
        r"\bemployee code\b",
        r"\bjoining date\b",
        r"\bjoined\b",
        r"\bprofile\b",
        r"\bteam member\b",
        r"\ball employees?\b",
        r"\blist employees\b",
        r"\bevery employee\b",
        r"\bemployee directory\b",
        r"\bpersonal (information|info|details|data)\b",
        r"\bhow many (employees|people|staff)\b",
        r"\bnumber of (employees|people|staff)\b",
        r"\bheadcount\b",
    ]
    if any(re.search(pat, q_lower) for pat in employee_patterns):
        return Intent.EMPLOYEE

    # 6. General greetings & capabilities
    general_patterns = [
        r"^hi\b",
        r"^hello\b",
        r"^hey\b",
        r"\bwho are you\b",
        r"\bwhat can you do\b",
        r"\bhelp\b",
        r"\bgood morning\b",
        r"\bgood afternoon\b",
        r"\bthank you\b",
        r"\bthanks\b",
    ]
    if any(re.search(pat, q_lower) for pat in general_patterns):
        return Intent.GENERAL

    return Intent.UNKNOWN


# ---------------------------------------------------------------------------
# Entity Extraction Helpers (Name, Month, Year)
# ---------------------------------------------------------------------------

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_SELF_RX = re.compile(r"\b(my|mine|me|i|myself)\b")
_THIS_MONTH_RX = re.compile(r"\b(this|current) month\b")
_LAST_MONTH_RX = re.compile(r"\b(last|previous|past) month\b")

# "another employee's salary", "someone else's leave" — another person, but nobody named
_UNNAMED_OTHER_RX = re.compile(
    r"\b(another|other|different|some other) (employee|employees|person|people|colleague|staff|team ?member)"
    r"|\b(someone|somebody|anyone|anybody) else\b"
    r"|\bcolleagues?'?s?\b|\bco-?workers?'?s?\b|\bpeers?'?s?\b"
)


def extract_month_and_year(question: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract an explicit month (1-12) and year from the question text.

    A missing part is returned as None; resolve_period() decides what a month without a year
    (or "this month") means, based on the data that exists.
    """
    q_lower = question.lower()
    found_month = None
    for name, num in MONTH_NAMES.items():
        if name == "may":
            # "May I see…" is not the month
            pattern = r"\b(in|of|for|during|since|until|from|to)\s+may\b|\bmay\s+20[0-9]{2}\b"
        else:
            pattern = r"\b" + name + r"\b"
        if re.search(pattern, q_lower):
            found_month = num
            break

    found_year = None
    year_match = re.search(r"\b(20[0-9]{2})\b", question)
    if year_match:
        found_year = int(year_match.group(1))

    return found_month, found_year


def _period_label(month: Optional[int], year: Optional[int]) -> str:
    if month and year:
        return f"{calendar.month_name[month]} {year}"
    if year:
        return f"the year {year}"
    return "all recorded dates"


def _period_bounds(month: Optional[int], year: Optional[int]) -> Tuple[Optional[date], Optional[date]]:
    if month and year:
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if year:
        return date(year, 1, 1), date(year, 12, 31)
    return None, None


def resolve_period(
    db: Session,
    question: str,
    source: str = "attendance",
    today: Optional[date] = None,
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Resolve the period a question refers to (D-029).

    Returns (month, year, note). `note` is a sentence for the LLM context when an assumption was
    made, so the answer can say which period it describes. `source` selects which data defines
    "has records": "attendance" (attendance table) or "salary" (payroll rows).
    """
    today = today or date.today()
    current = (today.year, today.month)
    month, year = extract_month_and_year(question)
    if month and year:
        return month, year, None

    q_lower = question.lower()
    periods = (
        salary_service.get_payroll_periods(db) if source == "salary" else attendance_service.get_months_with_data(db)
    )
    past_periods = [p for p in periods if p <= current]

    if month:
        years = [y for y, m in past_periods if m == month]
        year = max(years) if years else (today.year if month <= today.month else today.year - 1)
        note = f"Note: no year was given, so the most recent {calendar.month_name[month]} ({year}) is used."
        return month, year, note

    if year:
        return None, year, None

    if _THIS_MONTH_RX.search(q_lower):
        if current in periods or not past_periods:
            return today.month, today.year, None
        latest_year, latest_month = max(past_periods)
        note = (
            f"Note: there are no records yet for {_period_label(today.month, today.year)}; "
            f"the figures are for {_period_label(latest_month, latest_year)}, the most recent month with data."
        )
        return latest_month, latest_year, note

    if _LAST_MONTH_RX.search(q_lower):
        if today.month == 1:
            return 12, today.year - 1, None
        return today.month - 1, today.year, None

    return None, None, None


def refers_to_unnamed_other(question: str) -> bool:
    """True for "another employee's salary"-style questions that point at someone without naming them."""
    return bool(_UNNAMED_OTHER_RX.search(question.lower()))


def find_target_employee(db: Session, question: str, current_user: User) -> Tuple[Optional[Employee], bool]:
    """
    Determine the target employee from the query.

    Returns:
        (target_employee, is_explicitly_other_employee)
        (None, True) means "someone other than the caller who is not in the database / not named".
    """
    q_lower = question.lower()

    # Check for self-referential terms
    is_self = bool(_SELF_RX.search(q_lower))

    # Search for known employees by code or name
    explicit_match = None
    for emp in employee_service.get_all_employees(db):
        # Check employee code (e.g. EMP004)
        if emp.employee_code.lower() in q_lower:
            explicit_match = emp
            break
        # Check first name or full name (e.g. "Aman", "Aman Gupta", "Rahul", "Neha")
        first_name = emp.name.split()[0].lower()
        if re.search(r"\b" + re.escape(first_name) + r"\b", q_lower) or emp.name.lower() in q_lower:
            explicit_match = emp
            break

    if explicit_match:
        is_other = explicit_match.id != current_user.employee_id
        return explicit_match, is_other

    # "another employee", "a colleague" — someone else, but nobody named
    if refers_to_unnamed_other(question):
        return None, True

    # An employee code that matched nobody (e.g. "EMP999")
    if re.search(r"\bemp\d+\b", q_lower):
        return None, True

    if is_self:
        return current_user.employee, False

    # Check if question refers to a third person that does not exist in company DB
    # e.g., "of John Unknown", "was Bob present", "for Alice"
    stopwords = {
        "the", "a", "an", "my", "our", "all", "each", "this", "that", "company", "office", "any", "your", "latest",
        "standard", "designation", "department", "salary", "attendance", "leave", "overtime", "late", "most",
        "last", "previous", "current", "next", "today", "yesterday", "week", "month", "year", "me", "us",
        "everyone", "everybody", "employees", "employee", "present", "absent",
    } | set(MONTH_NAMES)
    for m in re.finditer(r"\b(?:of|for|about|who is|was|regarding|does)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", question, re.IGNORECASE):
        candidate = m.group(1).strip().lower()
        candidate_words = set(candidate.split())
        if not candidate_words.intersection(stopwords):
            return None, True

    # Fallback to current user if asking generally about records without naming someone
    return current_user.employee, False


def _missing_target_response(
    current_user: User,
    intent: Intent,
    question: str,
    data_source: str,
) -> Tuple[str, str, Optional[str]]:
    """
    Context when find_target_employee() found nobody. An unnamed "another employee" is refused for
    roles that may not see other people's data of this kind; otherwise the user is asked to name them.
    """
    if not refers_to_unnamed_other(question):
        return "No employee record found for the requested name.", data_source, None

    company_wide = current_user.role in COMPANY_WIDE_ROLES
    if (intent == Intent.SALARY and not company_wide) or (
        intent in (Intent.ATTENDANCE, Intent.LEAVE) and current_user.role == UserRole.EMPLOYEE.value
    ):
        # target -1 never matches the caller or a subordinate, so the standard denial is returned
        _, denial = check_rbac_access(current_user, intent.value, target_employee_id=-1)
        return denial, data_source, denial
    return (
        "No specific employee was named in the question. Ask the user which employee they mean "
        "(name or employee code) instead of guessing."
    ), data_source, None


# ---------------------------------------------------------------------------
# Ranking & Directory Helpers
# ---------------------------------------------------------------------------

_RANKING_PATTERNS = {
    "overtime": re.compile(
        r"\b(highest|most|max|maximum|top)\b.{0,20}\bovertime\b|\bovertime\b.{0,15}\bthe most\b"
    ),
    "late": re.compile(
        r"\b(most|highest|max|maximum|top)\b.{0,20}\b(late|lateness|latecomers?)\b"
        r"|\blate\b.{0,15}\b(the )?most\b|\bmost often late\b|\blatecomers?\b"
    ),
    "absent": re.compile(
        r"\b(most|highest|max|maximum|top)\b.{0,20}\b(absent|absences|absenteeism)\b"
        r"|\babsent\b.{0,15}\b(the )?most\b"
    ),
}

_RANKING_LABELS = {"overtime": "overtime", "late": "late arrivals", "absent": "absences"}
_RANKING_DENIAL_NAMES = {"overtime": "overtime", "late": "late-arrival", "absent": "absence"}


def detect_ranking_metric(question: str) -> Optional[str]:
    """'overtime' | 'late' | 'absent' for "who worked the most overtime / was late the most / was absent the most"."""
    q_lower = question.lower()
    for metric, rx in _RANKING_PATTERNS.items():
        if rx.search(q_lower):
            return metric
    return None


def _format_minutes(minutes: int) -> str:
    return f"{minutes} minutes ({minutes // 60} hours {minutes % 60} minutes)"


def _days(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def _ranking_context(
    db: Session,
    current_user: User,
    metric: str,
    question: str,
) -> Tuple[str, str, Optional[str]]:
    """Company-wide ranking (HR/Admin only, unchanged from the original overtime rule)."""
    label = _RANKING_LABELS[metric]
    if current_user.role not in COMPANY_WIDE_ROLES:
        denial = (
            f"Access denied: Company-wide {_RANKING_DENIAL_NAMES[metric]} rankings are restricted to HR and Administrators."
        )
        return denial, "attendance_database", denial

    month, year, note = resolve_period(db, question)
    start_d, end_d = _period_bounds(month, year)
    period = _period_label(month, year)
    ranked = attendance_service.rank_employees(db, metric, start_date=start_d, end_date=end_d, limit=5)
    if not ranked:
        context = f"No {label} records found for {period}."
        return (f"{context}\n{note}" if note else context), "attendance_database", None

    lines = [f"Employees ranked by {label} for {period} (calculated by the HR system; equal values share a rank):"]
    for item in ranked:
        rank = 1 + sum(1 for other in ranked if other["value"] > item["value"])
        who = f"{item['employee_name']} ({item['employee_code']}, {item['department']})"
        if metric == "overtime":
            detail = f"total overtime {_format_minutes(item['overtime_minutes'])}"
        elif metric == "late":
            detail = f"{_days(item['late_days'])} late ({item['late_minutes']} late minutes in total)"
        else:
            detail = f"{_days(item['absent_days'])} absent"
        lines.append(f"{rank}. {who}: {detail}")
    if note:
        lines.append(note)
    return "\n".join(lines), "attendance_database", None


_HEADCOUNT_RX = re.compile(
    r"\bhow many (employees|people|staff)\b|\bnumber of (employees|people|staff)\b|\bheadcount\b"
    r"|\bdepartments\b|\bdepartment (size|strength|stats|statistics)\b"
)
_DIRECTORY_RX = re.compile(
    r"\ball employees?\b|\blist (all )?employees\b|\bemployee directory\b|\bevery employee\b|\ball staff\b"
    r"|\beveryone'?s?\b|\beverybody'?s?\b"
)


def _headcount_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """Department headcount — same roles and scope as GET /departments (manager → own team)."""
    if current_user.role == UserRole.EMPLOYEE.value:
        denial = "Access denied: Headcount and department statistics are restricted to HR, Administrators and managers."
        return denial, "employee_database", denial

    scope_ids = employee_service.get_scope_employee_ids(db, current_user)
    departments = employee_service.list_departments(db, scope_ids=scope_ids)
    q_lower = question.lower()
    asked = [d for d in departments if d["name"].lower() in q_lower]
    scope_text = "company-wide" if scope_ids is None else "limited to you and your direct reports"

    lines = [f"Department headcount from the HR system ({scope_text}):"]
    for d in asked or departments:
        managers = ", ".join(d["managers"]) or "none"
        lines.append(
            f"- {d['name']}: {d['employee_count']} employees ({d['active_count']} active) | managers: {managers}"
        )
    if not asked:
        total = sum(d["employee_count"] for d in departments)
        active = sum(d["active_count"] for d in departments)
        lines.append(f"Total: {total} employees ({active} active) in {len(departments)} departments.")
    return "\n".join(lines), "employee_database", None


# ---------------------------------------------------------------------------
# Controlled Data Retrieval Layer
# ---------------------------------------------------------------------------

def retrieve_policy_context(
    db: Session,
    question: str,
) -> Optional[Tuple[str, str, Optional[int], List[Dict[str, Any]]]]:
    """
    RAG retrieval for POLICY questions over uploaded HR documents.

    Returns:
        (context_string, primary_source_name, primary_page, sources) when relevant
        chunks are found, otherwise None (caller falls back to policies.json).
    """
    from app.rag.retriever import search  # local import keeps router importable without RAG tables

    try:
        hits = search(db, question)
    except Exception:
        return None
    if not hits:
        return None

    blocks = []
    for i, hit in enumerate(hits, start=1):
        page_str = f", page {hit['page']}" if hit["page"] else ""
        blocks.append(f"[Source {i}: {hit['document_name']} ({hit['file_name']}{page_str})]\n{hit['content']}")
    context = (
        "The following excerpts were retrieved from the company's uploaded HR documents. "
        "Answer only from them and mention the document name you used.\n\n" + "\n\n".join(blocks)
    )
    sources = [
        {
            "document": hit["document_name"],
            "file_name": hit["file_name"],
            "page": hit["page"],
            "score": hit["score"],
        }
        for hit in hits
    ]
    return context, hits[0]["file_name"], hits[0]["page"], sources


_COMPANY_SALARY_RX = re.compile(
    r"\btotal (salary|salaries|payroll|net pay)\b|\bcompany(-wide)? (salary|salaries|payroll)\b"
    r"|\bpayroll (summary|total|cost)\b|\ball (the )?(employees'? )?salar(y|ies)\b"
    r"|\bsalar(y|ies) of (all|every)|\bevery(one|body)'?s? salar|\ball employees'? salar"
)


def retrieve_hr_context(
    db: Session,
    current_user: User,
    intent: Intent,
    question: str,
) -> Tuple[str, str, Optional[str]]:
    """
    Retrieve structured, factual HR data from existing services or policies.json.

    Returns:
        (context_string, data_source, error_or_denial_message)
    """
    # -----------------------------------------------------------------------
    # 1. POLICY INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.POLICY:
        policies_data = load_policies()
        policies_dict = policies_data.get("policies", {})
        q_lower = question.lower()

        # Match relevant policy topic
        matched_section = None
        if "leave" in q_lower:
            matched_section = policies_dict.get("leave_policy")
        elif "hour" in q_lower or "schedule" in q_lower or "shift" in q_lower:
            matched_section = policies_dict.get("working_hours")
        elif "overtime" in q_lower:
            matched_section = policies_dict.get("overtime_policy")
        elif "attendance" in q_lower or "late" in q_lower or "grace" in q_lower:
            matched_section = policies_dict.get("attendance_rules")
        elif "holiday" in q_lower:
            matched_section = policies_dict.get("holiday_rules")

        if matched_section:
            context = json.dumps(matched_section, indent=2)
        else:
            context = json.dumps(policies_dict, indent=2)

        return context, "policies.json", None

    # -----------------------------------------------------------------------
    # 2. SALARY INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.SALARY:
        month, year, note = resolve_period(db, question, source="salary")

        # Company-wide payroll inquiry ("total payroll", "show all salaries", "payroll for 2024" with nobody
        # named) → summary only, never a per-person salary table (AGENTS.md §3.6)
        q_lower = question.lower()
        target_emp, is_other = find_target_employee(db, question, current_user)
        is_company_query = bool(_COMPANY_SALARY_RX.search(q_lower)) or (
            bool(re.search(r"\bpayroll\b", q_lower)) and target_emp is not None and not is_other
            and not _SELF_RX.search(q_lower)
        )
        if is_company_query:
            if current_user.role not in COMPANY_WIDE_ROLES:
                denial = "Access denied: Company-wide salary summaries are restricted to HR and Administrators."
                return denial, "salary_database", denial

            if month is None and year is None:
                latest = salary_service.get_latest_payroll_period(db)
                if latest:
                    month, year = latest
                    note = "Note: no period was given, so the latest payroll month is used."
            summary = salary_service.get_salary_summary(db, month=month, year=year)
            period = _period_label(month, year)
            if not summary["record_count"]:
                context = f"No salary records found for {period}."
                return (f"{context}\n{note}" if note else context), "salary_database", None
            context = (
                f"Company Payroll Summary for {period}:\n"
                f"- Salary Records: {summary['record_count']} ({summary['employee_count']} employees)\n"
                f"- Total Gross Salary: ₹{summary['total_gross_salary']:,.2f}\n"
                f"- Total PF Deductions: ₹{summary['total_pf']:,.2f}\n"
                f"- Total Other Deductions: ₹{summary['total_deductions']:,.2f}\n"
                f"- Total Overtime Paid: ₹{summary['total_overtime_amount']:,.2f}\n"
                f"- Total Net Salary: ₹{summary['total_net_salary']:,.2f}"
            )
            return (f"{context}\n{note}" if note else context), "salary_database", None

        # Individual employee salary inquiry
        if not target_emp:
            return _missing_target_response(current_user, intent, question, "salary_database")

        # RBAC Check: Employees/Managers cannot view other employees' salary
        allowed, denial_reason = check_rbac_access(current_user, "SALARY", target_employee_id=target_emp.id)
        if not allowed:
            return denial_reason, "salary_database", denial_reason

        salaries = salary_service.get_salary_for_employee(db, employee_id=target_emp.id)
        if month:
            salaries = [s for s in salaries if s.month == month]
        if year:
            salaries = [s for s in salaries if s.year == year]
        if not salaries:
            period_str = f" for {_period_label(month, year)}" if month or year else ""
            return f"No salary records found for {target_emp.name}{period_str}.", "salary_database", None

        lines = [f"Salary records for {target_emp.name} ({target_emp.employee_code}):"]
        for s in salaries:
            lines.append(
                f"- Period: {calendar.month_name[s.month]} {s.year} | "
                f"Gross Salary: ₹{s.gross_salary:,.2f} | PF: ₹{s.pf:,.2f} | "
                f"Deductions: ₹{s.deductions:,.2f} | Overtime Amount: ₹{s.overtime_amount:,.2f} | "
                f"Net Salary: ₹{s.net_salary:,.2f}"
            )
        if note:
            lines.append(note)
        return "\n".join(lines), "salary_database", None

    # -----------------------------------------------------------------------
    # 3. ATTENDANCE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.ATTENDANCE:
        # Company-wide rankings: "Who worked the most overtime?", "Who was late the most?"
        metric = detect_ranking_metric(question)
        if metric:
            return _ranking_context(db, current_user, metric, question)

        # Individual attendance inquiry
        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return _missing_target_response(current_user, intent, question, "attendance_database")

        # RBAC Check: Employees cannot view other employees' attendance
        allowed, denial_reason = check_rbac_access(current_user, "ATTENDANCE", target_employee_id=target_emp.id)
        if not allowed:
            return denial_reason, "attendance_database", denial_reason

        month, year, note = resolve_period(db, question)
        start_d, end_d = _period_bounds(month, year)
        period_str = _period_label(month, year)
        summary = attendance_service.get_attendance_summary(
            db, employee_id=target_emp.id, start_date=start_d, end_date=end_d
        )

        if summary["total_days"] == 0:
            context = (
                f"No attendance records found for {target_emp.name} ({target_emp.employee_code}) for {period_str}. "
                f"Attendance data is not available for the requested period."
            )
            return (f"{context}\n{note}" if note else context), "attendance_database", None

        context = (
            f"Attendance summary for {target_emp.name} ({target_emp.employee_code}) for {period_str}:\n"
            f"- Total Days Recorded: {summary['total_days']}\n"
            f"- Present Days: {summary['present_days']}\n"
            f"- Absent Days: {summary['absent_days']}\n"
            f"- Half Days: {summary['half_day_days']}\n"
            f"- Leave Days: {summary['leave_days']}\n"
            f"- Late Clock-Ins: {summary['late_days']} (late entries after 09:15 AM)\n"
            f"- Overtime Days: {summary['overtime_days']}\n"
            f"- Total Overtime: {_format_minutes(summary['total_overtime_minutes'])}\n"
            f"- Total Working Minutes: {summary['total_working_minutes']}"
        )
        if note:
            context += f"\n{note}"
        return context, "attendance_database", None

    # -----------------------------------------------------------------------
    # 4. LEAVE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.LEAVE:
        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return _missing_target_response(current_user, intent, question, "leave_database")

        # RBAC Check: Employees cannot view other employees' leave applications
        allowed, denial_reason = check_rbac_access(current_user, "LEAVE", target_employee_id=target_emp.id)
        if not allowed:
            return denial_reason, "leave_database", denial_reason

        # Balance is calculated in Python (leave_service) for the year asked about, else the current year
        year_match = re.search(r"\b(20[0-9]{2})\b", question)
        balance_year = int(year_match.group(1)) if year_match else date.today().year
        balance = leave_service.get_leave_balance(db, target_emp.id, balance_year)

        lines = [
            f"Leave balance for {target_emp.name} ({target_emp.employee_code}) for calendar year {balance_year} "
            f"(working days; calculated by the HR system):"
        ]
        for b in balance:
            lines.append(
                f"- {b['leave_type'].title()} leave: entitled {b['entitled']}, used {b['used']}, "
                f"pending approval {b['pending']}, remaining {b['remaining']}"
            )

        leaves = leave_service.get_leaves_for_employee(db, employee_id=target_emp.id)
        if not leaves:
            lines.append(f"\nNo leave applications found for {target_emp.name}.")
            return "\n".join(lines), "leave_database", None

        lines.append(f"\nLeave applications for {target_emp.name}:")
        for lv in sorted(leaves, key=lambda l: l.from_date, reverse=True):
            days = leave_service.count_leave_days(lv.from_date, lv.to_date)
            lines.append(
                f"- Type: {lv.leave_type.upper()} | Dates: {lv.from_date} to {lv.to_date} | "
                f"Working days: {days} | Status: {lv.status.upper()} | Reason: {lv.reason or 'None'}"
            )
        return "\n".join(lines), "leave_database", None

    # -----------------------------------------------------------------------
    # 5. EMPLOYEE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.EMPLOYEE:
        q_lower = question.lower()
        if _HEADCOUNT_RX.search(q_lower):
            return _headcount_context(db, current_user, question)

        if _DIRECTORY_RX.search(q_lower):
            if current_user.role not in COMPANY_WIDE_ROLES:
                denial = (
                    "Access denied: The employee directory and other employees' personal information "
                    "are restricted to HR and Administrators."
                )
                return denial, "employee_database", denial

            all_emps = employee_service.get_all_employees(db)
            lines = ["Company Employees Directory:"]
            for e in all_emps:
                lines.append(f"- {e.employee_code}: {e.name} | Dept: {e.department} | Role: {e.designation}")
            return "\n".join(lines), "employee_database", None

        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            context, source, denial = _missing_target_response(current_user, intent, question, "employee_database")
            if context.startswith("No employee record found"):
                context = "No employee record found matching the inquiry."
            return context, source, denial

        manager_name = target_emp.manager.name if target_emp.manager else "None (Executive)"
        context = (
            f"Employee Profile:\n"
            f"- Code: {target_emp.employee_code}\n"
            f"- Name: {target_emp.name}\n"
            f"- Department: {target_emp.department}\n"
            f"- Designation: {target_emp.designation}\n"
            f"- Joining Date: {target_emp.joining_date}\n"
            f"- Status: {target_emp.status}\n"
            f"- Reporting Manager: {manager_name}"
        )
        return context, "employee_database", None

    # -----------------------------------------------------------------------
    # 6. GENERAL INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.GENERAL:
        context = (
            "You are the AI HR Assistant for AI HR Assistant Tech Corp. "
            "You help employees and HR personnel with questions regarding company policies, "
            "attendance tracking, leave records, salary slips, and employee profiles."
        )
        return context, "general", None

    # -----------------------------------------------------------------------
    # 7. UNKNOWN INTENT
    # -----------------------------------------------------------------------
    context = (
        "The inquiry is outside the scope of company HR, attendance, leaves, salary, or company policy. "
        "Politely state that you can only assist with company HR-related questions."
    )
    return context, "general", None
