"""
app/api/dashboard.py
--------------------
FastAPI endpoints for HR Dashboard analytics (PRD Section 21).

Provides:
- GET /dashboard/summary: Real-time high-level metrics, department attendance,
  overtime/late leaderboards, leave distribution and monthly attendance trend (HR / Admin).
- GET /dashboard/me: Personal overview for any role (+ team snapshot for managers).
"""

from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, UserRole
from app.services import dashboard_service
from app.utils.dependencies import get_current_user, require_role


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class KpiMetrics(BaseModel):
    total_employees: int
    present_today: int
    absent_today: int
    on_leave_today: int
    late_today: int
    total_overtime_hours: float


class DepartmentAttendanceItem(BaseModel):
    department: str
    total_employees: int
    present: int
    absent: int
    percentage: float


class OvertimeLeaderItem(BaseModel):
    name: str
    department: str
    overtime_hours: float


class LateLeaderItem(BaseModel):
    name: str
    department: str
    late_count: int
    total_late_minutes: int


class LeaveBreakdownItem(BaseModel):
    type: str
    count: int


class RecentLeaveItem(BaseModel):
    id: int
    employee_name: str
    department: str
    leave_type: str
    from_date: str
    to_date: str
    status: str
    reason: str


class MonthlyAttendanceItem(BaseModel):
    month: str
    label: str
    present: int
    absent: int
    late: int
    half_day: int
    leave: int
    attendance_rate: float


class DashboardSummaryResponse(BaseModel):
    reference_date: str
    is_fallback_date: bool
    month: str
    kpis: KpiMetrics
    department_attendance: List[DepartmentAttendanceItem]
    overtime_leaders: List[OvertimeLeaderItem]
    late_leaders: List[LateLeaderItem]
    leave_breakdown: List[LeaveBreakdownItem]
    recent_leaves: List[RecentLeaveItem]
    monthly_attendance: List[MonthlyAttendanceItem] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get HR Dashboard Summary",
    description="Retrieve company-wide attendance, leave, overtime, and department metrics for the dashboard.",
)
def get_dashboard_summary(
    ref_date: Optional[date] = Query(
        None,
        alias="date",
        description="Optional date to compute daily metrics for (YYYY-MM-DD). Defaults to today or latest record.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("hr", "admin")),
):
    """
    Returns full company-wide dashboard analytics.
    Restricted to HR and Administrators (403 for Employee and Manager).
    """
    return dashboard_service.get_dashboard_summary(db=db, ref_date=ref_date)


# ---------------------------------------------------------------------------
# GET /dashboard/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get My Dashboard",
    description="Personal overview: today's attendance, month stats, leave balance, latest payslip; managers also get a team snapshot.",
)
def get_my_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return dashboard_service.get_my_dashboard(db=db, current_user=current_user)
