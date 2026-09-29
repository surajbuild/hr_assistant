"""
app/services/attendance_service.py
-----------------------------------
Service layer for attendance business logic and database operations.

Contains reusable Python functions for:
- Retrieving attendance records (by employee, with existence verification)
- Creating attendance records (with existence and duplicate-date validation)
- Aggregating attendance statistics / summaries (with date filtering)

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be invoked by both API routers and AI/tool agents.
"""

from datetime import date, time
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.models import Attendance, AttendanceStatus, Employee


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class AttendanceServiceError(Exception):
    """Base exception for attendance service errors."""
    pass


class EmployeeNotFoundError(AttendanceServiceError):
    """Raised when an operation targets an employee that does not exist."""
    pass


class DuplicateAttendanceError(AttendanceServiceError):
    """Raised when attempting to create a duplicate attendance entry for the same employee and date."""
    pass


class InvalidDateRangeError(AttendanceServiceError):
    """Raised when start_date is later than end_date."""
    pass


# ---------------------------------------------------------------------------
# Queries / Retrieval
# ---------------------------------------------------------------------------

def get_attendance_by_employee_id(
    db: Session,
    employee_id: int,
) -> List[Attendance]:
    """
    Retrieve all attendance records for a given employee ID.

    Returns an empty list if no records exist.
    """
    return db.query(Attendance).filter(Attendance.employee_id == employee_id).all()


def get_my_attendance(
    db: Session,
    employee_id: int,
) -> List[Attendance]:
    """
    Retrieve attendance records for the authenticated employee.

    Convenience wrapper around get_attendance_by_employee_id.
    """
    return get_attendance_by_employee_id(db, employee_id=employee_id)


def get_attendance_for_employee(
    db: Session,
    employee_id: int,
) -> List[Attendance]:
    """
    Retrieve attendance records for a specific employee ID.

    Validates that the target employee exists in the database.

    Raises:
        EmployeeNotFoundError: If the employee ID is not found.

    Returns:
        List[Attendance]: The employee's attendance records.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")

    return get_attendance_by_employee_id(db, employee_id=employee_id)


def get_attendance_by_date(
    db: Session,
    employee_id: int,
    attendance_date: date,
) -> Optional[Attendance]:
    """
    Retrieve an attendance record for a specific employee on a specific date.

    Returns None if no matching record is found.
    """
    return db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.attendance_date == attendance_date,
    ).first()


# ---------------------------------------------------------------------------
# Creation / Modification
# ---------------------------------------------------------------------------

def create_attendance(
    db: Session,
    *,
    employee_id: int,
    attendance_date: date,
    status: str,
    in_time: Optional[time] = None,
    out_time: Optional[time] = None,
    working_minutes: int = 0,
    late_minutes: int = 0,
    overtime_minutes: int = 0,
) -> Attendance:
    """
    Create and persist a new attendance record.

    Validates:
      1. Employee exists.
      2. No record already exists for (employee_id, attendance_date).

    Raises:
        EmployeeNotFoundError: If employee does not exist.
        DuplicateAttendanceError: If an attendance record already exists for the date.

    Returns:
        Attendance: The newly persisted attendance record.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")

    existing_record = get_attendance_by_date(
        db,
        employee_id=employee_id,
        attendance_date=attendance_date,
    )
    if existing_record:
        raise DuplicateAttendanceError(
            f"Attendance record already exists for employee ID {employee_id} on {attendance_date}."
        )

    attendance_record = Attendance(
        employee_id=employee_id,
        attendance_date=attendance_date,
        in_time=in_time,
        out_time=out_time,
        working_minutes=working_minutes,
        status=status,
        late_minutes=late_minutes,
        overtime_minutes=overtime_minutes,
    )

    db.add(attendance_record)
    db.commit()
    db.refresh(attendance_record)
    return attendance_record


# ---------------------------------------------------------------------------
# Aggregation & Summary Calculations
# ---------------------------------------------------------------------------

def get_attendance_summary(
    db: Session,
    employee_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Calculate aggregated attendance statistics for an employee.

    Computes:
      - total_days: Count of recorded attendance days
      - present_days: Days where status == 'present'
      - absent_days: Days where status == 'absent'
      - half_day_days: Days where status == 'half_day'
      - leave_days: Days where status == 'leave'
      - holiday_days: Days where status == 'holiday'
      - weekend_days: Days where status == 'weekend'
      - late_days: Days where late_minutes > 0
      - overtime_days: Days where overtime_minutes > 0
      - total_working_minutes: Sum of working_minutes
      - total_overtime_minutes: Sum of overtime_minutes

    Optional date filtering by start_date and end_date.

    Raises:
        InvalidDateRangeError: If start_date > end_date.

    Returns:
        Dict[str, Any]: Aggregated summary metrics.
    """
    if start_date and end_date and start_date > end_date:
        raise InvalidDateRangeError("start_date cannot be after end_date.")

    query = db.query(
        func.count(Attendance.id).label("total_days"),
        func.sum(case((Attendance.status == AttendanceStatus.PRESENT.value, 1), else_=0)).label("present_days"),
        func.sum(case((Attendance.status == AttendanceStatus.ABSENT.value, 1), else_=0)).label("absent_days"),
        func.sum(case((Attendance.status == AttendanceStatus.HALF_DAY.value, 1), else_=0)).label("half_day_days"),
        func.sum(case((Attendance.status == AttendanceStatus.LEAVE.value, 1), else_=0)).label("leave_days"),
        func.sum(case((Attendance.status == AttendanceStatus.HOLIDAY.value, 1), else_=0)).label("holiday_days"),
        func.sum(case((Attendance.status == AttendanceStatus.WEEKEND.value, 1), else_=0)).label("weekend_days"),
        func.sum(case((Attendance.late_minutes > 0, 1), else_=0)).label("late_days"),
        func.sum(case((Attendance.overtime_minutes > 0, 1), else_=0)).label("overtime_days"),
        func.sum(Attendance.working_minutes).label("total_working_minutes"),
        func.sum(Attendance.overtime_minutes).label("total_overtime_minutes"),
    ).filter(Attendance.employee_id == employee_id)

    if start_date:
        query = query.filter(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.filter(Attendance.attendance_date <= end_date)

    result = query.one()

    return {
        "total_days": result.total_days or 0,
        "present_days": result.present_days or 0,
        "absent_days": result.absent_days or 0,
        "half_day_days": result.half_day_days or 0,
        "leave_days": result.leave_days or 0,
        "holiday_days": result.holiday_days or 0,
        "weekend_days": result.weekend_days or 0,
        "late_days": result.late_days or 0,
        "overtime_days": result.overtime_days or 0,
        "total_working_minutes": result.total_working_minutes or 0,
        "total_overtime_minutes": result.total_overtime_minutes or 0,
    }
