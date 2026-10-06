"""
app/services/correction_service.py
----------------------------------
Attendance corrections (D-033): fixing a day's attendance after the fact.

1. Correction requests (regularization) — an employee asks to set the in/out time of one of
   their days (missed check-out, wrong punch, forgot to check in). Their manager (direct
   reports) or HR/Admin approves or rejects; approval creates/updates the attendance row with
   server-computed working / late / overtime minutes. Nobody reviews their own request.
2. Direct edit — HR/Admin change any record (not their own) without a request.

Both are refused once the employee's salary for that month is marked paid (the payroll row is
locked, D-021), so paid payroll never silently disagrees with attendance.

This module is independent of FastAPI HTTP concerns so it can be used by routers and AI tools.
"""

from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.database.models import (
    Attendance,
    AttendanceCorrection,
    AttendanceStatus,
    CorrectionStatus,
    Employee,
    Salary,
    User,
)
from app.services.attendance_service import (
    HALF_DAY_THRESHOLD_MINUTES,
    calculate_day_metrics,
    get_attendance_by_date,
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class CorrectionServiceError(Exception):
    """Base exception for attendance-correction operations."""


class CorrectionNotFoundError(CorrectionServiceError):
    """Correction request (or attendance record) does not exist / is not visible to the caller."""


class InvalidCorrectionError(CorrectionServiceError):
    """The requested values are not valid (future date, out before in, missing reason...)."""


class CorrectionConflictError(CorrectionServiceError):
    """A pending request already exists, or the request is no longer pending."""


class CorrectionLockedError(CorrectionServiceError):
    """The month's salary is already paid — attendance for it is locked."""


class SelfReviewError(CorrectionServiceError):
    """Reviewing your own request, or directly editing your own attendance (D-033)."""


class CorrectionPermissionError(CorrectionServiceError):
    """The reviewer may not act on this employee (outside the manager's team)."""


# ---------------------------------------------------------------------------
# Shared rules
# ---------------------------------------------------------------------------

WORKED_STATUSES = (AttendanceStatus.PRESENT.value, AttendanceStatus.HALF_DAY.value)


def ensure_not_paid(db: Session, employee_id: int, day: date) -> None:
    """Raise CorrectionLockedError when the salary of `employee_id` for `day`'s month is paid."""
    paid = (
        db.query(Salary.id)
        .filter(
            Salary.employee_id == employee_id,
            Salary.month == day.month,
            Salary.year == day.year,
            Salary.paid_at.isnot(None),
        )
        .first()
    )
    if paid:
        raise CorrectionLockedError(
            f"Salary for {day.strftime('%B %Y')} is already paid — attendance for that month is locked."
        )


def worked_day_values(in_time: time, out_time: time) -> Dict[str, Any]:
    """Status + minutes for a worked day, using the same rules as check-out (D-007)."""
    if out_time <= in_time:
        raise InvalidCorrectionError("Out time must be after in time.")
    metrics = calculate_day_metrics(in_time, out_time)
    status = (
        AttendanceStatus.HALF_DAY.value
        if metrics["working_minutes"] < HALF_DAY_THRESHOLD_MINUTES
        else AttendanceStatus.PRESENT.value
    )
    return {"status": status, "in_time": in_time, "out_time": out_time, **metrics}


def _apply(db: Session, employee_id: int, day: date, values: Dict[str, Any]) -> Attendance:
    """Create or update the attendance row for (employee, day)."""
    record = get_attendance_by_date(db, employee_id=employee_id, attendance_date=day)
    if record is None:
        record = Attendance(employee_id=employee_id, attendance_date=day)
        db.add(record)
    record.status = values["status"]
    record.in_time = values.get("in_time")
    record.out_time = values.get("out_time")
    record.working_minutes = values.get("working_minutes", 0)
    record.late_minutes = values.get("late_minutes", 0)
    record.overtime_minutes = values.get("overtime_minutes", 0)
    return record


# ---------------------------------------------------------------------------
# Correction requests
# ---------------------------------------------------------------------------

def create_correction(
    db: Session,
    *,
    employee_id: int,
    attendance_date: date,
    in_time: time,
    out_time: time,
    reason: str,
    today: Optional[date] = None,
) -> AttendanceCorrection:
    """
    File a correction request for the caller's own day.

    Raises:
        InvalidCorrectionError, CorrectionConflictError, CorrectionLockedError
    """
    today = today or date.today()
    reason = (reason or "").strip()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise CorrectionNotFoundError("Employee not found.")
    if attendance_date > today:
        raise InvalidCorrectionError("You cannot correct a future date.")
    if employee.joining_date and attendance_date < employee.joining_date:
        raise InvalidCorrectionError("The date is before your joining date.")
    if not reason:
        raise InvalidCorrectionError("A reason is required.")
    worked_day_values(in_time, out_time)  # validates the times
    ensure_not_paid(db, employee_id, attendance_date)

    pending = (
        db.query(AttendanceCorrection.id)
        .filter(
            AttendanceCorrection.employee_id == employee_id,
            AttendanceCorrection.attendance_date == attendance_date,
            AttendanceCorrection.status == CorrectionStatus.PENDING.value,
        )
        .first()
    )
    if pending:
        raise CorrectionConflictError("You already have a pending correction request for this date.")

    existing = get_attendance_by_date(db, employee_id=employee_id, attendance_date=attendance_date)
    correction = AttendanceCorrection(
        employee_id=employee_id,
        attendance_date=attendance_date,
        attendance_id=existing.id if existing else None,
        requested_in_time=in_time,
        requested_out_time=out_time,
        reason=reason,
        status=CorrectionStatus.PENDING.value,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return correction


def cancel_correction(db: Session, correction_id: int, employee_id: int) -> AttendanceCorrection:
    """The requester withdraws a pending request."""
    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction or correction.employee_id != employee_id:
        raise CorrectionNotFoundError("Correction request not found.")
    if correction.status != CorrectionStatus.PENDING.value:
        raise CorrectionConflictError(f"Only pending requests can be cancelled (this one is {correction.status}).")
    correction.status = CorrectionStatus.CANCELLED.value
    db.commit()
    db.refresh(correction)
    return correction


def review_correction(
    db: Session,
    correction_id: int,
    reviewer: User,
    *,
    approve: bool,
    note: Optional[str] = None,
    scope_ids: Optional[Set[int]] = None,
) -> AttendanceCorrection:
    """
    Approve (apply to attendance) or reject a pending request.
    `scope_ids` = employees the reviewer may act on (None = everyone, i.e. HR/Admin).

    Raises:
        CorrectionNotFoundError, CorrectionPermissionError, SelfReviewError,
        CorrectionConflictError, CorrectionLockedError
    """
    correction = db.query(AttendanceCorrection).filter(AttendanceCorrection.id == correction_id).first()
    if not correction:
        raise CorrectionNotFoundError("Correction request not found.")
    if reviewer.employee_id == correction.employee_id:
        raise SelfReviewError("You cannot review your own correction request.")
    if scope_ids is not None and correction.employee_id not in scope_ids:
        raise CorrectionPermissionError("You can only review requests from your own team.")
    if correction.status != CorrectionStatus.PENDING.value:
        raise CorrectionConflictError(f"This request is already {correction.status}.")

    if approve:
        ensure_not_paid(db, correction.employee_id, correction.attendance_date)
        values = worked_day_values(correction.requested_in_time, correction.requested_out_time)
        _apply(db, correction.employee_id, correction.attendance_date, values)
        correction.status = CorrectionStatus.APPROVED.value
    else:
        correction.status = CorrectionStatus.REJECTED.value
    correction.reviewed_by = reviewer.id
    correction.reviewed_at = datetime.now().replace(microsecond=0)
    correction.review_note = (note or "").strip() or None
    db.commit()
    db.refresh(correction)
    return correction


def list_corrections(
    db: Session,
    *,
    scope_ids: Optional[Set[int]] = None,
    employee_id: Optional[int] = None,
    exclude_employee_id: Optional[int] = None,
    status: Optional[str] = None,
    correction_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Correction requests with employee info and the current record of that day, newest first."""
    query = db.query(AttendanceCorrection, Employee).join(Employee, Employee.id == AttendanceCorrection.employee_id)
    if scope_ids is not None:
        query = query.filter(AttendanceCorrection.employee_id.in_(scope_ids or {-1}))
    if employee_id is not None:
        query = query.filter(AttendanceCorrection.employee_id == employee_id)
    if exclude_employee_id is not None:
        query = query.filter(AttendanceCorrection.employee_id != exclude_employee_id)
    if status:
        query = query.filter(AttendanceCorrection.status == status)
    if correction_id is not None:
        query = query.filter(AttendanceCorrection.id == correction_id)
    rows = query.order_by(AttendanceCorrection.requested_at.desc(), AttendanceCorrection.id.desc()).all()

    reviewer_ids = {c.reviewed_by for c, _ in rows if c.reviewed_by}
    reviewers = {
        u.id: (u.employee.name if u.employee else u.email)
        for u in db.query(User).filter(User.id.in_(reviewer_ids or {-1})).all()
    }
    items = []
    for c, emp in rows:
        current = get_attendance_by_date(db, employee_id=emp.id, attendance_date=c.attendance_date)
        items.append({
            "id": c.id,
            "employee_id": emp.id,
            "employee_name": emp.name,
            "employee_code": emp.employee_code,
            "department": emp.department,
            "attendance_date": c.attendance_date,
            "requested_in_time": c.requested_in_time,
            "requested_out_time": c.requested_out_time,
            "reason": c.reason,
            "status": c.status,
            "requested_at": c.requested_at,
            "reviewed_by_name": reviewers.get(c.reviewed_by),
            "reviewed_at": c.reviewed_at,
            "review_note": c.review_note,
            "current_status": current.status if current else None,
            "current_in_time": current.in_time if current else None,
            "current_out_time": current.out_time if current else None,
        })
    return items


# ---------------------------------------------------------------------------
# Direct edit (HR / Admin)
# ---------------------------------------------------------------------------

def update_attendance_record(
    db: Session,
    record_id: int,
    editor: User,
    *,
    status: str,
    in_time: Optional[time] = None,
    out_time: Optional[time] = None,
) -> Attendance:
    """
    Overwrite one attendance record. Worked days (present / half day) need in and out time and
    get their status and minutes computed (D-007); other statuses clear the times and minutes.

    Raises:
        CorrectionNotFoundError, SelfReviewError, InvalidCorrectionError, CorrectionLockedError
    """
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if not record:
        raise CorrectionNotFoundError("Attendance record not found.")
    if editor.employee_id == record.employee_id:
        raise SelfReviewError(
            "You cannot edit your own attendance. Submit a correction request for someone else to approve."
        )
    if status not in {s.value for s in AttendanceStatus}:
        raise InvalidCorrectionError(f"Unknown status '{status}'.")
    ensure_not_paid(db, record.employee_id, record.attendance_date)

    if status in WORKED_STATUSES:
        if in_time is None or out_time is None:
            raise InvalidCorrectionError("In and out time are required for a worked day.")
        values = worked_day_values(in_time, out_time)
    else:
        values = {"status": status}
    _apply(db, record.employee_id, record.attendance_date, values)
    db.commit()
    db.refresh(record)
    return record
