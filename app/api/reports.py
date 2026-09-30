"""
app/api/reports.py
------------------
Excel Report export endpoints (PRD Section 22).

Endpoints:
- GET /reports/attendance: Export attendance report (.xlsx). Restricted to HR & Admin.
- GET /reports/overtime: Export overtime report (.xlsx). Restricted to HR & Admin.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import report_service
from app.utils.dependencies import require_role

router = APIRouter(prefix="/reports", tags=["Reports"])

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/attendance",
    status_code=status.HTTP_200_OK,
    summary="Export Attendance Report (Excel)",
    description="Generates and downloads an Excel (.xlsx) report of company attendance records. Restricted to HR and Admin.",
)
def export_attendance_report(
    date_from: Optional[date] = Query(None, description="Start date for attendance records (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date for attendance records (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    """
    Streams an in-memory .xlsx attendance report.
    Enforces HR & Admin role authorization.
    """
    excel_buffer = report_service.generate_attendance_report(
        db,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f"attendance_report_{date.today().strftime('%Y%m%d')}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }

    return StreamingResponse(
        excel_buffer,
        media_type=EXCEL_MEDIA_TYPE,
        headers=headers,
    )


@router.get(
    "/overtime",
    status_code=status.HTTP_200_OK,
    summary="Export Overtime Report (Excel)",
    description="Generates and downloads an Excel (.xlsx) report of employee overtime records. Restricted to HR and Admin.",
)
def export_overtime_report(
    date_from: Optional[date] = Query(None, description="Start date for overtime records (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="End date for overtime records (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    """
    Streams an in-memory .xlsx overtime report.
    Enforces HR & Admin role authorization.
    """
    excel_buffer = report_service.generate_overtime_report(
        db,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f"overtime_report_{date.today().strftime('%Y%m%d')}.xlsx"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Access-Control-Expose-Headers": "Content-Disposition",
    }

    return StreamingResponse(
        excel_buffer,
        media_type=EXCEL_MEDIA_TYPE,
        headers=headers,
    )
