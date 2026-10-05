"""
app/api/reports.py
------------------
Excel Report export endpoints (PRD Section 22).

Endpoints:
- GET /reports/attendance: Export attendance report (.xlsx). Restricted to HR & Admin.
- GET /reports/overtime: Export overtime report (.xlsx). Restricted to HR & Admin.
- GET /reports/leave: Export leave report (.xlsx). Restricted to HR & Admin.

Period filters (all optional):
- `date_from` / `date_to` (YYYY-MM-DD), or
- `month` (1-12) + `year` — expanded to that calendar month (takes precedence), or
- `year` alone — the whole calendar year.
- `department` limits the report to one department.
"""

import calendar
from datetime import date
from typing import Callable, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import report_service
from app.utils.dependencies import require_role

router = APIRouter(prefix="/reports", tags=["Reports"])

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _resolve_period(
    date_from: Optional[date],
    date_to: Optional[date],
    month: Optional[int],
    year: Optional[int],
) -> Tuple[Optional[date], Optional[date], str]:
    """Return (date_from, date_to, filename_suffix)."""
    if month is not None and year is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="'year' is required with 'month'.")
    if year is not None and month is not None:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day), f"{year}_{month:02d}"
    if year is not None:
        return date(year, 1, 1), date(year, 12, 31), str(year)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from cannot be after date_to.")
    return date_from, date_to, date.today().strftime("%Y%m%d")


def _excel_response(
    generator: Callable,
    prefix: str,
    db: Session,
    date_from: Optional[date],
    date_to: Optional[date],
    month: Optional[int],
    year: Optional[int],
    department: Optional[str],
) -> StreamingResponse:
    start, end, suffix = _resolve_period(date_from, date_to, month, year)
    excel_buffer = generator(db, date_from=start, date_to=end, department=department or None)
    filename = f"{prefix}_report_{suffix}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return StreamingResponse(excel_buffer, media_type=EXCEL_MEDIA_TYPE, headers=headers)


@router.get(
    "/attendance",
    status_code=status.HTTP_200_OK,
    summary="Export Attendance Report (Excel)",
    description="Summary sheet (Present/Absent/Half Day/Late Count/Working & OT minutes per employee) + daily records. HR & Admin only.",
)
def export_attendance_report(
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    department: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    return _excel_response(
        report_service.generate_attendance_report, "attendance", db, date_from, date_to, month, year, department
    )


@router.get(
    "/overtime",
    status_code=status.HTTP_200_OK,
    summary="Export Overtime Report (Excel)",
    description="Summary sheet (OT hours + OT amount per employee) + overtime sessions. HR & Admin only.",
)
def export_overtime_report(
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    department: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    return _excel_response(
        report_service.generate_overtime_report, "overtime", db, date_from, date_to, month, year, department
    )


@router.get(
    "/leave",
    status_code=status.HTTP_200_OK,
    summary="Export Leave Report (Excel)",
    description="Employee, leave type, leave days (working days) and status for leaves overlapping the period. HR & Admin only.",
)
def export_leave_report(
    date_from: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    department: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    return _excel_response(
        report_service.generate_leave_report, "leave", db, date_from, date_to, month, year, department
    )
