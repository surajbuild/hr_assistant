"""
app/api/salary.py
-----------------
Salary management routes.

Endpoints
---------
GET /salary/me             — Get salary records for the authenticated employee.
GET /salary/summary        — Get aggregated salary summary statistics (HR / Admin).
GET /salary/{employee_id}  — Get salary records for a specific employee (HR / Admin).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import salary_service
from app.services.salary_service import EmployeeNotFoundError, InvalidSalaryFilterError
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/salary", tags=["Salary"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SalaryResponse(BaseModel):
    """Schema for returning a salary record."""
    id: int
    employee_id: int
    month: int
    year: int
    gross_salary: float
    pf: float
    deductions: float
    overtime_amount: float
    net_salary: float
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SalarySummaryResponse(BaseModel):
    """Schema for returning aggregated salary summary statistics."""
    month: Optional[int] = None
    year: Optional[int] = None
    total_records: int = 0
    total_employees: int = 0
    record_count: int = 0
    employee_count: int = 0
    total_gross_salary: float = 0.0
    total_pf: float = 0.0
    total_deductions: float = 0.0
    total_overtime_amount: float = 0.0
    total_net_salary: float = 0.0


# ---------------------------------------------------------------------------
# GET /salary/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=List[SalaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get My Salary",
    description="Returns all salary records for the authenticated employee.",
)
def get_my_salary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate retrieval to salary_service.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    return salary_service.get_my_salary(
        db,
        employee_id=current_user.employee.id,
    )


# ---------------------------------------------------------------------------
# GET /salary/summary
# ---------------------------------------------------------------------------

@router.get(
    "/summary",
    response_model=SalarySummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Salary Summary",
    description="Allows HR or Admin to retrieve aggregated salary statistics with optional month and year filtering.",
)
def get_salary_summary(
    month: Optional[int] = Query(None, description="Month (1-12) to filter by"),
    year: Optional[int] = Query(None, description="Year to filter by"),
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role (enforced by dependency).
    2. Delegate calculation and aggregation to salary_service.
    3. Catch domain exceptions (e.g. InvalidSalaryFilterError) and return 400.
    4. Return structured summary response.
    """
    try:
        summary_data = salary_service.get_salary_summary(
            db,
            month=month,
            year=year,
        )
        return SalarySummaryResponse(**summary_data)
    except InvalidSalaryFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /salary/{employee_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{employee_id}",
    response_model=List[SalaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Employee Salary",
    description="Allows HR or Admin to fetch salary records for a specific employee.",
)
def get_employee_salary(
    employee_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role (enforced by dependency).
    2. Delegate employee lookup and salary retrieval to salary_service.
    3. Return list of salary records or 404 if employee does not exist.
    """
    try:
        return salary_service.get_salary_for_employee(
            db,
            employee_id=employee_id,
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
