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

Targets (find_target_employee, D-043, D-044): a question is answered for a named employee (code, employee ID or
name in any case — a name that fits several employees is never guessed), for the caller when they are the
subject ("my", "did I"; not "Can I see …"), for "my manager", or for a group through a group tool. The caller's
own record is never substituted for another person, an unknown name, "his"/"her", an employee ID, a group, a
department or the company. When the target is unclear or unknown the router produces the final answer itself
(CLARIFICATION_PREFIX / NOT_FOUND_PREFIX, see direct_answer) — no records are loaded and the LLM is not called.

Group tools (HR/Admin company-wide, managers self + direct reports, employees refused): rankings, thresholds,
department-wise overtime, attendance of a team / department for a day or period, who is (was) on leave,
pending leave requests, team / department lists, and — HR/Admin only — company and department payroll totals.

Enforces RBAC and data isolation rules before passing context to the LLM.
No arbitrary SQL is generated or executed by the LLM, and this module runs no queries of its own.
"""

import calendar
import json
import os
import re
from dataclasses import dataclass, field
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
        # "How many casual leaves are allowed?" (PRD §11) is a policy question, not the caller's balance
        r"\b(leaves?|holidays?|work from home|wfh|days? off)\b.{0,40}\b(allowed|permitted|eligible)\b",
        r"\b(allowed|permitted|eligible)\b.{0,40}\b(leaves?|holidays?|work from home|wfh|days? off)\b",
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
        r"\bwho (all )?works? (in|for|under)\b",
        r"\bwho (all )?(is|are) (in|on) (my|the|our)\b",
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
_STRONG_SELF_RX = re.compile(
    r"\b(my|mine|myself)\b|\b(was|am|did|have|had)\s+i\b"
    r"|\bi\s+(was|am|have|had|did|took|worked|earned|got|applied)\b"
)
# "Can I see …", "show me …", "I want to know …": the user is the requester here, not the subject of the question
_REQUESTER_RX = re.compile(
    r"\b(can|could|may|should)\s+i\s+(see|know|get|view|check|ask|find out)\b|\b(show|tell|give|send|let|help)\s+me\b"
    r"|\bi\s+(want|would like|need|wish)\s+to\s+(know|see|check|view|find out)\b|\bi\s+(want|need)\b"
)
# He / she / they without a name: someone else, but nobody identifiable
_THIRD_PERSON_RX = re.compile(r"\b(he|him|his|she|her|hers|they|them|their|theirs)\b")
# "my manager", "my boss": the caller's reporting manager (employees.manager_id)
_MY_MANAGER_RX = re.compile(r"\bmy (?:reporting |direct |line )?(?:manager|boss|supervisor|team ?lead)('s|’s)?")
_THIS_MONTH_RX = re.compile(r"\b(this|current) month\b")
_LAST_MONTH_RX = re.compile(r"\b(last|previous|past) month\b")
_THIS_WEEK_RX = re.compile(r"\b(this|current) week\b")
_LAST_WEEK_RX = re.compile(r"\b(last|previous|past) week\b")
_TODAY_RX = re.compile(r"\btoday\b")
_YESTERDAY_RX = re.compile(r"\byesterday\b")

# Context that asks the user to name a person / rephrase instead of answering (chat confidence
# "clarification_needed"). No HR figures are ever put in such a context.
CLARIFICATION_PREFIX = "Clarification needed:"
# Context for a name / code / employee ID that identifies nobody (PRD §29 "I could not find an employee named …").
# Like a clarification it is the final answer (direct_answer) — the LLM is not called.
NOT_FOUND_PREFIX = "Employee not found:"

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
    r"|\bcolleagues?'?s?\b|\bco-?workers?'?s?\b|\bpeers?'?s?\b|\bteam ?mates?'?s?\b"
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


def refers_to_self(question: str) -> bool:
    """
    True when the caller is the subject ("my salary", "was I late", "how many hours did I work").
    "I" / "me" as the requester ("Can I see the payroll?", "Show me Rahul's leave") does not count.
    """
    q_lower = question.lower()
    return bool(_SELF_RX.search(_REQUESTER_RX.sub(" ", q_lower)))


def refers_to_third_person(question: str) -> bool:
    """True for "his salary", "was she present" — another person, but nobody identifiable."""
    return bool(_THIRD_PERSON_RX.search(question.lower()))


def named_departments(db: Session, question: str) -> List[str]:
    """Department names (from the employee data, D-005) written in the question."""
    q_lower = question.lower()
    return [d["name"] for d in employee_service.list_departments(db) if d["name"].lower() in q_lower]


def refers_to_group(db: Session, question: str) -> bool:
    """True when the question is about a team, a department, several employees or the whole company."""
    return bool(_GROUP_RX.search(question.lower())) or bool(named_departments(db, question))


@dataclass
class EmployeeMatch:
    """Who a question names (match_employees)."""
    employee: Optional[Employee] = None                         # exactly one person named
    candidates: List[Employee] = field(default_factory=list)    # one written name fits several employees
    mention: Optional[str] = None                               # the code / ID / name as written
    multiple: bool = False                                      # several different people named
    asked: bool = False                                         # a code / employee ID / name was written
    by_identifier: bool = False                                 # named by code or employee ID (not by name)


# Words that are never read as a person's name (KI-038: names are matched case-insensitively, so ordinary
# words in the "name slots" below must be excluded explicitly). Department names come from the data.
_NOT_A_NAME = {
    # determiners, pronouns, question words
    "the", "a", "an", "my", "our", "your", "his", "her", "their", "its", "this", "that", "these", "those", "all",
    "each", "every", "any", "some", "no", "me", "us", "him", "them", "it", "i", "you", "we", "they", "he", "she",
    "one", "someone", "somebody", "anyone", "anybody", "everyone", "everybody", "nobody", "myself", "yourself",
    "who", "whom", "whose", "what", "which", "how", "when", "where", "why", "there", "here", "else", "other",
    "another", "same", "own", "both", "either", "more", "less", "most", "least", "many", "much", "few", "not",
    "in", "on", "at", "to", "by", "with", "from", "and", "or", "of", "for", "about", "as", "per", "into", "than",
    "is", "was", "are", "were", "be", "been", "do", "did", "does", "has", "had", "have", "get", "got", "can",
    "will", "would", "should", "could", "may", "might", "please", "kindly", "show", "tell", "give", "list",
    # time
    "today", "yesterday", "tomorrow", "day", "days", "week", "weeks", "weekly", "month", "months", "monthly",
    "year", "years", "yearly", "quarter", "date", "dates", "period", "time", "last", "previous", "current", "next",
    "past", "recent", "latest", "this", "now", "morning", "evening", "weekend", "weekends", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "fy",
    # HR vocabulary
    "salary", "salaries", "pay", "payroll", "payslip", "payslips", "pf", "provident", "fund", "overtime", "ot",
    "attendance", "leave", "leaves", "balance", "balances", "holiday", "holidays", "policy", "policies", "rule",
    "rules", "late", "lateness", "absent", "absence", "absences", "present", "presence", "hours", "hour",
    "minutes", "minute", "work", "working", "worked", "shift", "shifts", "team", "teams", "department",
    "departments", "company", "organisation", "organization", "employee", "employees", "staff", "people",
    "person", "member", "members", "manager", "managers", "hr", "admin", "administrator", "report", "reports",
    "reporting", "record", "records", "data", "details", "detail", "information", "info", "profile", "summary",
    "history", "status", "deduction", "deductions", "gross", "net", "amount", "total", "totals", "average",
    "count", "number", "code", "id", "emp", "designation", "role", "joining", "new", "sick", "casual", "earned",
    "unpaid", "annual", "maternity", "paternity", "approved", "pending", "rejected", "cancelled", "approval",
    "request", "requests", "application", "applications", "office", "home", "remote", "wfh", "interns", "intern",
    "contractors", "contractor", "trainees", "trainee", "consultants", "everyone's", "colleague", "colleagues",
    "boss", "supervisor", "lead", "subordinates", "user", "users", "access", "system", "assistant", "question",
    # relatives and events ("leave for my sister's wedding")
    "sister", "brother", "mother", "father", "mom", "dad", "wife", "husband", "son", "daughter", "child",
    "children", "kids", "parents", "family", "friend", "cousin", "uncle", "aunt", "wedding", "marriage",
    "birthday", "festival", "diwali", "holi", "eid", "christmas", "pongal", "onam", "medical", "doctor",
    # English words that are also given names — only matched as part of a full name
    "grace", "mark", "will", "hope", "joy", "rose", "bill", "faith", "sunny", "summer", "may", "june", "april",
    "august",
} | set(MONTH_NAMES)

# Slots in which a word is read as a person's name even when it is written in lower case (KI-038):
# "bruce's salary", "was bruce present", "did bruce work", "who is bruce".
_PERSON_SLOT_RXS = [
    re.compile(r"(?<!\bmy )(?<!\bour )(?<!\byour )(?<!\bhis )(?<!\bher )(?<!\bthe )\b([a-z]+)(?:'|’)s\b"),
    re.compile(
        r"\b(?:was|is|did|does|has|had|were|will|can|could)\s+([a-z]+)(?:\s+([a-z]+))?\s+(?:present|absent|late|"
        r"on\s+leave|work|working|worked|take|took|taken|apply|applied|get|got|earn|earns|earned|paid|attend|"
        r"attended|come|came|join|joined|clock|clocked|check|checked)\b"
    ),
    re.compile(r"\bwho\s+is\s+([a-z]+)(?:\s+([a-z]+))?\s*[?.!]*$"),
]
# "salary of bruce", "attendance for bruce wayne" — only when the caller is not the subject
# ("did I take leave for diwali?" is about the caller).
_OF_PERSON_RX = re.compile(r"\b(?:of|for|about|regarding)\s+(?:employee\s+|mr\.?\s+|ms\.?\s+|mrs\.?\s+)?([a-z]+)(?:\s+([a-z]+))?")


def _contains_word(word: str, text: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text))


def _name_tokens(name: str) -> List[str]:
    return re.findall(r"[a-z]+", name.lower())


def _code_number(code: str) -> Optional[int]:
    """EMP004 → 4; codes that are not letters + digits (EMP-GGL-1A2B3C) have no employee number."""
    m = re.fullmatch(r"[A-Za-z]+-?0*(\d+)", code.strip())
    return int(m.group(1)) if m else None


def match_employees(db: Session, question: str) -> EmployeeMatch:
    """
    Who a question names, by employee code ("EMP004"), employee ID ("employee 4" — the number of the code) or
    name, case-insensitively ("Aman", "aman gupta", "SURAJ", "gupta"). A full name wins over a first name or
    surname; a name that fits several employees ("Sharma") is returned as `candidates`, never resolved by guess;
    two different people in one question set `multiple`.
    """
    q_lower = question.lower()
    employees = employee_service.get_all_employees(db)

    for emp in employees:
        if _contains_word(emp.employee_code.lower(), q_lower):
            return EmployeeMatch(employee=emp, mention=emp.employee_code, asked=True, by_identifier=True)

    id_match = _EMPLOYEE_ID_RX.search(q_lower)
    if id_match:
        number = int(id_match.group(1))
        written = id_match.group(0).strip()
        mention = written.upper() if " " not in written else written
        for emp in employees:
            if _code_number(emp.employee_code) == number:
                return EmployeeMatch(employee=emp, mention=mention, asked=True, by_identifier=True)
        return EmployeeMatch(mention=mention, asked=True, by_identifier=True)

    full: Dict[str, List[Employee]] = {}
    for emp in employees:
        if _contains_word(emp.name.lower().strip(), q_lower):
            full.setdefault(emp.name.lower().strip(), []).append(emp)
    consumed = {tok for name in full for tok in _name_tokens(name)}
    by_token: Dict[str, Dict[int, Employee]] = {}
    for emp in employees:
        for tok in _name_tokens(emp.name):
            if len(tok) >= 3 and tok not in consumed and tok not in _NOT_A_NAME and _contains_word(tok, q_lower):
                by_token.setdefault(tok, {})[emp.id] = emp

    people: Dict[int, Employee] = {}
    groups: List[Tuple[str, List[Employee]]] = []
    for name, emps in full.items():
        if len(emps) == 1:
            people[emps[0].id] = emps[0]
        else:
            groups.append((name, emps))
    for tok, emps_by_id in by_token.items():
        if len(emps_by_id) == 1:
            emp = next(iter(emps_by_id.values()))
            people[emp.id] = emp
        else:
            groups.append((tok, list(emps_by_id.values())))
    # an ambiguous surname that also fits a person named elsewhere in the question narrows to them ("rahul … sharma")
    open_groups = [(w, emps) for w, emps in groups if not any(e.id in people for e in emps)]

    if len(people) > 1 or (people and open_groups) or len(open_groups) > 1:
        return EmployeeMatch(multiple=True, asked=True)
    if people:
        emp = next(iter(people.values()))
        return EmployeeMatch(employee=emp, mention=emp.name, asked=True)
    if open_groups:
        word, emps = open_groups[0]
        return EmployeeMatch(candidates=sorted(emps, key=lambda e: e.name), mention=word, asked=True)
    return EmployeeMatch()


def find_named_employee(db: Session, question: str) -> Tuple[Optional[Employee], bool]:
    """
    The one employee a question names by code, employee ID or name (match_employees).

    Returns (employee, named): (None, True) when a code / ID / name was written that identifies nobody
    (unknown, or fits several employees — see match_employees for which).
    """
    match = match_employees(db, question)
    return match.employee, match.asked


def unknown_person_mention(db: Session, question: str) -> Optional[str]:
    """
    A name of someone who is not an employee ("was bruce present", "salary of John Unknown"), case-insensitive
    (KI-038), or None. Only called after match_employees() found nobody.
    """
    q_lower = question.lower()
    excluded = _NOT_A_NAME | {tok for d in employee_service.list_departments(db) for tok in _name_tokens(d["name"])}

    def mention(groups: Tuple[Optional[str], ...]) -> Optional[str]:
        words = [g for g in groups if g]
        if not words or words[0] in excluded or len(words[0]) < 2:
            return None
        return " ".join(w for w in words[:1] + [w for w in words[1:2] if w not in excluded])

    for rx in _PERSON_SLOT_RXS:
        for m in rx.finditer(q_lower):
            found = mention(m.groups())
            if found:
                return found
    if not _STRONG_SELF_RX.search(q_lower):
        for m in _OF_PERSON_RX.finditer(q_lower):
            found = mention(m.groups())
            if found:
                return found
    return None


def _own_record_note(own: Employee) -> str:
    return (
        f"Note: no person was named, so these are the records of the user themself, {own.name} "
        f"({own.employee_code}) — the only employee whose records of this kind this user can see. Say so in the answer."
    )


def find_target_employee(
    db: Session, question: str, current_user: User, intent: Optional["Intent"] = None
) -> Tuple[Optional[Employee], bool, Optional[str]]:
    """
    The one employee a question is about.

    Returns (target_employee, is_other, note):
      - a named employee (code, employee ID or name, any case)  → (employee, employee is not the caller, None)
      - a code / ID / name that identifies nobody (unknown, or fits several employees), several people named,
        an unnamed "another employee" / "a colleague", "his" / "her"     → (None, True, None)
      - "my manager's …" (not for "who is my manager")        → (the caller's manager, True, None)
      - a group, team, department or company question        → (None, False, None)
      - "my", "I", "me" as the subject                       → (caller, False, None)
      - nobody named and no self reference: when the caller can only ever see their own records of this kind
        (employees: everything; managers: salary), a plain question ("How much PF was deducted?") is about them —
        returned with a note the answer must state. Otherwise (and for aggregate / "who" wording) the target is
        unknown → (None, False, None).
    The caller's own record is never used for a question about someone else or about a group (D-043, D-044).
    """
    match = match_employees(db, question)
    if match.employee:
        return match.employee, match.employee.id != current_user.employee_id, None
    if match.asked or refers_to_unnamed_other(question):
        return None, True, None
    if refers_to_group(db, question):
        return None, False, None

    q_lower = question.lower()
    own = current_user.employee
    manager_ref = _MY_MANAGER_RX.search(q_lower)
    if manager_ref and not (intent == Intent.EMPLOYEE and not manager_ref.group(1) and "of my" not in q_lower):
        boss = own.manager if own else None
        return boss, True, None
    if unknown_person_mention(db, question) or refers_to_third_person(question):
        return None, True, None
    if refers_to_self(question):
        return own, False, None

    if own and not _AGGREGATE_RX.search(q_lower) and (
        current_user.role == UserRole.EMPLOYEE.value
        or (intent == Intent.SALARY and current_user.role not in COMPANY_WIDE_ROLES)
    ):
        return own, False, _own_record_note(own)
    return None, False, None


_GROUP_HELP = (
    "Questions about several employees I can answer: rankings (\"Who worked the most overtime this month?\"), "
    "thresholds (\"Show employees with more than 5 late entries\"), \"Which members of my team worked overtime "
    "last week?\", department-wise overtime, attendance of a team or department (\"How many employees were "
    "present today?\"), headcount and team lists, who is on leave, pending leave requests, and — for HR and "
    "Administrators — company and department payroll summaries."
)


def direct_answer(context: str) -> Optional[str]:
    """
    The final answer when the router already knows it (D-044): a clarification question or an
    "employee not found" message. POST /chat returns it as is and does not call the LLM.
    """
    for prefix in (CLARIFICATION_PREFIX, NOT_FOUND_PREFIX):
        if context.startswith(prefix):
            return context[len(prefix):].strip()
    return None


def _may_see_others(current_user: User, intent: Intent) -> bool:
    """Whether the role may see this kind of data for anyone but themself (AGENTS.md §3.2)."""
    if intent == Intent.SALARY:
        return current_user.role in COMPANY_WIDE_ROLES
    if intent in (Intent.ATTENDANCE, Intent.LEAVE, Intent.EMPLOYEE):
        return current_user.role != UserRole.EMPLOYEE.value
    return True


def _missing_target_response(
    db: Session,
    current_user: User,
    intent: Intent,
    question: str,
    data_source: str,
    is_other: bool,
) -> Tuple[str, str, Optional[str]]:
    """
    Answer when find_target_employee() found nobody. No record is loaded for anyone, and the result is either
    the standard access denial or a direct answer for the user (direct_answer(), the LLM is not called):
      - several people named → ask for one at a time;
      - a name that fits several employees → list the ones the caller may see, ask for the full name / code;
      - a name / code / employee ID that matches nobody → "I could not find an employee named …" (PRD §29) —
        for roles that may not see other people's data of this kind, the same denial as for a real colleague,
        so the chat cannot be used to find out who works here;
      - an unnamed "another employee" / "his" / a group without a tool → denial for those roles (D-030),
        otherwise a clarification; nobody named at all → ask whose records are meant (never the caller's).
    """
    match = match_employees(db, question)
    may_see = _may_see_others(current_user, intent)
    # target -1 never matches the caller or a subordinate, so the standard denial is returned
    _, denial = check_rbac_access(current_user, intent.value, target_employee_id=-1)
    denial = denial or "Access denied."

    if match.multiple:
        return (
            f"{CLARIFICATION_PREFIX} Your question names more than one person. Please ask about one employee "
            "at a time (by name or employee code)."
        ), data_source, None

    if match.candidates:
        visible = [
            c for c in match.candidates
            if c.id == current_user.employee_id or check_rbac_access(current_user, intent.value, c.id)[0]
        ]
        if not visible:
            return denial, data_source, denial
        options = "; ".join(f"{c.name} ({c.employee_code})" for c in visible)
        return (
            f"{CLARIFICATION_PREFIX} More than one employee matches \"{match.mention.title()}\". Which one do you "
            f"mean: {options}? Please ask again with the full name or the employee code."
        ), data_source, None

    third_person = refers_to_unnamed_other(question) or refers_to_third_person(question)
    if is_other and not third_person:
        if not may_see:
            return denial, data_source, denial
        if match.by_identifier:
            if " " in (match.mention or ""):  # "employee 1025"
                return f"{NOT_FOUND_PREFIX} I could not find {match.mention}.", data_source, None
            return (f"{NOT_FOUND_PREFIX} I could not find an employee with the code "
                    f"\"{match.mention}\"."), data_source, None
        if _MY_MANAGER_RX.search(question.lower()):
            return f"{NOT_FOUND_PREFIX} No reporting manager is recorded for you in the HR system.", data_source, None
        name = unknown_person_mention(db, question)
        if name:
            return f"{NOT_FOUND_PREFIX} I could not find an employee named \"{name.title()}\".", data_source, None
        return f"{NOT_FOUND_PREFIX} I could not find that employee in the HR records.", data_source, None

    group = not is_other and refers_to_group(db, question)
    if (third_person or group) and not may_see:
        return denial, data_source, denial
    if third_person:
        return (
            f"{CLARIFICATION_PREFIX} Which employee do you mean? Please give their name or employee code."
        ), data_source, None
    if group:
        return (
            f"{CLARIFICATION_PREFIX} I can't answer that question about a group of employees from the HR data, "
            f"so nothing was retrieved. {_GROUP_HELP}"
        ), data_source, None
    return (
        f"{CLARIFICATION_PREFIX} Whose records do you mean? Please name the employee (name or employee code), "
        "say \"my\" for your own records, or ask a team or company-level question."
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
# A question about people (not "how many days"): "who was present", "which of my team", "how many employees"
_WHO_PEOPLE_RX = re.compile(r"\b(who|whom)\b|\b(which|how many) (of|employees|people|staff|members|persons)\b")
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


# "Who is absent?", "How many employees are present?" — present tense without a period means today
_PRESENT_TENSE_RX = re.compile(r"\b(is|are)\s+(present|absent|late|on leave|in (the )?office|working)\b")


def _group_date_range(db: Session, question: str) -> Tuple[Optional[date], Optional[date], str, Optional[str]]:
    """resolve_date_range() for group attendance questions; present-tense presence wording without a period → today."""
    start_d, end_d, period, note = resolve_date_range(db, question)
    if start_d is None and _PRESENT_TENSE_RX.search(question.lower()):
        today = date.today()
        return today, today, f"today ({today})", None
    return start_d, end_d, period, note


_PER_EMPLOYEE_LIMIT = 25  # group attendance contexts list individual employees only up to this many


def _summary_line(summary: Dict[str, Any]) -> str:
    pct = attendance_service.attendance_percentage(summary)
    pct_text = (
        f"attendance {pct['percentage']}% ({_number(pct['attended_days'])} of {pct['working_days']} recorded "
        "working days attended)" if pct["percentage"] is not None else "attendance % not available (no working days)"
    )
    return (
        f"{pct_text}; present days {summary['present_days']}, half days {summary['half_day_days']}, absent days "
        f"{summary['absent_days']}, leave days {summary['leave_days']}, late entries {summary['late_days']}, "
        f"overtime {_format_minutes(summary['total_overtime_minutes'])}"
    )


def _attendance_overview_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """
    Attendance of several employees (KI-039) — same roles and scope as the rankings (D-032):
      - one day ("today", "yesterday", "is … present")  → attendance_service.get_daily_attendance: counts per
        status and who is in each status (active employees; `not_marked` when there is no record);
      - a period → attendance_service.get_group_attendance_summaries: per department (and per employee for up to
        25 people) present / half / absent / leave days, late entries, overtime and attendance %.
    All numbers are calculated here (PRD §20); the LLM only phrases them.
    """
    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        return _group_denial("Attendance figures")

    scope_ids, scope_text = _group_scope(db, current_user, question)
    departments = named_departments(db, question)
    if departments:
        scope_text += f", department {', '.join(departments)}"
    start_d, end_d, period, note = _group_date_range(db, question)

    if start_d is not None and start_d == end_d:
        sheet = attendance_service.get_daily_attendance(db, target_date=start_d, scope_ids=scope_ids)
        rows = [r for r in sheet["rows"] if not departments or r["department"] in departments]
        if not any(r["status"] != "not_marked" for r in rows):
            context = f"No attendance has been recorded for {period} ({scope_text}). Checked by the HR system."
            return (f"{context}\n{note}" if note else context), "attendance_database", None
        labels = {
            "present": "Present", "half_day": "Half day", "absent": "Absent", "leave": "On leave",
            "holiday": "Holiday", "weekend": "Weekend", "not_marked": "No attendance recorded",
        }
        lines = [
            f"Attendance for {period}, {scope_text} (from the HR system): {len(rows)} active employee"
            f"{'s' if len(rows) != 1 else ''}."
        ]
        for status_key, label in labels.items():
            people = [r for r in rows if r["status"] == status_key]
            if people:
                names = ", ".join(
                    f"{r['name']} ({r['employee_code']}{', late ' + str(r['late_minutes']) + ' min' if r['late_minutes'] else ''})"
                    for r in people
                )
                lines.append(f"- {label}: {len(people)} — {names}")
        late = sum(1 for r in rows if (r["late_minutes"] or 0) > 0)
        lines.append(f"Late arrivals among them: {late}.")
        return "\n".join(lines), "attendance_database", None

    summaries = attendance_service.get_group_attendance_summaries(db, start_date=start_d, end_date=end_d, scope_ids=scope_ids)
    if departments:
        summaries = [s for s in summaries if s["department"] in departments]
    if not summaries:
        context = f"No attendance records found for {period} ({scope_text}). Attendance data is not available for the requested period."
        return (f"{context}\n{note}" if note else context), "attendance_database", None

    who = "1 employee's records" if len(summaries) == 1 else f"{len(summaries)} employees' records"
    lines = [f"Attendance for {period}, {scope_text} (calculated by the HR system from {who}):"]
    by_department: Dict[str, List[Dict[str, Any]]] = {}
    for s in summaries:
        by_department.setdefault(s["department"], []).append(s)
    for department, items in by_department.items():
        lines.append(f"- {department} ({len(items)} employee{'s' if len(items) != 1 else ''}): "
                     f"{_summary_line(attendance_service.combine_summaries(items))}")
    if len(by_department) > 1:
        lines.append(f"- All of these: {_summary_line(attendance_service.combine_summaries(summaries))}")
    if len(summaries) <= _PER_EMPLOYEE_LIMIT:
        lines.append("Per employee:")
        lines += [f"- {s['employee_name']} ({s['employee_code']}, {s['department']}): {_summary_line(s)}" for s in summaries]
    if note:
        lines.append(note)
    return "\n".join(lines), "attendance_database", None


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
    departments = named_departments(db, question)
    group = refers_to_group(db, question)
    who_without_self = bool(_WHO_RX.search(q_lower)) and not refers_to_self(question)
    if not metric:
        # "How many employees were present today?", "attendance of the Engineering department", "my team's
        # attendance this month", "department-wise attendance" — but not "How many days present?" (whose?)
        if group or (_WHO_PEOPLE_RX.search(q_lower) and not refers_to_self(question)):
            return _attendance_overview_context(db, current_user, question)
        return None
    threshold = _parse_threshold(question)
    department_wise = metric == "overtime" and bool(_DEPARTMENT_WISE_RX.search(q_lower))
    if not (department_wise or group or who_without_self):
        return None

    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        return _group_denial("Attendance figures")

    scope_ids, scope_text = _group_scope(db, current_user, question)
    start_d, end_d, period, note = _group_date_range(db, question)

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


_PENDING_REQUESTS_RX = re.compile(
    r"\bpending\b.{0,30}\b(requests?|approvals?|applications?)\b|\b(requests?|applications?)\b.{0,30}\bpending\b"
    r"|\bawaiting (my )?approval\b|\b(leaves?|requests?) (to|for me to) approve\b|\bneed(s)? (my )?approval\b"
)


def _pending_leaves_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """
    Leave requests waiting for a decision — the approval queue of the caller: HR/Admin company-wide, managers
    their direct reports. The caller's own requests are left out (nobody approves their own leave, D-022).
    """
    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        denial = "Access denied: Leave records of other employees are restricted to HR, Administrators and managers."
        return denial, "leave_database", denial
    scope_ids, scope_text = _group_scope(db, current_user, question)
    if scope_ids is not None:
        scope_ids = scope_ids - {current_user.employee_id}
        scope_text = "your direct reports"
    pending = leave_service.list_leaves(db, scope_ids=scope_ids, status="pending")
    pending = [p for p in pending if p["employee_id"] != current_user.employee_id]
    departments = named_departments(db, question)
    if departments:
        pending = [p for p in pending if p["department"] in departments]
        scope_text += f", department {', '.join(departments)}"
    if not pending:
        return (f"No leave requests are pending approval ({scope_text}; your own requests are reviewed by someone "
                "else and not listed). Checked by the HR system."), "leave_database", None
    lines = [
        f"Leave requests pending approval, {scope_text} (from the HR system; your own requests are not listed): "
        f"{len(pending)} request{'s' if len(pending) != 1 else ''}."
    ]
    for p in sorted(pending, key=lambda p: p["from_date"]):
        lines.append(
            f"- {p['employee_name']} ({p['employee_code']}, {p['department']}): {p['leave_type']} leave "
            f"{p['from_date']} to {p['to_date']}, {_days(p['days'])} (working days), applied "
            f"{str(p['applied_at'])[:10] if p['applied_at'] else 'on an unrecorded date'}"
        )
    return "\n".join(lines), "leave_database", None


def _on_leave_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """Who is / was on approved leave on a day or in a period — HR/Admin company-wide, managers their team."""
    if current_user.role not in COMPANY_WIDE_ROLES and current_user.role != UserRole.MANAGER.value:
        denial = "Access denied: Leave records of other employees are restricted to HR, Administrators and managers."
        return denial, "leave_database", denial

    q_lower = question.lower()
    today = date.today()
    end_date: Optional[date] = None
    if "tomorrow" in q_lower:
        on_date = today + timedelta(days=1)
        label = f"tomorrow ({on_date})"
    else:
        # "today" / "yesterday" / "last week" / "this month" / "in August 2024"; nothing named → today
        start_d, end_d, period, _ = resolve_date_range(db, question, source="leave")
        if start_d is None:
            on_date, label = today, f"today ({today})"
        else:
            on_date, end_date = start_d, (end_d if end_d != start_d else None)
            label = period if period.split()[0] in ("today", "yesterday", "this", "last") else f"in {period}"
    verb = "were" if (end_date or on_date) < today else "are"
    scope_ids, scope_text = _group_scope(db, current_user, question)
    on_leave = leave_service.get_employees_on_leave(db, on_date, scope_ids=scope_ids, end_date=end_date)
    departments = named_departments(db, question)
    if departments:
        on_leave = [r for r in on_leave if r["department"] in departments]
        scope_text += f", department {', '.join(departments)}"

    if not on_leave:
        return (
            f"No employees {verb} on approved leave {label} ({scope_text}). Checked by the HR system."
        ), "leave_database", None
    people = len({r["employee_id"] for r in on_leave})
    lines = [
        f"Employees on approved leave {label}, {scope_text} (from the HR system): "
        f"{people} employee{'s' if people != 1 else ''}."
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


def _payroll_lines(totals: Dict[str, Any]) -> str:
    records, people = totals["record_count"], totals["employee_count"]
    return (
        f"{records} salary record{'s' if records != 1 else ''} ({people} employee{'s' if people != 1 else ''}); gross "
        f"₹{totals['total_gross_salary']:,.2f}; PF ₹{totals['total_pf']:,.2f}; other deductions "
        f"₹{totals['total_deductions']:,.2f}; overtime paid ₹{totals['total_overtime_amount']:,.2f}; net "
        f"₹{totals['total_net_salary']:,.2f}"
    )


def _department_payroll_context(
    db: Session,
    month: Optional[int],
    year: Optional[int],
    period: str,
    departments: List[str],
    note: Optional[str],
) -> Tuple[str, str, Optional[str]]:
    """Payroll totals for the named department(s), or for every department — aggregates only (AGENTS.md §3.6)."""
    rows = salary_service.get_payroll_by_department(db, month=month, year=year)
    if departments:
        rows = [r for r in rows if r["department"] in departments]
    if not rows:
        which = f" in {', '.join(departments)}" if departments else ""
        context = f"No salary records found{which} for {period}."
        return (f"{context}\n{note}" if note else context), "salary_database", None
    lines = [f"Payroll by department for {period} (totals calculated by the HR system; no individual salaries):"]
    lines += [f"- {r['department']}: {_payroll_lines(r)}" for r in rows]
    if len(rows) > 1:
        keys = ("record_count", "employee_count", "total_gross_salary", "total_pf", "total_deductions",
                "total_overtime_amount", "total_net_salary")
        lines.append(f"- All of these departments: {_payroll_lines({k: sum(r[k] for r in rows) for k in keys})}")
    if note:
        lines.append(note)
    return "\n".join(lines), "salary_database", None


_TEAM_LIST_RX = re.compile(
    r"\b(team members|members of my team|my (direct )?reports|reports? to me|my subordinates|in my team|my team)\b"
)
_LIST_WORDS_RX = re.compile(r"\b(who|list|show|members?|employees|staff|people|works?)\b")


def _directory_context(db: Session, current_user: User, question: str) -> Tuple[str, str, Optional[str]]:
    """
    Employee list — same scope as GET /employees: HR/Admin everyone, managers themself + direct reports (D-039),
    employees refused. Optionally limited to "my team" or named departments.
    """
    if current_user.role == UserRole.EMPLOYEE.value:
        denial = (
            "Access denied: The employee directory and other employees' personal information "
            "are restricted to HR and Administrators."
        )
        return denial, "employee_database", denial
    scope_ids, scope_text = _group_scope(db, current_user, question)
    departments = named_departments(db, question)
    employees = employee_service.list_employees(db, scope_ids=scope_ids)
    if departments:
        employees = [e for e in employees if e.department in departments]
        scope_text += f", department {', '.join(departments)}"
    if not employees:
        return f"No employees found ({scope_text}).", "employee_database", None
    title = "Company Employees Directory" if scope_text == "company-wide" else "Employees"
    lines = [f"{title} ({scope_text}, from the HR system): {len(employees)} employee{'s' if len(employees) != 1 else ''}."]
    for e in employees:
        manager = e.manager.name if e.manager else "none"
        lines.append(
            f"- {e.employee_code}: {e.name} | Dept: {e.department} | Role: {e.designation} | Status: {e.status} "
            f"| Manager: {manager}"
        )
    return "\n".join(lines), "employee_database", None


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
        # A named department or "department-wise" → per-department totals (KI-039). HR/Admin only.
        q_lower = question.lower()
        target_emp, is_other, target_note = find_target_employee(db, question, current_user, intent)
        nobody_named = (target_emp is None or target_note is not None) and not is_other
        departments = named_departments(db, question)
        department_wise = bool(_DEPARTMENT_WISE_RX.search(q_lower))
        is_company_query = not departments and not department_wise and (
            bool(_COMPANY_SALARY_RX.search(q_lower) and not (target_emp and not target_note))
            or (bool(re.search(r"\bpayroll\b", q_lower)) and nobody_named and not refers_to_self(question))
        )
        # "salary of the Engineering department", "department-wise payroll" (nobody named) → department totals
        is_department_query = nobody_named and (bool(departments) or department_wise)
        if is_company_query or is_department_query:
            if current_user.role not in COMPANY_WIDE_ROLES:
                denial = (
                    "Access denied: Company-wide and department salary summaries are restricted to HR and "
                    "Administrators."
                )
                return denial, "salary_database", denial

            if month is None and year is None:
                latest = salary_service.get_latest_payroll_period(db)
                if latest:
                    month, year = latest
                    note = "Note: no period was given, so the latest payroll month is used."
            period = _period_label(month, year)
            if is_department_query:
                return _department_payroll_context(db, month, year, period, departments, note)
            summary = salary_service.get_salary_summary(db, month=month, year=year)
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
        target_emp, is_other, target_note = find_target_employee(db, question, current_user, intent)
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
        # "How many employees are on leave today?", "Who on my team was on leave last week?" (nobody named)
        q_lower = question.lower()
        named, asked = find_named_employee(db, question)
        about_self = refers_to_self(question)
        if (
            _ON_LEAVE_RX.search(q_lower) and not named and not asked
            and (refers_to_group(db, question) or (_WHO_RX.search(q_lower) and not about_self)
                 or re.search(r"\b(anyone|anybody|someone|somebody)\b", q_lower))
        ):
            return _on_leave_context(db, current_user, question)
        # "How many leave requests are pending?" from an approver — their approval queue, not their own leave
        if (
            _PENDING_REQUESTS_RX.search(q_lower) and not named and not asked and not about_self
            and current_user.role != UserRole.EMPLOYEE.value
        ):
            return _pending_leaves_context(db, current_user, question)

        target_emp, is_other, target_note = find_target_employee(db, question, current_user, intent)
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

        # Lists: "List all employees", "Who is in my team?", "Who works in Engineering?" — GET /employees scope
        named, asked = find_named_employee(db, question)
        team_or_department_list = not named and not asked and (
            bool(_TEAM_LIST_RX.search(q_lower))
            or (bool(named_departments(db, question)) and bool(_LIST_WORDS_RX.search(q_lower)))
        )
        if _DIRECTORY_RX.search(q_lower) or team_or_department_list:
            return _directory_context(db, current_user, question)

        target_emp, is_other, target_note = find_target_employee(db, question, current_user, intent)
        if not target_emp:
            return _missing_target_response(db, current_user, intent, question, "employee_database", is_other)

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
