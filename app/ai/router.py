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
- app.services.employee_service   (profiles incl. employee-ID lookup, directory, department headcount)
- app.services.attendance_service (summaries, hours worked, attendance %, rankings, thresholds, department overtime)
- app.services.leave_service      (applications, balances, leave taken in a period, who is on leave)
- app.services.salary_service     (payslips incl. PF / overtime amount, payroll summary)
- app/data/policies.json

Time periods (resolve_period, D-029): "August 2024" is used as given; a month without a year means the
most recent such month that has records; "this month" falls back to the latest month with data when
the current month has none; "last month" is the previous calendar month. resolve_date_range adds
"today", "yesterday", "this week" and "last week".

Targets (find_target_employee, D-043): a question is answered for a named employee, for the caller when
they say "my"/"I", or for a group through a group tool. The caller's own record is never substituted for
another person, an employee ID, a group, a department or the company; when the target is unclear the
context asks for clarification (CLARIFICATION_PREFIX) and no records are loaded.

Enforces RBAC and data isolation rules before passing context to the LLM.
No arbitrary SQL is generated or executed by the LLM, and this module runs no queries of its own.
"""

import calendar
import json
import os
import re
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.ai.guardrails import check_rbac_access
from app.database.models import Employee, User, UserRole
from app.services import attendance_service, employee_service, holiday_service, leave_service, salary_service


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
        r"\bholiday calendar\b",
        r"\bupcoming holidays?\b",
        r"\b(list|which|what) (are )?(the )?(company )?holidays\b",
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
        r"\bpf\b",
        r"\bprovident fund\b",
        r"\b(overtime|ot) (amount|pay|payment|paid)\b",
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
        r"\bhours\b.{0,30}\bwork(ed)?\b",
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
_THIS_WEEK_RX = re.compile(r"\b(this|current) week\b")
_LAST_WEEK_RX = re.compile(r"\b(last|previous|past) week\b")
_TODAY_RX = re.compile(r"\btoday\b")
_YESTERDAY_RX = re.compile(r"\byesterday\b")

# Context that asks the user to name a person / rephrase instead of answering (chat confidence
# "clarification_needed"). No HR figures are ever put in such a context.
CLARIFICATION_PREFIX = "Clarification needed:"

# A question about several people (a team, a department, the company) — never answered with the caller's
# own record (D-043). Department names are matched separately (they come from the data).
_GROUP_RX = re.compile(
    r"\bteams?\b|\bmembers\b|\b(direct )?reports\b|\bsubordinates\b|\bemployees\b|\bstaff\b|\bpeople\b"
    r"|\beveryone\b|\beverybody\b|\bcompany(-wide)?\b|\borgani[sz]ation\b|\bdepartments\b"
    r"|\bdepartment-?wise\b|\b(by|per|each|every) department\b"
)
# Words that make a question without a named person an aggregate or "who" question — then it is not
# read as "about the caller", even for the employee role.
_AGGREGATE_RX = re.compile(
    r"\b(total|average|avg|overall|highest|lowest|maximum|minimum|most|least|who|whom|whose|which|anyone|anybody)\b"
)
_TEAM_RX = re.compile(r"\b(my|our) (own )?team\b|\bmembers of my\b|\bmy (direct )?reports\b|\bmy subordinates\b")
# "employee 1025", "employee ID 4", "emp #12" — the number is the employee code's number (EMP004 = 4)
_EMPLOYEE_ID_RX = re.compile(r"\b(?:employee|emp)\s*(?:id|code|no\.?|number)?\s*#?\s*(\d{1,6})\b")

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
    "has records": "attendance" (attendance table), "salary" (payroll rows) or "leave" (none — the calendar).
    """
    today = today or date.today()
    current = (today.year, today.month)
    month, year = extract_month_and_year(question)
    if month and year:
        return month, year, None

    q_lower = question.lower()
    if source == "salary":
        periods = salary_service.get_payroll_periods(db)
    elif source == "leave":
        periods = []  # leave questions use the calendar ("this month" = the current month)
    else:
        periods = attendance_service.get_months_with_data(db)
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


