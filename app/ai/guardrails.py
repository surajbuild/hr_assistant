"""
app/ai/guardrails.py
--------------------
Security, RBAC validation, and anti-hallucination guardrails for the AI assistant.
"""

import re
from typing import Optional, Tuple
from app.database.models import User, UserRole


def check_rbac_access(
    current_user: User,
    intent: str,
    target_employee_id: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Verify if the authenticated user is authorized to access the requested HR data.

    Rules:
    - Policy inquiries: Allowed for all authenticated users.
    - General inquiries: Allowed for all authenticated users.
    - Self data: All users can view their own employee, attendance, leave, and salary records.
    - Other employee's salary:
      * HR & Admin: Allowed.
      * Manager & Employee: FORBIDDEN.
    - Other employee's leaves:
      * HR & Admin: Allowed.
      * Manager: Allowed for subordinates (or HR/Admin).
      * Employee: FORBIDDEN.
    - Other employee's attendance:
      * HR & Admin: Allowed.
      * Manager: Allowed for subordinates.
      * Employee: FORBIDDEN.
    - Employee directory / all employees:
      * HR & Admin: Allowed.
      * Manager & Employee: Limited to self profile.
    - Another employee's profile (EMPLOYEE intent) — same as GET /employees/{id} (D-039):
      * HR & Admin: Allowed.
      * Manager: direct reports only.
      * Employee: FORBIDDEN.

    Returns:
        (is_allowed, denial_reason)
    """
    user_role = current_user.role
    user_emp_id = current_user.employee_id

    # Policy and General are public to any authenticated user
    if intent in ["POLICY", "GENERAL", "UNKNOWN"]:
        return True, None

    # If querying own data (target matches user's linked employee)
    if target_employee_id is not None and target_employee_id == user_emp_id:
        return True, None

    # Admin and HR have company-wide access to all HR records
    if user_role in [UserRole.ADMIN.value, UserRole.HR.value]:
        return True, None

    # Manager: authorized for direct subordinates (Team data) for Attendance & Leaves, but NOT Salary
    if user_role == UserRole.MANAGER.value:
        subordinate_ids = (
            {sub.id for sub in current_user.employee.subordinates}
            if current_user.employee and current_user.employee.subordinates
            else set()
        )
        if target_employee_id is not None and target_employee_id in subordinate_ids:
            if intent in ["ATTENDANCE", "LEAVE", "EMPLOYEE"]:
                return True, None
            if intent == "SALARY":
                return False, "Access denied: You are not authorized to view another employee's salary details."
        else:
            if intent == "SALARY":
                return False, "Access denied: You are not authorized to view another employee's salary details."
            if intent == "LEAVE":
                return False, "Access denied: You are not authorized to view another employee's leave records."
            if intent == "ATTENDANCE":
                return False, "Access denied: You are not authorized to view another employee's attendance records."
            if intent == "EMPLOYEE":
                return False, "Access denied: You can only view the profiles of yourself and your direct reports."

    # Employee: cannot view other employees' profile, salary, leaves, or attendance
    if intent == "SALARY":
        return False, "Access denied: You are not authorized to view another employee's salary details."

    if intent == "LEAVE":
        return False, "Access denied: You are not authorized to view another employee's leave records."

    if intent == "ATTENDANCE":
        return False, "Access denied: You are not authorized to view another employee's attendance records."

    if intent == "EMPLOYEE":
        # Same rule as GET /employees/{id} (D-039, confirmed by the product owner): employees see only themselves
        return False, "Access denied: You can only view your own employee profile."

    return True, None


# ---------------------------------------------------------------------------
# Prompt Injection Detection (PRD Section 18)
# ---------------------------------------------------------------------------

PROMPT_INJECTION_REFUSAL = (
    "I can't help with that request. I only answer HR questions using the data "
    "your role is permitted to access, and I can't change my instructions or your permissions."
)

_INJECTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,40}\b(instruction|instructions|rules|guardrails|prompt|restrictions|policy|policies|permissions?)\b",
    r"\b(previous|prior|above|earlier|system)\b.{0,20}\b(instruction|instructions|prompt)\b.{0,20}\b(ignore|disregard|forget|override)\b",
    r"\byou are now\b",
    r"\bpretend (to be|you are)\b",
    r"\bact as (an? )?(admin|administrator|hr|super ?user|root|developer)\b",
    r"\b(give|grant|make|elevate)\b.{0,20}\b(me|my)\b.{0,20}\b(admin|administrator|hr|root|full|super ?user)\b.{0,15}\b(access|rights|role|privileges?|permissions?)\b",
    r"\b(reveal|show|print|display|repeat|leak)\b.{0,30}\b(system prompt|your prompt|your instructions|hidden instructions)\b",
    r"\b(jailbreak|developer mode|dan mode|sudo mode|god mode)\b",
    r"\b(drop|delete|truncate|alter|update)\s+table\b",
    r"\bselect\s+\*?\s*.{0,40}\bfrom\b\s+\w+",
    r";\s*--",
]
_INJECTION_REGEXES = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def detect_prompt_injection(question: str) -> bool:
    """
    True when the question tries to override instructions, escalate privileges,
    extract the system prompt, or smuggle SQL. Such requests are refused before
    any data is retrieved, regardless of the user's role.
    """
    if not question:
        return False
    return any(rx.search(question) for rx in _INJECTION_REGEXES)


def sanitize_question(question: str) -> str:
    """
    Sanitize and clamp user question length to protect against abuse.
    """
    if not question:
        return ""
    # Strip null bytes and clamp length
    cleaned = question.replace("\x00", "").strip()
    return cleaned[:1000]
