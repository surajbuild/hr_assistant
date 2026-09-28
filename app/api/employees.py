"""
app/api/employees.py
--------------------
Employee-related routes.

Endpoints
---------
GET /employees/me  — Return the profile of the currently authenticated user.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database.models import User
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/employees", tags=["Employees"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class EmployeeResponse(BaseModel):
    """Schema for employee profile response."""
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
    1. get_current_user extracts the JWT, decodes it, and fetches the User from DB.
    2. current_user.employee accesses the related Employee record via SQLAlchemy relationships.
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )
    return current_user.employee
