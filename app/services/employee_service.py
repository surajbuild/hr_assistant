"""
app/services/employee_service.py
--------------------------------
Service layer for employee profile business logic and database queries.

Contains reusable Python functions for:
- Retrieving the authenticated user's employee profile
- Retrieving all employees (for administrative/HR directory listing)
- Retrieving a specific employee by ID (with existence validation)

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be safely invoked by both API routers and AI/tool agents.
"""

from typing import List

from sqlalchemy.orm import Session

from app.database.models import Employee, User
from app.database.queries import get_all_employees as db_get_all_employees
from app.database.queries import get_employee_by_id as db_get_employee_by_id


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class EmployeeServiceError(Exception):
    """Base exception for employee service operations."""
    pass


class EmployeeNotFoundError(EmployeeServiceError):
    """Raised when an operation targets an employee that does not exist."""
    pass


# ---------------------------------------------------------------------------
# Queries / Retrieval
# ---------------------------------------------------------------------------

def get_my_profile(current_user: User) -> Employee:
    """
    Retrieve the employee profile associated with the authenticated user.

    Raises:
        EmployeeNotFoundError: If no linked employee record exists.

    Returns:
        Employee: The linked employee profile.
    """
    if not current_user.employee:
        raise EmployeeNotFoundError("Employee profile not found for the current user.")
    return current_user.employee


def get_all_employees(db: Session) -> List[Employee]:
    """
    Retrieve all employee records from the database.

    Returns:
        List[Employee]: All persisted employees.
    """
    return db_get_all_employees(db)


def get_employee_by_id(db: Session, employee_id: int) -> Employee:
    """
    Retrieve an employee record by their primary key ID.

    Validates that the employee exists.

    Raises:
        EmployeeNotFoundError: If the employee ID is not found.

    Returns:
        Employee: The employee record.
    """
    employee = db_get_employee_by_id(db, employee_id)
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")
    return employee
