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
- app.services.employee_service
- app.services.attendance_service
- app.services.leave_service
- app.services.salary_service
- app/data/policies.json

Enforces RBAC and data isolation rules before passing context to the LLM.
No arbitrary SQL is generated or executed by the LLM.
"""

import calendar
import json
import os
import re
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.ai.guardrails import check_rbac_access
from app.database.models import Attendance, AttendanceStatus, Employee, Leave, Salary, User, UserRole
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

    # 5. Employee cues (designation, department, manager, profile)
    employee_patterns = [
        r"\bdesignation\b",
        r"\bdepartment\b",
        r"\bmanager\b",
        r"\breporting to\b",
        r"\breports to\b",
        r"\bwho is\b",
        r"\bemployee code\b",
        r"\bjoining date\b",
        r"\bjoined\b",
        r"\bprofile\b",
        r"\bteam member\b",
        r"\ball employees\b",
        r"\blist employees\b",
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


def extract_month_and_year(question: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract month (1-12) and year from question text if specified."""
    q_lower = question.lower()
    found_month = None
    for name, num in MONTH_NAMES.items():
        if re.search(r"\b" + name + r"\b", q_lower):
            found_month = num
            break

    found_year = None
    year_match = re.search(r"\b(202[0-9])\b", question)
    if year_match:
        found_year = int(year_match.group(1))
    elif found_month:
        # Default to 2024 for demo dataset when month is mentioned
        found_year = 2024

    return found_month, found_year