def resolve_date_range(
    db: Session,
    question: str,
    source: str = "attendance",
    today: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date], str, Optional[str]]:
    """
    (start, end, label, note) for a question: "today" / "yesterday" / "this week" (Monday → today) /
    "last week" (the previous Monday → Sunday) first, otherwise the month/year period of resolve_period().
    (None, None, "all recorded dates", None) when the question names no period.
    """
    today = today or date.today()
    q_lower = question.lower()
    monday = today - timedelta(days=today.weekday())
    if _LAST_WEEK_RX.search(q_lower):
        start, end = monday - timedelta(days=7), monday - timedelta(days=1)
        return start, end, f"last week ({start} to {end})", None
    if _THIS_WEEK_RX.search(q_lower):
        return monday, today, f"this week ({monday} to {today})", None
    if _YESTERDAY_RX.search(q_lower):
        day = today - timedelta(days=1)
        return day, day, f"yesterday ({day})", None
    if _TODAY_RX.search(q_lower):
        return today, today, f"today ({today})", None
    month, year, note = resolve_period(db, question, source=source, today=today)
    start, end = _period_bounds(month, year)
    return start, end, _period_label(month, year), note


def refers_to_unnamed_other(question: str) -> bool:
    """True for "another employee's salary"-style questions that point at someone without naming them."""
    return bool(_UNNAMED_OTHER_RX.search(question.lower()))


def named_departments(db: Session, question: str) -> List[str]:
    """Department names (from the employee data, D-005) written in the question."""
    q_lower = question.lower()
    return [d["name"] for d in employee_service.list_departments(db) if d["name"].lower() in q_lower]


def refers_to_group(db: Session, question: str) -> bool:
    """True when the question is about a team, a department, several employees or the whole company."""
    return bool(_GROUP_RX.search(question.lower())) or bool(named_departments(db, question))


def find_named_employee(db: Session, question: str) -> Tuple[Optional[Employee], bool]:
    """
    The employee a question names by code ("EMP004"), employee ID ("employee 4") or name ("Aman", "Aman Gupta").

    Returns (employee, named): (None, True) when a code / ID was given that matches nobody.
    """
    q_lower = question.lower()
    employees = employee_service.get_all_employees(db)
    for emp in employees:
        if emp.employee_code.lower() in q_lower:
            return emp, True

    id_match = _EMPLOYEE_ID_RX.search(q_lower)
    if id_match:
        number = int(id_match.group(1))
        for emp in employees:
            digits = re.sub(r"\D", "", emp.employee_code)
            if digits and int(digits) == number:
                return emp, True
        return None, True

    for emp in employees:
        first_name = emp.name.split()[0].lower()
        if re.search(r"\b" + re.escape(first_name) + r"\b", q_lower) or emp.name.lower() in q_lower:
            return emp, True
    return None, False


