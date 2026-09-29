"""
app/services/leave_service.py
-----------------------------
Service layer for leave management business logic and database operations.

Contains reusable Python functions for:
- Creating leave requests (with date validation and pending status)
- Retrieving leave records (by employee, with ownership and existence verification)
- Approving or rejecting leave requests (with state-transition validation)

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be invoked by both API routers and AI/tool agents.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database.models import Employee, Leave, LeaveStatus


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class LeaveServiceError(Exception):
    """Base exception for leave service operations."""
    pass


class LeaveNotFoundError(LeaveServiceError):
    """Raised when a requested leave record cannot be found."""
    pass


class LeaveStatusError(LeaveServiceError):
    """Raised when an invalid status transition is attempted on a leave record."""
    pass


class InvalidLeaveDateError(LeaveServiceError):
    """Raised when start_date is later than end_date."""
    pass


class EmployeeNotFoundError(LeaveServiceError):
    """Raised when an operation targets an employee that does not exist."""
    pass


# ---------------------------------------------------------------------------
# Queries / Retrieval
# ---------------------------------------------------------------------------

def get_leave_by_id(
    db: Session,
    leave_id: int,
) -> Optional[Leave]:
    """
    Retrieve a single leave request by its primary key ID.

    Returns None if not found.
    """
    return db.query(Leave).filter(Leave.id == leave_id).first()


def get_leaves_by_employee_id(
    db: Session,
    employee_id: int,
) -> List[Leave]:
    """
    Retrieve all leave requests belonging to a specific employee ID.

    Returns an empty list if no records exist.
    """
    return db.query(Leave).filter(Leave.employee_id == employee_id).all()


def get_my_leaves(
    db: Session,
    employee_id: int,
) -> List[Leave]:
    """
    Retrieve all leave requests for the authenticated employee.

    Convenience wrapper around get_leaves_by_employee_id.
    """
    return get_leaves_by_employee_id(db, employee_id=employee_id)


def get_leaves_for_employee(
    db: Session,
    employee_id: int,
) -> List[Leave]:
    """
    Retrieve leave records for a specific employee ID after verifying employee exists.

    Raises:
        EmployeeNotFoundError: If the employee ID does not exist in the database.

    Returns:
        List[Leave]: List of leave records for the employee.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")

    return get_leaves_by_employee_id(db, employee_id=employee_id)


# ---------------------------------------------------------------------------
# Creation / Lifecycle
# ---------------------------------------------------------------------------

def create_leave_request(
    db: Session,
    *,
    employee_id: int,
    leave_type: str,
    from_date: date,
    to_date: date,
    reason: Optional[str] = None,
) -> Leave:
    """
    Create and persist a new leave request with 'pending' status.

    Validates:
      1. from_date must be less than or equal to to_date.
      2. employee must exist.

    Raises:
        InvalidLeaveDateError: If from_date is after to_date.
        EmployeeNotFoundError: If employee_id does not exist.

    Returns:
        Leave: The newly persisted leave request record.
    """
    if from_date > to_date:
        raise InvalidLeaveDateError("start_date cannot be after end_date")

    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")

    leave = Leave(
        employee_id=employee_id,
        leave_type=leave_type,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        status=LeaveStatus.PENDING.value,
    )

    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


# ---------------------------------------------------------------------------
# State Transitions (Approval / Rejection)
# ---------------------------------------------------------------------------

def update_leave_status(
    db: Session,
    *,
    leave_id: int,
    status: str,
    approved_by_user_id: int,
) -> Leave:
    """
    Update the status of a pending leave request (approve or reject).

    Validates:
      1. Leave record exists.
      2. Leave record is currently in 'pending' status.
      3. Target status is either 'approved' or 'rejected'.

    Raises:
        LeaveNotFoundError: If the leave request does not exist.
        LeaveStatusError: If the leave request is not pending or target status is invalid.

    Returns:
        Leave: The updated and persisted leave record.
    """
    leave = get_leave_by_id(db, leave_id)
    if not leave:
        raise LeaveNotFoundError("Leave request not found.")

    if leave.status != LeaveStatus.PENDING.value:
        raise LeaveStatusError(
            f"Cannot update leave status. Current status is '{leave.status}'."
        )

    valid_statuses = {LeaveStatus.APPROVED.value, LeaveStatus.REJECTED.value}
    if status not in valid_statuses:
        raise LeaveStatusError(
            f"Invalid target status '{status}'. Must be one of: {sorted(valid_statuses)}."
        )

    leave.status = status
    leave.approved_by = approved_by_user_id

    db.commit()
    db.refresh(leave)
    return leave
