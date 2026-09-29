"""
app/api/salary.py
---------------------
Salary management routes.

Endpoints
---------
GET /salary/me             — Get salary records for the authenticated employee.
GET /salary/{employee_id}  — Get salary records for a specific employee.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Employee, Salary, User
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
    2. Query Salary table for records belonging to this employee.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    records = db.query(Salary).filter(Salary.employee_id == current_user.employee.id).all()
    return records


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
    1. Verify current user has 'hr' or 'admin' role.
    2. Check if the specified employee exists.
    3. Query and return all salary records for this employee.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    records = db.query(Salary).filter(Salary.employee_id == employee_id).all()
    return records
