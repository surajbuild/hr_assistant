"""
app/api/employees.py
--------------------
Employee-related routes.

Endpoints
---------
GET /employees/me             — Return the profile of the currently authenticated user.
GET /employees                — Return a list of all employees (HR / Admin).
GET /employees/{employee_id}  — Return the profile for a specific employee (HR / Admin).
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import employee_service
from app.services.employee_service import EmployeeNotFoundError
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/employees", tags=["Employees"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EmployeeResponse(BaseModel):
    """Schema for employee profile response (excludes sensitive auth fields)."""
    id: int
    employee_code: str
    name: str
    department: str
    designation: str
    joining_date: date
    status: str
    manager_id: Optional[int] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# GET /employees/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Employee Profile",
    description="Returns the employee profile of the currently authenticated user.",
)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    1. Authenticate user via JWT dependency.
    2. Delegate retrieval to employee_service.
    3. Return employee profile.
    """
    try:
        return employee_service.get_my_profile(current_user)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /employees
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=List[EmployeeResponse],
    status_code=status.HTTP_200_OK,
    summary="Get All Employees",
    description="Returns a list of all employees. Accessible by HR and Admin.",
)
def get_all_employees(
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role.
    2. Delegate retrieval of all employees to employee_service.
    3. Return list of employees.
    """
    return employee_service.get_all_employees(db)


# ---------------------------------------------------------------------------
# GET /employees/{employee_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Employee By ID",
    description="Returns the employee profile for the specified employee ID. Accessible by HR and Admin.",
)
def get_employee_by_id(
    employee_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role.
    2. Delegate lookup to employee_service.
    3. Return employee profile or 404 if not found.
    """
    try:
        return employee_service.get_employee_by_id(db, employee_id=employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
