"""
app/api/attendance.py
---------------------
Attendance management routes.

Endpoints
---------
GET /attendance/me             — Get attendance records for the authenticated employee.
POST /attendance               — Create a new attendance record (HR / Admin).
GET /attendance/summary        — Get aggregated attendance summary for the authenticated employee.
GET /attendance/today         — Today's record for the authenticated employee (or null).
POST /attendance/check-in      — Self-service check-in (late after 9:15).
POST /attendance/check-out     — Self-service check-out (server computes working/OT minutes).
GET /attendance/daily          — Daily sheet for all in-scope employees (HR / Admin / Manager-team).
GET /attendance/records        — Filtered record search (HR / Admin / Manager-team), paginated (X-Total-Count).
PUT /attendance/records/{id}   — Edit one record (HR / Admin; not own record; not in a paid month) (D-033).
POST /attendance/corrections   — Request a correction of one of your own days.
GET /attendance/corrections/me — Your correction requests.
GET /attendance/corrections    — Requests to review (HR / Admin all; Manager team; own excluded).
POST /attendance/corrections/{id}/approve | /reject — Review (never your own; manager → team only).
POST /attendance/corrections/{id}/cancel           — Withdraw your pending request.
GET /attendance/{employee_id}  — Get attendance records for a specific employee (HR / Admin).
"""

from datetime import date, datetime, time
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import AttendanceStatus, CorrectionStatus, User
from app.services import attendance_service, correction_service, employee_service
from app.services.attendance_service import (
    CheckInError,
    DuplicateAttendanceError,
    EmployeeNotFoundError,
    InvalidDateRangeError,
)
from app.utils.dependencies import get_current_user, require_role
from app.utils.pagination import set_total_count

