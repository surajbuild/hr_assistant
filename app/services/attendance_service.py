"""
app/services/attendance_service.py
-----------------------------------
Service layer for attendance business logic and database operations.

Contains reusable Python functions for:
- Retrieving attendance records (by employee, with existence verification)
- Creating attendance records (with existence and duplicate-date validation)
- Aggregating attendance statistics / summaries (with date filtering)
- Self-service check-in / check-out with late & overtime calculation
- Company daily attendance view and filtered record listing (scoped by role)
- Months that have data and employee rankings (overtime / late / absent) for the AI router

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be invoked by both API routers and AI/tool agents.
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import case, extract, func
from sqlalchemy.orm import Session

from app.database.models import Attendance, AttendanceStatus, Employee, EmployeeStatus


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


class CheckInError(AttendanceServiceError):
    """Raised when a check-in / check-out action is not valid in the current state."""
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
        "total_days": int(result.total_days or 0),
        "present_days": int(result.present_days or 0),
        "absent_days": int(result.absent_days or 0),
        "half_day_days": int(result.half_day_days or 0),
        "leave_days": int(result.leave_days or 0),
        "holiday_days": int(result.holiday_days or 0),
        "weekend_days": int(result.weekend_days or 0),
        "late_days": int(result.late_days or 0),
        "overtime_days": int(result.overtime_days or 0),
        "total_working_minutes": int(result.total_working_minutes or 0),
        "total_overtime_minutes": int(result.total_overtime_minutes or 0),
    }


# ---------------------------------------------------------------------------
# Periods & Rankings (used by the AI router's controlled tools)
# ---------------------------------------------------------------------------

RANKING_METRICS = ("overtime", "late", "absent")


def get_months_with_data(db: Session) -> List[Tuple[int, int]]:
    """Sorted (year, month) pairs that have at least one attendance record."""
    rows = (
        db.query(extract("year", Attendance.attendance_date), extract("month", Attendance.attendance_date))
        .distinct()
        .all()
    )
    return sorted((int(y), int(m)) for y, m in rows)


def rank_employees(
    db: Session,
    metric: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    scope_ids: Optional[Set[int]] = None,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Rank employees by an attendance metric, highest first. Employees with a zero value are left out.

    metric:
      - "overtime": total overtime minutes
      - "late":     days with late_minutes > 0 (ties broken by total late minutes)
      - "absent":   days with status 'absent'

    Returns dicts: employee_id, employee_code, employee_name, department, value, overtime_minutes,
    late_days, late_minutes, absent_days.
    """
    if metric not in RANKING_METRICS:
        raise ValueError(f"Unknown ranking metric: {metric}")
    if start_date and end_date and start_date > end_date:
        raise InvalidDateRangeError("start_date cannot be after end_date.")

    overtime = func.sum(Attendance.overtime_minutes)
    late_days = func.sum(case((Attendance.late_minutes > 0, 1), else_=0))
    late_minutes = func.sum(Attendance.late_minutes)
    absent_days = func.sum(case((Attendance.status == AttendanceStatus.ABSENT.value, 1), else_=0))

    query = (
        db.query(
            Employee.id, Employee.employee_code, Employee.name, Employee.department,
            overtime.label("overtime_minutes"),
            late_days.label("late_days"),
            late_minutes.label("late_minutes"),
            absent_days.label("absent_days"),
        )
        .join(Attendance, Attendance.employee_id == Employee.id)
    )
    if scope_ids is not None:
        query = query.filter(Employee.id.in_(scope_ids or {-1}))
    if start_date:
        query = query.filter(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.filter(Attendance.attendance_date <= end_date)

    order = {
        "overtime": [overtime.desc()],
        "late": [late_days.desc(), late_minutes.desc()],
        "absent": [absent_days.desc()],
    }[metric]
    rows = query.group_by(Employee.id).order_by(*order, Employee.name.asc()).all()

    ranked = []
    for row in rows:
        item = {
            "employee_id": row.id,
            "employee_code": row.employee_code,
            "employee_name": row.name,
            "department": row.department,
            "overtime_minutes": int(row.overtime_minutes or 0),
            "late_days": int(row.late_days or 0),
            "late_minutes": int(row.late_minutes or 0),
            "absent_days": int(row.absent_days or 0),
        }
        item["value"] = {"overtime": item["overtime_minutes"], "late": item["late_days"], "absent": item["absent_days"]}[metric]
        if item["value"] > 0:
            ranked.append(item)
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Company Attendance Rules (mirrors app/data/policies.json — see D-007)
# ---------------------------------------------------------------------------

SHIFT_START = time(9, 0)
GRACE_MINUTES = 15
LUNCH_BREAK_MINUTES = 60
STANDARD_WORKING_MINUTES = 480   # 8h of work (9:00–18:00 minus 1h lunch)
HALF_DAY_THRESHOLD_MINUTES = 240  # fewer than 4h worked → half day

# Fixed-date mandatory national holidays (app/data/policies.json → holiday_rules). Paid, non-working days.
# They recur every year. Holidays HR declares for one date live in the `holidays` table (D-034) —
# pass them as `extra_holidays` (holiday_service.get_declared_holiday_dates).
COMPANY_HOLIDAYS = {(1, 26): "Republic Day", (8, 15): "Independence Day", (10, 2): "Gandhi Jayanti"}


def is_working_day(day: date, extra_holidays: Optional[Set[date]] = None) -> bool:
    """Mon–Fri, not a national holiday and not one of `extra_holidays` (declared company holidays)."""
    return (
        day.weekday() < 5
        and (day.month, day.day) not in COMPANY_HOLIDAYS
        and not (extra_holidays and day in extra_holidays)
    )


def working_days_between(start: date, end: date, extra_holidays: Optional[Set[date]] = None) -> List[date]:
    """All working days in [start, end]."""
    days = []
    current = start
    while current <= end:
        if is_working_day(current, extra_holidays):
            days.append(current)
        current = date.fromordinal(current.toordinal() + 1)
    return days


def _minutes_between(start: time, end: time) -> int:
    return int(
        (datetime.combine(date.min, end) - datetime.combine(date.min, start)).total_seconds() // 60
    )


def calculate_late_minutes(in_time: time) -> int:
    """
    Minutes late relative to the 9:00 shift start.
    Arrivals within the 15-minute grace period count as on time (0).
    """
    late = _minutes_between(SHIFT_START, in_time)
    return late if late > GRACE_MINUTES else 0


def calculate_day_metrics(in_time: time, out_time: time) -> Dict[str, int]:
    """
    Python calculation engine for a single day (PRD §20).

    working_minutes  = (out - in) - lunch break (lunch only deducted for spans > 5h)
    overtime_minutes = working minutes beyond the 480-minute standard day
    late_minutes     = minutes after 9:00 when beyond the grace period
    """
    span = max(0, _minutes_between(in_time, out_time))
    working = span - LUNCH_BREAK_MINUTES if span > 300 else span
    working = max(0, working)
    return {
        "working_minutes": working,
        "overtime_minutes": max(0, working - STANDARD_WORKING_MINUTES),
        "late_minutes": calculate_late_minutes(in_time),
    }


# ---------------------------------------------------------------------------
# Self-service Check-in / Check-out
# ---------------------------------------------------------------------------

def check_in(db: Session, employee_id: int, now: Optional[datetime] = None) -> Attendance:
    """
    Record today's check-in for the employee.

    Raises:
        CheckInError: if a record for today already exists.
    """
    now = now or datetime.now()
    today = now.date()
    if get_attendance_by_date(db, employee_id=employee_id, attendance_date=today):
        raise CheckInError("You have already checked in today.")
    in_time = now.time().replace(microsecond=0)
    record = Attendance(
        employee_id=employee_id,
        attendance_date=today,
        in_time=in_time,
        out_time=None,
        working_minutes=0,
        status=AttendanceStatus.PRESENT.value,
        late_minutes=calculate_late_minutes(in_time),
        overtime_minutes=0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def check_out(db: Session, employee_id: int, now: Optional[datetime] = None) -> Attendance:
    """
    Record today's check-out and compute working / overtime minutes.

    Raises:
        CheckInError: if not checked in today, or already checked out.
    """
    now = now or datetime.now()
    record = get_attendance_by_date(db, employee_id=employee_id, attendance_date=now.date())
    if not record or not record.in_time:
        raise CheckInError("You have not checked in today.")
    if record.out_time:
        raise CheckInError("You have already checked out today.")
    out_time = now.time().replace(microsecond=0)
    metrics = calculate_day_metrics(record.in_time, out_time)
    record.out_time = out_time
    record.working_minutes = metrics["working_minutes"]
    record.overtime_minutes = metrics["overtime_minutes"]
    record.late_minutes = metrics["late_minutes"]
    record.status = (
        AttendanceStatus.HALF_DAY.value
        if metrics["working_minutes"] < HALF_DAY_THRESHOLD_MINUTES
        else AttendanceStatus.PRESENT.value
    )
    db.commit()
    db.refresh(record)
    return record


# ---------------------------------------------------------------------------
# Company / Team Views
# ---------------------------------------------------------------------------

def get_latest_attendance_date(db: Session) -> Optional[date]:
    """Most recent date that has any attendance record (demo data is historical)."""
    row = db.query(func.max(Attendance.attendance_date)).scalar()
    return row


def get_daily_attendance(
    db: Session,
    *,
    target_date: Optional[date] = None,
    scope_ids: Optional[Set[int]] = None,
) -> Dict[str, Any]:
    """
    Every in-scope active employee with their record for `target_date`
    (status `not_marked` when no record exists).

    When `target_date` is None, today is used if it has data, otherwise the
    latest date with attendance (is_fallback_date = True).
    """
    is_fallback = False
    if target_date is None:
        today = date.today()
        has_today = db.query(Attendance.id).filter(Attendance.attendance_date == today).first()
        if has_today:
            target_date = today
        else:
            latest = get_latest_attendance_date(db)
            target_date = latest or today
            is_fallback = latest is not None

    emp_query = db.query(Employee).filter(Employee.status == EmployeeStatus.ACTIVE.value)
    if scope_ids is not None:
        emp_query = emp_query.filter(Employee.id.in_(scope_ids or {-1}))
    employees = emp_query.order_by(Employee.name.asc()).all()

    records = {
        r.employee_id: r
        for r in db.query(Attendance).filter(Attendance.attendance_date == target_date).all()
    }

    counts = {
        "present": 0, "absent": 0, "late": 0, "half_day": 0, "leave": 0,
        "holiday": 0, "weekend": 0, "not_marked": 0, "total": len(employees),
    }
    rows = []
    for emp in employees:
        rec = records.get(emp.id)
        row_status = rec.status if rec else "not_marked"
        if row_status in counts:
            counts[row_status] += 1
        if rec and (rec.late_minutes or 0) > 0:
            counts["late"] += 1
        rows.append({
            "employee_id": emp.id,
            "employee_code": emp.employee_code,
            "name": emp.name,
            "department": emp.department,
            "designation": emp.designation,
            "status": row_status,
            "in_time": rec.in_time if rec else None,
            "out_time": rec.out_time if rec else None,
            "working_minutes": rec.working_minutes if rec else None,
            "late_minutes": rec.late_minutes if rec else 0,
            "overtime_minutes": rec.overtime_minutes if rec else 0,
        })

    return {
        "date": target_date,
        "is_fallback_date": is_fallback,
        "counts": counts,
        "rows": rows,
    }


def list_attendance_records(
    db: Session,
    *,
    scope_ids: Optional[Set[int]] = None,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
    with_total: bool = False,
) -> Any:
    """
    Filtered attendance records joined with employee name/department, newest first.
    Returns the page as a list, or {"total", "items"} when `with_total` is set (pagination).
    """
    if start_date and end_date and start_date > end_date:
        raise InvalidDateRangeError("start_date cannot be after end_date.")

    query = db.query(Attendance, Employee).join(Employee, Employee.id == Attendance.employee_id)
    if scope_ids is not None:
        query = query.filter(Attendance.employee_id.in_(scope_ids or {-1}))
    if employee_id is not None:
        query = query.filter(Attendance.employee_id == employee_id)
    if start_date:
        query = query.filter(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.filter(Attendance.attendance_date <= end_date)
    if status:
        query = query.filter(Attendance.status == status)

    total = query.count() if with_total else None
    rows = (
        query.order_by(Attendance.attendance_date.desc(), Employee.name.asc(), Attendance.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        {
            "id": att.id,
            "employee_id": emp.id,
            "employee_code": emp.employee_code,
            "employee_name": emp.name,
            "department": emp.department,
            "attendance_date": att.attendance_date,
            "in_time": att.in_time,
            "out_time": att.out_time,
            "working_minutes": att.working_minutes,
            "status": att.status,
            "late_minutes": att.late_minutes,
            "overtime_minutes": att.overtime_minutes,
        }
        for att, emp in rows
    ]
    return {"total": total, "items": items} if with_total else items
