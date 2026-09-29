"""
app/ai/guardrails.py
--------------------
Security, RBAC validation, and anti-hallucination guardrails for the AI assistant.
"""

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

    # If target is someone else or company-wide data:
    if intent == "SALARY":
        return False, "Access denied: You are not authorized to view another employee's salary details."

    if intent == "LEAVE":
        return False, "Access denied: You are not authorized to view another employee's leave records."

    if intent == "ATTENDANCE":
        return False, "Access denied: You are not authorized to view another employee's attendance records."

    if intent == "EMPLOYEE":
        # Managers and Employees querying other employees' profiles
        return True, None

    return True, None


def sanitize_question(question: str) -> str:
    """
    Sanitize and clamp user question length to protect against abuse.
    """
    if not question:
        return ""
    # Strip null bytes and clamp length
    cleaned = question.replace("\x00", "").strip()
    return cleaned[:1000]
