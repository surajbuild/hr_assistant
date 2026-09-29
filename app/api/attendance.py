"""
app/api/attendance.py
---------------------
Attendance management routes.

Endpoints
---------
GET /attendance/me             — Get attendance records for the authenticated employee.
POST /attendance               — Create a new attendance record (HR / Admin).
GET /attendance/summary        — Get aggregated attendance summary for the authenticated employee.
GET /attendance/{employee_id}  — Get attendance records for a specific employee (HR / Admin).
"""

from datetime import date, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import AttendanceStatus, User
from app.services import attendance_service
from app.services.attendance_service import (
    DuplicateAttendanceError,
    EmployeeNotFoundError,
    InvalidDateRangeError,
)
from app.utils.dependencies import get_current_user, require_role

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
    """
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate calculation and aggregation to attendance_service.
    3. Return structured summary response.
    """
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