router = APIRouter(prefix="/attendance", tags=["Attendance"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AttendanceCreateRequest(BaseModel):
    """Payload for submitting an attendance record."""
    employee_id: int
    attendance_date: date
    in_time: Optional[time] = None
    out_time: Optional[time] = None
    status: AttendanceStatus
    working_minutes: int = 0
    late_minutes: int = 0
    overtime_minutes: int = 0


class AttendanceSummaryResponse(BaseModel):
    """Schema for returning aggregated attendance statistics."""
    total_days: int = 0
    present_days: int = 0
    absent_days: int = 0
    half_day_days: int = 0
    leave_days: int = 0
    holiday_days: int = 0
    weekend_days: int = 0
    late_days: int = 0
    overtime_days: int = 0
    total_working_minutes: int = 0
    total_overtime_minutes: int = 0


class AttendanceResponse(BaseModel):
    """Schema for returning an attendance record."""
    id: int
    employee_id: int
    attendance_date: date
    in_time: Optional[time] = None
    out_time: Optional[time] = None
    working_minutes: Optional[int] = None
    status: str
    late_minutes: int
    overtime_minutes: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET /attendance/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=List[AttendanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get My Attendance",
    description="Returns all attendance records for the authenticated employee.",
)
def get_my_attendance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate attendance retrieval to attendance_service.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    return attendance_service.get_my_attendance(
        db,
        employee_id=current_user.employee.id,
    )


# ---------------------------------------------------------------------------
# POST /attendance
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Attendance Record",
    description="Allows HR or Admin to create a new attendance record for an employee.",
)
def create_attendance(
    body: AttendanceCreateRequest,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role (enforced by dependency).
    2. Delegate creation, validation, and persistence to attendance_service.
    3. Catch domain exceptions and map to appropriate HTTP status codes.

    Not for your own attendance (D-033): HR/Admin use check-in/out or a correction request like everyone else.
    """
    if body.employee_id == current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create your own attendance record. Use check-in/out or request a correction.",
        )
    try:
        return attendance_service.create_attendance(
            db,
            employee_id=body.employee_id,
            attendance_date=body.attendance_date,
            in_time=body.in_time,
            out_time=body.out_time,
            status=body.status.value,
            working_minutes=body.working_minutes,
            late_minutes=body.late_minutes,
            overtime_minutes=body.overtime_minutes,
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except DuplicateAttendanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /attendance/summary
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=AttendanceSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get My Attendance Summary",
    description="Returns aggregated attendance statistics for the authenticated employee.",
)
def get_my_attendance_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate calculation and aggregation to attendance_service.
    3. Return structured summary response.

    `from_date` / `to_date` are accepted as aliases of `start_date` / `end_date`.
    """
    start_date = start_date or from_date
    end_date = end_date or to_date
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    try:
        summary_data = attendance_service.get_attendance_summary(
            db,
            employee_id=current_user.employee.id,
            start_date=start_date,
            end_date=end_date,
        )
        return AttendanceSummaryResponse(**summary_data)
    except InvalidDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /attendance/today, POST /attendance/check-in, POST /attendance/check-out
# ---------------------------------------------------------------------------

def _require_employee(current_user: User) -> int:
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )
    return current_user.employee.id


@router.get(
    "/today",
    response_model=Optional[AttendanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get My Attendance For Today",
    description="Returns today's attendance record for the authenticated employee, or null.",
)
def get_my_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    return attendance_service.get_attendance_by_date(
        db, employee_id=employee_id, attendance_date=date.today()
    )


@router.post(
    "/check-in",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Check In",
    description="Self-service check-in. Arrivals after 9:15 are recorded as late.",
)
def check_in(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    try:
        return attendance_service.check_in(db, employee_id)
    except CheckInError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/check-out",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Check Out",
    description="Self-service check-out. Working and overtime minutes are calculated by the server.",
)
def check_out(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    try:
        return attendance_service.check_out(db, employee_id)
    except CheckInError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /attendance/daily, GET /attendance/records  (HR / Admin / Manager-team)
# ---------------------------------------------------------------------------

class DailyAttendanceRow(BaseModel):
    employee_id: int
    employee_code: str
    name: str
    department: str
    designation: str
    status: str
    in_time: Optional[time] = None
    out_time: Optional[time] = None
    working_minutes: Optional[int] = None
    late_minutes: int = 0
    overtime_minutes: int = 0


class DailyAttendanceResponse(BaseModel):
    date: date
    is_fallback_date: bool
    counts: Dict[str, int]
    rows: List[DailyAttendanceRow]


class AttendanceRecordRow(BaseModel):
    id: int
    employee_id: int
    employee_code: str
    employee_name: str
    department: str
    attendance_date: date
    in_time: Optional[time] = None
    out_time: Optional[time] = None
    working_minutes: Optional[int] = None
    status: str
    late_minutes: int
    overtime_minutes: int


@router.get(
    "/daily",
    response_model=DailyAttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Daily Attendance Sheet",
    description="Attendance of every in-scope active employee for one date (default: today or latest with data).",
)
def get_daily_attendance(
    target_date: Optional[date] = Query(None, alias="date"),
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    return attendance_service.get_daily_attendance(db, target_date=target_date, scope_ids=scope)


@router.get(
    "/records",
    response_model=List[AttendanceRecordRow],
    status_code=status.HTTP_200_OK,
    summary="Search Attendance Records",
    description=(
        "Filtered attendance records, newest first. Managers are limited to their team. "
        "Paginated with `limit` / `offset`; the total is returned in the `X-Total-Count` header."
    ),
)
def list_attendance_records(
    response: Response,
    employee_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status_filter: Optional[AttendanceStatus] = Query(None, alias="status"),
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    if employee_id is not None and scope is not None and employee_id not in scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    try:
        page = attendance_service.list_attendance_records(
            db,
            scope_ids=scope,
            employee_id=employee_id,
            start_date=from_date,
            end_date=to_date,
            status=status_filter.value if status_filter else None,
            limit=limit,
            offset=offset,
            with_total=True,
        )
    except InvalidDateRangeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    set_total_count(response, page["total"])
    return page["items"]


# ---------------------------------------------------------------------------
# PUT /attendance/records/{record_id}  (HR / Admin direct edit, D-033)
# ---------------------------------------------------------------------------

class AttendanceUpdateRequest(BaseModel):
    status: AttendanceStatus
    in_time: Optional[time] = None
    out_time: Optional[time] = None


@router.put(
    "/records/{record_id}",
    response_model=AttendanceResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit Attendance Record",
    description=(
        "HR / Admin. Worked days (present / half day) need in and out time; status and minutes are "
        "computed by the server. Not allowed on your own record or in a month whose salary is paid."
    ),
)
def update_attendance_record(
    record_id: int,
    body: AttendanceUpdateRequest,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    try:
        return correction_service.update_attendance_record(
            db, record_id, current_user, status=body.status.value, in_time=body.in_time, out_time=body.out_time
        )
    except correction_service.CorrectionServiceError as exc:
        raise _correction_http_error(exc)


# ---------------------------------------------------------------------------
# Attendance correction requests (D-033)
# ---------------------------------------------------------------------------

class CorrectionCreateRequest(BaseModel):
    attendance_date: date
    in_time: time
    out_time: time
    reason: str = Field(..., min_length=1, max_length=1000)


class CorrectionReviewRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)


class CorrectionItem(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    department: str
    attendance_date: date
    requested_in_time: time
    requested_out_time: time
    reason: str
    status: str
    requested_at: datetime
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    current_status: Optional[str] = None
    current_in_time: Optional[time] = None
    current_out_time: Optional[time] = None


def _correction_http_error(exc: Exception) -> HTTPException:
    codes = [
        (correction_service.CorrectionNotFoundError, status.HTTP_404_NOT_FOUND),
        (correction_service.InvalidCorrectionError, status.HTTP_422_UNPROCESSABLE_ENTITY),
        (correction_service.CorrectionConflictError, status.HTTP_409_CONFLICT),
        (correction_service.CorrectionLockedError, status.HTTP_409_CONFLICT),
        (correction_service.SelfReviewError, status.HTTP_403_FORBIDDEN),
        (correction_service.CorrectionPermissionError, status.HTTP_403_FORBIDDEN),
    ]
    for cls, code in codes:
        if isinstance(exc, cls):
            return HTTPException(status_code=code, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _one_correction(db: Session, correction_id: int) -> dict:
    return correction_service.list_corrections(db, correction_id=correction_id)[0]


@router.post(
    "/corrections",
    response_model=CorrectionItem,
    status_code=status.HTTP_201_CREATED,
    summary="Request Attendance Correction",
    description="Ask your manager / HR to set the in and out time of one of your days.",
)
def create_correction(
    body: CorrectionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    try:
        correction = correction_service.create_correction(
            db,
            employee_id=employee_id,
            attendance_date=body.attendance_date,
            in_time=body.in_time,
            out_time=body.out_time,
            reason=body.reason,
        )
    except correction_service.CorrectionServiceError as exc:
        raise _correction_http_error(exc)
    return _one_correction(db, correction.id)


@router.get(
    "/corrections/me",
    response_model=List[CorrectionItem],
    status_code=status.HTTP_200_OK,
    summary="My Correction Requests",
)
def my_corrections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    return correction_service.list_corrections(db, employee_id=employee_id)


@router.get(
    "/corrections",
    response_model=List[CorrectionItem],
    status_code=status.HTTP_200_OK,
    summary="Correction Requests To Review",
    description="HR / Admin: everyone's; Manager: direct reports'. Your own requests are not listed here.",
)
def list_corrections(
    status_filter: Optional[CorrectionStatus] = Query(None, alias="status"),
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    return correction_service.list_corrections(
        db,
        scope_ids=scope,
        exclude_employee_id=current_user.employee_id,
        status=status_filter.value if status_filter else None,
    )


def _review(correction_id: int, approve: bool, body: Optional[CorrectionReviewRequest], current_user: User, db: Session):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    try:
        correction_service.review_correction(
            db, correction_id, current_user, approve=approve, note=body.note if body else None, scope_ids=scope
        )
    except correction_service.CorrectionServiceError as exc:
        raise _correction_http_error(exc)
    return _one_correction(db, correction_id)


@router.post(
    "/corrections/{correction_id}/approve",
    response_model=CorrectionItem,
    status_code=status.HTTP_200_OK,
    summary="Approve Correction",
    description="Applies the requested times to the attendance record (manager → team only; never your own).",
)
def approve_correction(
    correction_id: int,
    body: Optional[CorrectionReviewRequest] = None,
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    return _review(correction_id, True, body, current_user, db)


@router.post(
    "/corrections/{correction_id}/reject",
    response_model=CorrectionItem,
    status_code=status.HTTP_200_OK,
    summary="Reject Correction",
)
def reject_correction(
    correction_id: int,
    body: Optional[CorrectionReviewRequest] = None,
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    return _review(correction_id, False, body, current_user, db)


@router.post(
    "/corrections/{correction_id}/cancel",
    response_model=CorrectionItem,
    status_code=status.HTTP_200_OK,
    summary="Cancel My Correction Request",
)
def cancel_correction(
    correction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee_id = _require_employee(current_user)
    try:
        correction_service.cancel_correction(db, correction_id, employee_id)
    except correction_service.CorrectionServiceError as exc:
        raise _correction_http_error(exc)
    return _one_correction(db, correction_id)


# ---------------------------------------------------------------------------
# GET /attendance/{employee_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{employee_id}",
    response_model=List[AttendanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Employee Attendance",
    description="Allows HR or Admin to fetch attendance records for a specific employee.",
)
def get_employee_attendance(
    employee_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role (enforced by dependency).
    2. Delegate employee lookup and attendance retrieval to attendance_service.
    3. Return list of attendance records or 404 if employee does not exist.
    """
    try:
        return attendance_service.get_attendance_for_employee(
            db,
            employee_id=employee_id,
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