# Third person who is not in the database, e.g. "of John Unknown", "was Bruce Wayne present" (names are capitalised)
_UNKNOWN_PERSON_RX = re.compile(
    r"\b(?i:of|for|about|who is|was|regarding|does)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)
_UNKNOWN_PERSON_STOPWORDS = {
    "the", "a", "an", "my", "our", "all", "each", "this", "that", "company", "office", "any", "your", "latest",
    "standard", "designation", "department", "salary", "attendance", "leave", "overtime", "late", "most",
    "last", "previous", "current", "next", "today", "yesterday", "week", "month", "year", "me", "us",
    "everyone", "everybody", "employees", "employee", "present", "absent", "i", "it", "there",
} | set(MONTH_NAMES)


def find_target_employee(
    db: Session, question: str, current_user: User
) -> Tuple[Optional[Employee], bool, Optional[str]]:
    """
    The one employee a question is about.

    Returns (target_employee, is_other, note):
      - a named employee (code, employee ID or name)        → (employee, employee is not the caller, None)
      - a code / ID / name that matches nobody, or an unnamed
        "another employee" / "a colleague"                  → (None, True, None)
      - a group, team, department or company question        → (None, False, None)
      - "my", "I", "me"                                      → (caller, False, None)
      - nobody named and no self reference: an *employee* can only see their own records, so a plain
        question ("How much PF was deducted?") is about them — returned with a note the answer must state.
        For other roles (and for aggregate / "who" wording) the target is unknown → (None, False, None).
    The caller's own record is never used for a question about someone else or about a group (D-043).
    """
    named, asked = find_named_employee(db, question)
    if named:
        return named, named.id != current_user.employee_id, None
    if asked or refers_to_unnamed_other(question):
        return None, True, None
    if refers_to_group(db, question):
        return None, False, None

    q_lower = question.lower()
    if _SELF_RX.search(q_lower):
        return current_user.employee, False, None

    for m in _UNKNOWN_PERSON_RX.finditer(question):
        if not set(m.group(1).lower().split()) & _UNKNOWN_PERSON_STOPWORDS:
            return None, True, None

    own = current_user.employee
    if current_user.role == UserRole.EMPLOYEE.value and own and not _AGGREGATE_RX.search(q_lower):
        note = (
            f"Note: no person was named, so these are the records of the user themself, {own.name} "
            f"({own.employee_code}) — the only employee whose records this user can see. Say so in the answer."
        )
        return own, False, note
    return None, False, None


_GROUP_HELP = (
    "Group questions the HR assistant can answer: rankings (\"Who worked the most overtime this month?\"), "
    "thresholds (\"Show employees with more than 5 late entries\", \"How many employees worked more than "
    "10 hours overtime?\"), \"Which members of my team worked overtime last week?\", department-wise overtime, "
    "department headcount, who is on leave today, and (HR/Admin) the company payroll summary."
)


def _missing_target_response(
    db: Session,
    current_user: User,
    intent: Intent,
    question: str,
    data_source: str,
    is_other: bool,
) -> Tuple[str, str, Optional[str]]:
    """
    Context when find_target_employee() found nobody. No record is loaded for anyone:
      - an unnamed "another employee" or a group question is refused for roles that may not see other
        people's data of this kind (D-030); otherwise the user is asked to name the person / rephrase;
      - a name / code / employee ID that matches nobody → "No employee record found";
      - nobody named at all → the user is asked whose records they mean (never the caller's by default).
    """
    unnamed_other = refers_to_unnamed_other(question)
    group = not is_other and refers_to_group(db, question)
    if is_other and not unnamed_other:
        return "No employee record found for the requested name or employee ID.", data_source, None

    if unnamed_other or group:
        company_wide = current_user.role in COMPANY_WIDE_ROLES
        if (intent == Intent.SALARY and not company_wide) or (
            intent in (Intent.ATTENDANCE, Intent.LEAVE, Intent.EMPLOYEE)
            and current_user.role == UserRole.EMPLOYEE.value
        ):
            # target -1 never matches the caller or a subordinate, so the standard denial is returned
            _, denial = check_rbac_access(current_user, intent.value, target_employee_id=-1)
            return denial, data_source, denial

    if unnamed_other:
        return (
            f"{CLARIFICATION_PREFIX} No specific employee was named in the question. Ask the user which employee "
            "they mean (name or employee code) instead of guessing. Do not give any figures."
        ), data_source, None
    if group:
        return (
            f"{CLARIFICATION_PREFIX} The question is about a group of employees (a team, a department or the "
            "whole company) in a form the HR system cannot answer, so no records were retrieved. Tell the user "
            f"this without giving any figures and suggest a supported question. {_GROUP_HELP}"
        ), data_source, None
    return (
        f"{CLARIFICATION_PREFIX} The question does not say whose records it is about, so no records were "
        "retrieved. Ask the user to name the employee (name or employee code), to say \"my\" for their own "
        "records, or to ask a company-level question. Do not give any figures."
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


def _group_scope(db: Session, current_user: User, question: str) -> Tuple[Optional[Set[int]], str]:
    """
    Employee ids a group attendance question covers, and how to describe that scope.
    "my team" → the caller + direct reports (any role); otherwise HR/Admin → company-wide (None),
    manager → themself + direct reports (D-032, same scope as GET /attendance/records).
    """
    team_text = "limited to you and your direct reports"
    if _TEAM_RX.search(question.lower()) and current_user.employee:
        own = current_user.employee
        return {own.id} | {sub.id for sub in own.subordinates}, team_text
    scope_ids = employee_service.get_scope_employee_ids(db, current_user)
    return scope_ids, ("company-wide" if scope_ids is None else team_text)


def _ranking_context(
    db: Session,
    current_user: User,
    metric: str,
    question: str,
) -> Tuple[str, str, Optional[str]]:
    """
    Attendance ranking. HR/Admin → company-wide; manager → themself + direct reports (KI-029, D-032,
    same scope as GET /attendance/records); employee → refused.
    """
    label = _RANKING_LABELS[metric]
    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        denial = (
            f"Access denied: {_RANKING_DENIAL_NAMES[metric].capitalize()} rankings are restricted to HR, "
            "Administrators and managers (for their own team)."
        )
        return denial, "attendance_database", denial

    scope_ids, scope_text = _group_scope(db, current_user, question)
    start_d, end_d, period, note = resolve_date_range(db, question)
    ranked = attendance_service.rank_employees(
        db, metric, start_date=start_d, end_date=end_d, scope_ids=scope_ids, limit=5
    )
    if not ranked:
        context = f"No {label} records found for {period} ({scope_text})."
        return (f"{context}\n{note}" if note else context), "attendance_database", None

    lines = [
        f"Employees ranked by {label} for {period}, {scope_text} "
        "(calculated by the HR system; equal values share a rank):"
    ]
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


_METRIC_RX = {
    "overtime": re.compile(r"\bovertime\b|\bot hours\b|\bextra hours\b"),
    "late": re.compile(r"\blate\b|\blatecomers?\b|\blateness\b"),
    "absent": re.compile(r"\babsent\b|\babsences?\b"),
}
# "more than 5", "over 10 hours", "at least 3 times" — strict unless "at least" / "or more" / ">="
_THRESHOLD_RX = re.compile(
    r"\b(more than|over|above|greater than|exceeding|at least|minimum of)\s+(\d+(?:\.\d+)?)\s*"
    r"(hours?|hrs?|minutes?|mins?)?"
    r"|(>=|>)\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)?"
    r"|\b(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?|times|days|late entries)?\s+or more\b"
)
_WHO_RX = re.compile(r"\b(who|whom|which|how many)\b")
_DEPARTMENT_WISE_RX = re.compile(
    r"\bdepartment-?\s?wise\b|\b(by|per|each|every|across) departments?\b|\bdepartment (breakdown|split|totals?)\b"
)


def _attendance_metric(question: str) -> Optional[str]:
    q_lower = question.lower()
    for metric, rx in _METRIC_RX.items():
        if rx.search(q_lower):
            return metric
    return None


def _parse_threshold(question: str) -> Optional[Tuple[float, bool, Optional[str]]]:
    """(value, inclusive, unit) for "more than 10 hours", "at least 3 times", "5 or more"; None when absent."""
    m = _THRESHOLD_RX.search(question.lower())
    if not m:
        return None
    if m.group(2):
        return float(m.group(2)), m.group(1) in ("at least", "minimum of"), m.group(3)
    if m.group(5):
        return float(m.group(5)), m.group(4) == ">=", m.group(6)
    return float(m.group(7)), True, m.group(8)


def _number(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)


def _group_denial(kind: str) -> Tuple[str, str, Optional[str]]:
    denial = (
        f"Access denied: {kind} for other employees are restricted to HR, Administrators and managers "
        "(for their own team)."
    )
    return denial, "attendance_database", denial


def _attendance_group_context(
    db: Session,
    current_user: User,
    question: str,
) -> Optional[Tuple[str, str, Optional[str]]]:
    """
    Attendance questions about several employees (no one named), or None when the question is not one:
      - department-wise overtime                                 → attendance_service.get_overtime_by_department
      - "employees with more than 5 late entries", "more than 10 hours overtime",
        "which members of my team worked overtime last week"     → attendance_service.rank_employees(limit=None)
    Same roles and scope as the rankings (D-032): HR/Admin company-wide, managers their team, employees refused.
    """
    q_lower = question.lower()
    metric = _attendance_metric(question)
    if not metric:
        return None
    departments = named_departments(db, question)
    group = refers_to_group(db, question)
    threshold = _parse_threshold(question)
    department_wise = metric == "overtime" and bool(_DEPARTMENT_WISE_RX.search(q_lower))
    who_without_self = bool(_WHO_RX.search(q_lower)) and not _SELF_RX.search(q_lower)
    if not (department_wise or group or who_without_self):
        return None

    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        return _group_denial("Attendance figures")

    scope_ids, scope_text = _group_scope(db, current_user, question)
    start_d, end_d, period, note = resolve_date_range(db, question)

    if department_wise:
        rows = attendance_service.get_overtime_by_department(db, start_date=start_d, end_date=end_d, scope_ids=scope_ids)
        if departments:
            rows = [r for r in rows if r["department"] in departments]
        if not rows:
            context = f"No attendance records found for {period} ({scope_text})."
            return (f"{context}\n{note}" if note else context), "attendance_database", None
        lines = [f"Overtime by department for {period}, {scope_text} (calculated by the HR system):"]
        for r in rows:
            lines.append(
                f"- {r['department']}: total overtime {_format_minutes(r['total_overtime_minutes'])}; "
                f"{r['employees_with_overtime']} of {r['employees_with_records']} employees with attendance "
                "records worked overtime"
            )
        total = sum(r["total_overtime_minutes"] for r in rows)
        lines.append(f"Total across these departments: {_format_minutes(total)}.")
        if note:
            lines.append(note)
        return "\n".join(lines), "attendance_database", None

    items = attendance_service.rank_employees(
        db, metric, start_date=start_d, end_date=end_d, scope_ids=scope_ids, limit=None
    )
    if departments:
        items = [i for i in items if i["department"] in departments]
        scope_text += f", department {', '.join(departments)}"

    if threshold:
        value, inclusive, unit = threshold
        compare = "at least" if inclusive else "more than"
        if metric == "overtime":
            minutes = value if unit and unit.startswith("min") else value * 60
            unit_text = "minutes" if unit and unit.startswith("min") else "hours"
            items = [i for i in items if i["overtime_minutes"] >= minutes] if inclusive else \
                [i for i in items if i["overtime_minutes"] > minutes]
            description = f"{compare} {_number(value)} {unit_text} of overtime"
        else:
            count_key = "late_days" if metric == "late" else "absent_days"
            items = [i for i in items if i[count_key] >= value] if inclusive else \
                [i for i in items if i[count_key] > value]
            description = f"{compare} {_number(value)} " + ("late entries" if metric == "late" else "absences")
    else:
        description = {"overtime": "any overtime", "late": "any late entries", "absent": "any absences"}[metric]

    if not items:
        context = f"No employees had {description} for {period} ({scope_text}). Checked by the HR system."
        return (f"{context}\n{note}" if note else context), "attendance_database", None

    count = len(items)
    lines = [
        f"Employees with {description} for {period}, {scope_text} (calculated by the HR system): "
        f"{count} employee{'s' if count != 1 else ''}."
    ]
    for item in items:
        who = f"{item['employee_name']} ({item['employee_code']}, {item['department']})"
        if metric == "overtime":
            detail = f"total overtime {_format_minutes(item['overtime_minutes'])}"
        elif metric == "late":
            detail = f"{_days(item['late_days'])} late ({item['late_minutes']} late minutes in total)"
        else:
            detail = f"{_days(item['absent_days'])} absent"
        lines.append(f"- {who}: {detail}")
    if note:
        lines.append(note)
    return "\n".join(lines), "attendance_database", None


_ON_LEAVE_RX = re.compile(r"\bon leave\b|\bon (a )?(sick|casual|earned) leave\b")


def _on_leave_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """Who is on approved leave today / yesterday / tomorrow — HR/Admin company-wide, managers their team."""
    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        denial = "Access denied: Leave records of other employees are restricted to HR, Administrators and managers."
        return denial, "leave_database", denial

    q_lower = question.lower()
    today = date.today()
    if "tomorrow" in q_lower:
        on_date, label = today + timedelta(days=1), "tomorrow"
    elif _YESTERDAY_RX.search(q_lower):
        on_date, label = today - timedelta(days=1), "yesterday"
    else:
        on_date, label = today, "today"
    scope_ids, scope_text = _group_scope(db, current_user, question)
    on_leave = leave_service.get_employees_on_leave(db, on_date, scope_ids=scope_ids)
    departments = named_departments(db, question)
    if departments:
        on_leave = [r for r in on_leave if r["department"] in departments]
        scope_text += f", department {', '.join(departments)}"

    if not on_leave:
        return (
            f"No employees are on approved leave {label} ({on_date}, {scope_text}). Checked by the HR system."
        ), "leave_database", None
    lines = [
        f"Employees on approved leave {label} ({on_date}), {scope_text} (from the HR system): "
        f"{len(on_leave)} employee{'s' if len(on_leave) != 1 else ''}."
    ]
    for r in on_leave:
        lines.append(
            f"- {r['employee_name']} ({r['employee_code']}, {r['department']}): {r['leave_type']} leave "
            f"from {r['from_date']} to {r['to_date']}"
        )
    return "\n".join(lines), "leave_database", None


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


def holiday_calendar_context(db: Session, question: str) -> Optional[str]:
    """
    The company holiday calendar (national + HR-declared holidays, D-034) for the year named in a
    holiday question (default: this year), or None when the question is not about holidays.
    Added to POLICY context whether the policy text came from documents or policies.json.
    """
    q_lower = question.lower()
    if "holiday" not in q_lower:
        return None
    year_match = re.search(r"\b(20\d{2})\b", q_lower)
    year = int(year_match.group(1)) if year_match else date.today().year
    lines = [f"Company holiday calendar for {year} (from the HR system):"]
    lines += [f"- {h['date']} ({h['weekday']}): {h['name']} [{h['kind']}]" for h in holiday_service.list_holidays(db, year)]
    return "\n".join(lines)


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
    r"\btotal (salary|salaries|payroll|net pay)\b|\bcompany(-wide)? (salary|salaries|payroll|pf|overtime)\b"
    r"|\bpayroll (summary|total|cost)\b|\ball (the )?(employees'? )?salar(y|ies)\b"
    r"|\bsalar(y|ies) of (all|every)|\bevery(one|body)'?s? salar|\ball employees'? salar"
    r"|\btotal (pf|provident fund|deductions|(overtime|ot) (amount|pay|payment|paid))\b"
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

        calendar_context = holiday_calendar_context(db, question)
        if calendar_context:
            context += "\n\n" + calendar_context

        return context, "policies.json", None

    # -----------------------------------------------------------------------
    # 2. SALARY INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.SALARY:
        month, year, note = resolve_period(db, question, source="salary")

        # Company-wide payroll inquiry ("total payroll", "show all salaries", "total overtime amount",
        # "payroll for 2024" with nobody named) → summary only, never a per-person salary table (AGENTS.md §3.6).
        # Not for one department: there is no department payroll summary, so that is a group question below.
        q_lower = question.lower()
        target_emp, is_other, target_note = find_target_employee(db, question, current_user)
        nobody_named = (target_emp is None or target_note is not None) and not is_other
        is_company_query = not named_departments(db, question) and (
            bool(_COMPANY_SALARY_RX.search(q_lower) and not (target_emp and not target_note))
            or (bool(re.search(r"\bpayroll\b", q_lower)) and nobody_named and not _SELF_RX.search(q_lower))
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
            return _missing_target_response(db, current_user, intent, question, "salary_database", is_other)

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
        if len(salaries) > 1:
            # Sums are calculated here, never by the LLM (PRD §20)
            lines.append(
                f"Totals for the {len(salaries)} periods listed: Gross ₹{sum(s.gross_salary for s in salaries):,.2f} | "
                f"PF ₹{sum(s.pf for s in salaries):,.2f} | Deductions ₹{sum(s.deductions for s in salaries):,.2f} | "
                f"Overtime Amount ₹{sum(s.overtime_amount for s in salaries):,.2f} | "
                f"Net ₹{sum(s.net_salary for s in salaries):,.2f}"
            )
        if note:
            lines.append(note)
        if target_note:
            lines.append(target_note)
        return "\n".join(lines), "salary_database", None

    # -----------------------------------------------------------------------
    # 3. ATTENDANCE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.ATTENDANCE:
        # Rankings: "Who worked the most overtime?", "Who was late the most?" (manager → own team)
        metric = detect_ranking_metric(question)
        if metric:
            return _ranking_context(db, current_user, metric, question)

        # Several employees: thresholds, "who worked overtime", department-wise overtime (nobody named)
        named, asked = find_named_employee(db, question)
        if not named and not asked and not refers_to_unnamed_other(question):
            group_context = _attendance_group_context(db, current_user, question)
            if group_context:
                return group_context

        # Individual attendance inquiry
        target_emp, is_other, target_note = find_target_employee(db, question, current_user)
        if not target_emp:
            return _missing_target_response(db, current_user, intent, question, "attendance_database", is_other)

        # RBAC Check: Employees cannot view other employees' attendance
        allowed, denial_reason = check_rbac_access(current_user, "ATTENDANCE", target_employee_id=target_emp.id)
        if not allowed:
            return denial_reason, "attendance_database", denial_reason

        start_d, end_d, period_str, note = resolve_date_range(db, question)
        if target_note:
            note = f"{note}\n{target_note}" if note else target_note
        summary = attendance_service.get_attendance_summary(
            db, employee_id=target_emp.id, start_date=start_d, end_date=end_d
        )

        if summary["total_days"] == 0:
            context = (
                f"No attendance records found for {target_emp.name} ({target_emp.employee_code}) for {period_str}. "
                f"Attendance data is not available for the requested period."
            )
            return (f"{context}\n{note}" if note else context), "attendance_database", None

        pct = attendance_service.attendance_percentage(summary)
        pct_text = (
            f"{pct['percentage']}% ({_number(pct['attended_days'])} of {pct['working_days']} recorded working days "
            "attended; present days count 1 and half days 0.5; absences and leave count as not attended; "
            "weekends and holidays are excluded)"
            if pct["percentage"] is not None else "not available (no recorded working days)"
        )
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
            f"- Total Working Minutes: {summary['total_working_minutes']}\n"
            f"- Total Hours Worked: {summary['total_working_minutes'] // 60} hours "
            f"{summary['total_working_minutes'] % 60} minutes\n"
            f"- Attendance Percentage: {pct_text}"
        )
        if note:
            context += f"\n{note}"
        return context, "attendance_database", None

    # -----------------------------------------------------------------------
    # 4. LEAVE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.LEAVE:
        # "How many employees are on leave today?", "Who on my team is on leave?" (nobody named)
        q_lower = question.lower()
        named, asked = find_named_employee(db, question)
        if (
            _ON_LEAVE_RX.search(q_lower) and not named and not asked
            and (refers_to_group(db, question) or (_WHO_RX.search(q_lower) and not _SELF_RX.search(q_lower))
                 or re.search(r"\b(anyone|anybody|someone|somebody)\b", q_lower))
        ):
            return _on_leave_context(db, current_user, question)

        target_emp, is_other, target_note = find_target_employee(db, question, current_user)
        if not target_emp:
            return _missing_target_response(db, current_user, intent, question, "leave_database", is_other)

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

        # "How many leaves did I take this month / last week?" — leave days inside that period (by the calendar)
        start_d, end_d, period_str, _ = resolve_date_range(db, question, source="leave")
        if start_d and end_d:
            taken = leave_service.get_leave_days_in_range(db, target_emp.id, start_d, end_d)
            lines.append(
                f"\nLeave taken in {period_str} (working days, calculated by the HR system): "
                f"approved {sum(t['approved'] for t in taken)} in total ("
                + ", ".join(f"{t['leave_type']} {t['approved']}" for t in taken)
                + f"); pending approval {sum(t['pending'] for t in taken)}."
            )
        if target_note:
            lines.append(target_note)

        leaves = leave_service.get_leaves_for_employee(db, employee_id=target_emp.id)
        if not leaves:
            lines.append(f"\nNo leave applications found for {target_emp.name}.")
            return "\n".join(lines), "leave_database", None

        lines.append(f"\nLeave applications for {target_emp.name}:")
        holidays = holiday_service.get_declared_holiday_dates(db)
        for lv in sorted(leaves, key=lambda l: l.from_date, reverse=True):
            days = leave_service.count_leave_days(lv.from_date, lv.to_date, holidays=holidays)
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

        target_emp, is_other, target_note = find_target_employee(db, question, current_user)
        if not target_emp:
            context, source, denial = _missing_target_response(
                db, current_user, intent, question, "employee_database", is_other
            )
            if context.startswith("No employee record found"):
                context = "No employee record found matching the inquiry (name, employee code or employee ID)."
            return context, source, denial

        # Another person's profile: same scope as GET /employees/{id} (D-039) — refused before the LLM
        allowed, denial = check_rbac_access(current_user, intent.value, target_employee_id=target_emp.id)
        if not allowed:
            return denial, "employee_database", denial

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
        if target_note:
            context += f"\n{target_note}"
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