def find_target_employee(db: Session, question: str, current_user: User) -> Tuple[Optional[Employee], bool]:
    """
    Determine the target employee from the query.

    Returns:
        (target_employee, is_explicitly_other_employee)
    """
    q_lower = question.lower()

    # Check for self-referential terms
    self_terms = [r"\bmy\b", r"\bmine\b", r"\bme\b", r"\bi\b", r"\bmyself\b"]
    is_self = any(re.search(term, q_lower) for term in self_terms)

    # Search for known employees by code or name
    all_emps = db.query(Employee).all()
    explicit_match = None

    for emp in all_emps:
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

    if is_self:
        current_emp = db.query(Employee).filter(Employee.id == current_user.employee_id).first()
        return current_emp, False

    # Check if question refers to a third person that does not exist in company DB
    # e.g., "of John Unknown", "was Bob present", "for Alice"
    stopwords = {"the", "a", "an", "my", "our", "all", "each", "this", "company", "office", "any", "your", "latest", "standard", "designation", "department", "salary", "attendance", "leave", "overtime"}
    for m in re.finditer(r"\b(?:of|for|about|who is|was|regarding|does)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", question, re.IGNORECASE):
        candidate = m.group(1).strip().lower()
        candidate_words = set(candidate.split())
        if not candidate_words.intersection(stopwords):
            return None, True

    # Fallback to current user if asking generally about records without naming someone
    current_emp = db.query(Employee).filter(Employee.id == current_user.employee_id).first()
    return current_emp, False


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
        month, year = extract_month_and_year(question)
        q_lower = question.lower()

        # Check for company-wide payroll summary inquiry
        is_summary_query = any(k in q_lower for k in ["total salary", "company salary", "payroll summary", "total payroll"])
        if is_summary_query:
            if current_user.role not in [UserRole.ADMIN.value, UserRole.HR.value]:
                denial = "Access denied: Company-wide salary summaries are restricted to HR and Administrators."
                return denial, "salary_database", denial

            summary = salary_service.get_salary_summary(db, month=month, year=year)
            context = (
                f"Company Payroll Summary:\n"
                f"- Month: {summary.get('month') or 'All'}, Year: {summary.get('year') or 'All'}\n"
                f"- Record Count: {summary.get('record_count')}\n"
                f"- Total Gross Salary: ₹{summary.get('total_gross_salary'):,.2f}\n"
                f"- Total PF Deductions: ₹{summary.get('total_pf_deductions'):,.2f}\n"
                f"- Total Other Deductions: ₹{summary.get('total_other_deductions'):,.2f}\n"
                f"- Total Overtime Paid: ₹{summary.get('total_overtime_amount'):,.2f}\n"
                f"- Total Net Salary: ₹{summary.get('total_net_salary'):,.2f}"
            )
            return context, "salary_database", None

        # Individual employee salary inquiry
        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return "No employee record found for the requested name.", "salary_database", None

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
            period_str = f" for month {month}/{year}" if month and year else ""
            return f"No salary records found for {target_emp.name}{period_str}.", "salary_database", None

        lines = [f"Salary records for {target_emp.name} ({target_emp.employee_code}):"]
        for s in salaries:
            lines.append(
                f"- Period: {calendar.month_name[s.month]} {s.year} | "
                f"Gross Salary: ₹{s.gross_salary:,.2f} | PF: ₹{s.pf:,.2f} | "
                f"Deductions: ₹{s.deductions:,.2f} | Overtime Amount: ₹{s.overtime_amount:,.2f} | "
                f"Net Salary: ₹{s.net_salary:,.2f}"
            )
        return "\n".join(lines), "salary_database", None

    # -----------------------------------------------------------------------
    # 3. ATTENDANCE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.ATTENDANCE:
        month, year = extract_month_and_year(question)
        q_lower = question.lower()

        # Check for company-wide highest overtime inquiry (e.g. "Who worked the highest overtime in September?")
        is_highest_ot = "highest overtime" in q_lower or "most overtime" in q_lower or "max overtime" in q_lower
        if is_highest_ot:
            if current_user.role not in [UserRole.ADMIN.value, UserRole.HR.value]:
                denial = "Access denied: Company-wide overtime rankings are restricted to HR and Administrators."
                return denial, "attendance_database", denial

            # Query attendance table for highest overtime
            ot_query = db.query(
                Attendance.employee_id,
                func.sum(Attendance.overtime_minutes).label("total_ot"),
            )
            if month and year:
                start_d = date(year, month, 1)
                end_d = date(year, month, calendar.monthrange(year, month)[1])
                ot_query = ot_query.filter(Attendance.attendance_date >= start_d, Attendance.attendance_date <= end_d)

            top_ot = ot_query.group_by(Attendance.employee_id).order_by(desc("total_ot")).first()
            if top_ot and top_ot.total_ot > 0:
                top_emp = db.query(Employee).filter(Employee.id == top_ot.employee_id).first()
                emp_name = top_emp.name if top_emp else f"Employee #{top_ot.employee_id}"
                emp_code = top_emp.employee_code if top_emp else ""
                hours = top_ot.total_ot // 60
                mins = top_ot.total_ot % 60
                period_str = f"in {calendar.month_name[month]} {year}" if month and year else ""
                context = (
                    f"Highest Overtime Record {period_str}:\n"
                    f"- Employee: {emp_name} ({emp_code})\n"
                    f"- Total Overtime: {top_ot.total_ot} minutes ({hours} hours {mins} minutes)"
                )
                return context, "attendance_database", None
            else:
                return "No overtime records found for the requested period.", "attendance_database", None

        # Individual attendance inquiry
        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return "No employee record found for the requested name.", "attendance_database", None

        # RBAC Check: Employees cannot view other employees' attendance
        allowed, denial_reason = check_rbac_access(current_user, "ATTENDANCE", target_employee_id=target_emp.id)
        if not allowed:
            return denial_reason, "attendance_database", denial_reason

        # Date range filtering
        start_d, end_d = None, None
        if month and year:
            start_d = date(year, month, 1)
            end_d = date(year, month, calendar.monthrange(year, month)[1])

        summary = attendance_service.get_attendance_summary(
            db, employee_id=target_emp.id, start_date=start_d, end_date=end_d
        )

        ot_hours = summary["total_overtime_minutes"] // 60
        ot_mins = summary["total_overtime_minutes"] % 60
        period_str = f"{calendar.month_name[month]} {year}" if month and year else "All recorded dates"

        context = (
            f"Attendance summary for {target_emp.name} ({target_emp.employee_code}) for {period_str}:\n"
            f"- Total Days Recorded: {summary['total_days']}\n"
            f"- Present Days: {summary['present_days']}\n"
            f"- Absent Days: {summary['absent_days']}\n"
            f"- Late Clock-Ins: {summary['late_days']} (late entries after 09:15 AM)\n"
            f"- Overtime Days: {summary['overtime_days']}\n"
            f"- Total Overtime: {summary['total_overtime_minutes']} minutes ({ot_hours} hours {ot_mins} minutes)\n"
            f"- Total Working Minutes: {summary['total_working_minutes']}"
        )
        return context, "attendance_database", None

    # -----------------------------------------------------------------------
    # 4. LEAVE INTENT
    # -----------------------------------------------------------------------
    if intent == Intent.LEAVE:
        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return "No employee record found for the requested name.", "leave_database", None

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
        if "all employees" in q_lower or "list employees" in q_lower or "employee directory" in q_lower:
            if current_user.role not in [UserRole.ADMIN.value, UserRole.HR.value]:
                denial = "Access denied: Employee directory listing is restricted to HR and Administrators."
                return denial, "employee_database", denial

            all_emps = employee_service.get_all_employees(db)
            lines = ["Company Employees Directory:"]
            for e in all_emps:
                lines.append(f"- {e.employee_code}: {e.name} | Dept: {e.department} | Role: {e.designation}")
            return "\n".join(lines), "employee_database", None

        target_emp, is_other = find_target_employee(db, question, current_user)
        if not target_emp:
            return "No employee record found matching the inquiry.", "employee_database", None

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
