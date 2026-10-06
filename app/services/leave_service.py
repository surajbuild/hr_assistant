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

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.database.models import Employee, Leave, LeaveStatus, LeaveType
from app.services.attendance_service import is_working_day
from app.services.holiday_service import get_declared_holiday_dates

# Annual entitlements per calendar year — mirrors app/data/policies.json (leave_policy).
LEAVE_ENTITLEMENTS: Dict[str, int] = {
    LeaveType.CASUAL.value: 12,
    LeaveType.SICK.value: 10,
    LeaveType.EARNED.value: 15,
}


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


def cancel_leave(db: Session, *, leave_id: int, employee_id: int) -> Leave:
    """
    Cancel the employee's own pending leave request.

    Raises:
        LeaveNotFoundError: leave missing or not owned by the employee.
        LeaveStatusError: leave is no longer pending.
    """
    leave = get_leave_by_id(db, leave_id)
    if not leave or leave.employee_id != employee_id:
        raise LeaveNotFoundError("Leave request not found.")
    if leave.status != LeaveStatus.PENDING.value:
        raise LeaveStatusError(f"Only pending requests can be cancelled. Current status is '{leave.status}'.")
    leave.status = LeaveStatus.CANCELLED.value
    db.commit()
    db.refresh(leave)
    return leave


# ---------------------------------------------------------------------------
# Calculations (leave days & balances)
# ---------------------------------------------------------------------------

def count_leave_days(
    from_date: date,
    to_date: date,
    year: Optional[int] = None,
    holidays: Optional[Set[date]] = None,
) -> int:
    """
    Number of working days covered by a leave, optionally clipped to one calendar year.
    Weekends (D-008) and holidays — national ones always, declared company holidays when
    passed as `holidays` (holiday_service.get_declared_holiday_dates, D-034) — are not
    charged against leave balances.
    """
    start, end = from_date, to_date
    if year is not None:
        start = max(start, date(year, 1, 1))
        end = min(end, date(year, 12, 31))
    days = 0
    current = start
    while current <= end:
        if is_working_day(current, holidays):
            days += 1
        current += timedelta(days=1)
    return days


def get_leave_balance(db: Session, employee_id: int, year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Leave balance per entitled type for a calendar year.

    used      = approved working days in the year
    pending   = pending working days in the year
    remaining = entitled - used (never below 0)
    """
    year = year or date.today().year
    holidays = get_declared_holiday_dates(db, date(year, 1, 1), date(year, 12, 31))
    leaves = (
        db.query(Leave)
        .filter(
            Leave.employee_id == employee_id,
            Leave.from_date <= date(year, 12, 31),
            Leave.to_date >= date(year, 1, 1),
        )
        .all()
    )
    balance = []
    for leave_type, entitled in LEAVE_ENTITLEMENTS.items():
        used = sum(
            count_leave_days(lv.from_date, lv.to_date, year, holidays)
            for lv in leaves
            if lv.leave_type == leave_type and lv.status == LeaveStatus.APPROVED.value
        )
        pending = sum(
            count_leave_days(lv.from_date, lv.to_date, year, holidays)
            for lv in leaves
            if lv.leave_type == leave_type and lv.status == LeaveStatus.PENDING.value
        )
        balance.append({
            "leave_type": leave_type,
            "year": year,
            "entitled": entitled,
            "used": used,
            "pending": pending,
            "remaining": max(0, entitled - used),
        })
    return balance


# ---------------------------------------------------------------------------
# Company / Team listing
# ---------------------------------------------------------------------------

def list_leaves(
    db: Session,
    *,
    scope_ids: Optional[Set[int]] = None,
    status: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Leave requests joined with employee info, newest first."""
    query = db.query(Leave, Employee).join(Employee, Employee.id == Leave.employee_id)
    if scope_ids is not None:
        query = query.filter(Leave.employee_id.in_(scope_ids or {-1}))
    if status:
        query = query.filter(Leave.status == status)
    if employee_id is not None:
        query = query.filter(Leave.employee_id == employee_id)
    rows = query.order_by(Leave.applied_at.desc(), Leave.id.desc()).all()
    holidays = get_declared_holiday_dates(db)
    return [
        {
            "id": lv.id,
            "employee_id": emp.id,
            "employee_name": emp.name,
            "employee_code": emp.employee_code,
            "department": emp.department,
            "leave_type": lv.leave_type,
            "from_date": lv.from_date,
            "to_date": lv.to_date,
            "days": count_leave_days(lv.from_date, lv.to_date, holidays=holidays),
            "status": lv.status,
            "reason": lv.reason,
            "applied_at": lv.applied_at,
        }
        for lv, emp in rows
    ]
