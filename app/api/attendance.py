"""
app/api/attendance.py
---------------------
Attendance management routes.

Endpoints
---------
GET /attendance/me  — Get attendance records for the authenticated employee.
POST /attendance    — Create a new attendance record.
"""

from datetime import date, time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Attendance, AttendanceStatus, Employee, User
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
    2. Query Attendance table for records belonging to this employee.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    records = db.query(Attendance).filter(Attendance.employee_id == current_user.employee.id).all()
    return records


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
    1. Verify current user has 'hr' or 'admin' role.
    2. Check if the specified employee exists.
    3. Check if an attendance record already exists for that employee on that date.
    4. Create and persist the new attendance record.
    """
    employee = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    existing_record = db.query(Attendance).filter(
        Attendance.employee_id == body.employee_id,
        Attendance.attendance_date == body.attendance_date
    ).first()
    
    if existing_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Attendance record already exists for employee ID {body.employee_id} on {body.attendance_date}.",
        )

    attendance_record = Attendance(
        employee_id=body.employee_id,
        attendance_date=body.attendance_date,
        in_time=body.in_time,
        out_time=body.out_time,
        working_minutes=body.working_minutes,
        status=body.status.value,
        late_minutes=body.late_minutes,
        overtime_minutes=body.overtime_minutes,
    )
    
    db.add(attendance_record)
    db.commit()
    db.refresh(attendance_record)
    
    return attendance_record


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
    2. Validate date range.
    3. Perform SQLAlchemy aggregations.
    4. Return summary.
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )
        
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date cannot be after end_date.",
        )

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
    ).filter(Attendance.employee_id == current_user.employee.id)

    if start_date:
        query = query.filter(Attendance.attendance_date >= start_date)
    if end_date:
        query = query.filter(Attendance.attendance_date <= end_date)

    result = query.one()

    return AttendanceSummaryResponse(
        total_days=result.total_days or 0,
        present_days=result.present_days or 0,
        absent_days=result.absent_days or 0,
        half_day_days=result.half_day_days or 0,
        leave_days=result.leave_days or 0,
        holiday_days=result.holiday_days or 0,
        weekend_days=result.weekend_days or 0,
        late_days=result.late_days or 0,
        overtime_days=result.overtime_days or 0,
        total_working_minutes=result.total_working_minutes or 0,
        total_overtime_minutes=result.total_overtime_minutes or 0,
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
    1. Verify current user has 'hr' or 'admin' role.
    2. Check if the specified employee exists.
    3. Query and return all attendance records for this employee.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    records = db.query(Attendance).filter(Attendance.employee_id == employee_id).all()
    return records

