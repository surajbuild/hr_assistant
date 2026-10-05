"""
app/api/employees.py
--------------------
Employee-related routes.

Endpoints
---------
GET    /employees/me             — Profile of the currently authenticated user.
GET    /employees                — Employee directory with filters.
                                   HR / Admin: everyone. Manager: self + direct reports.
GET    /employees/{employee_id}  — One employee. Employee: self only. Manager: self/team.
                                   HR / Admin: anyone.
POST   /employees                — Create employee (+ optional login account). HR / Admin.
PUT    /employees/{employee_id}  — Partial update. HR / Admin.
DELETE /employees/{employee_id}  — Soft delete (status -> inactive, login disabled). HR / Admin.
"""

from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import employee_service
from app.services.employee_service import (
    EmployeeConflictError,
    EmployeeNotFoundError,
    EmployeeValidationError,
)
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/employees", tags=["Employees"])

EmployeeStatusLiteral = Literal["active", "inactive", "terminated", "on_notice"]
RoleLiteral = Literal["employee", "manager", "hr", "admin"]


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


class EmployeeDetailResponse(EmployeeResponse):
    """Directory/detail view with manager name and linked login info."""
    manager_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    # Only populated for HR/Admin viewers or the employee themself (D-021)
    monthly_gross_salary: Optional[float] = None


class EmployeeCreateRequest(BaseModel):
    """Payload for creating an employee, optionally with a login account."""
    employee_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    department: str = Field(..., min_length=1, max_length=100)
    designation: str = Field(..., min_length=1, max_length=100)
    joining_date: date
    status: EmployeeStatusLiteral = "active"
    manager_id: Optional[int] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role: RoleLiteral = "employee"
    monthly_gross_salary: Optional[float] = Field(None, ge=0, le=100_000_000)


class EmployeeUpdateRequest(BaseModel):
    """Partial update payload — only provided fields are changed."""
    employee_code: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    designation: Optional[str] = Field(None, min_length=1, max_length=100)
    joining_date: Optional[date] = None
    status: Optional[EmployeeStatusLiteral] = None
    manager_id: Optional[int] = None
    monthly_gross_salary: Optional[float] = Field(None, ge=0, le=100_000_000)


def _service_error_to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, EmployeeNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, EmployeeConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /employees/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Employee Profile",
    description="Returns the employee profile of the currently authenticated user (incl. manager name).",
)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    1. Authenticate user via JWT dependency.
    2. Delegate retrieval to employee_service.
    3. Return employee profile (own salary structure included — it is the caller's own data).
    """
    try:
        employee = employee_service.get_my_profile(current_user)
        return employee_service.serialize_employee(employee, include_salary=True)
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
    response_model=List[EmployeeDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="List Employees",
    description="Employee directory. HR/Admin see everyone; managers see themselves and their direct reports.",
)
def list_employees(
    search: Optional[str] = Query(None, max_length=100),
    department: Optional[str] = Query(None, max_length=100),
    status_filter: Optional[EmployeeStatusLiteral] = Query(None, alias="status"),
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    employees = employee_service.list_employees(
        db, scope_ids=scope, search=search, department=department, status=status_filter
    )
    show_salary = current_user.role in ("hr", "admin")
    return [employee_service.serialize_employee(e, include_salary=show_salary) for e in employees]


# ---------------------------------------------------------------------------
# GET /employees/{employee_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{employee_id}",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Employee By ID",
    description="Employees may view only themselves, managers their team, HR/Admin anyone.",
)
def get_employee_by_id(
    employee_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not employee_service.can_access_employee(db, current_user, employee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    try:
        employee = employee_service.get_employee_by_id(db, employee_id=employee_id)
    except EmployeeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return employee_service.serialize_employee(
        employee, include_salary=employee_service.can_view_salary(current_user, employee.id)
    )


# ---------------------------------------------------------------------------
# POST /employees
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Employee",
    description="Create an employee profile. Supplying email + password also creates a login account.",
)
def create_employee(
    payload: EmployeeCreateRequest,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    # Only admins may mint admin accounts
    if payload.email and payload.role == "admin" and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can create admin accounts.")
    try:
        employee = employee_service.create_employee(db, **payload.model_dump())
    except (EmployeeConflictError, EmployeeValidationError) as exc:
        raise _service_error_to_http(exc)
    return employee_service.serialize_employee(employee, include_salary=True)


# ---------------------------------------------------------------------------
# PUT /employees/{employee_id}
# ---------------------------------------------------------------------------

@router.put(
    "/{employee_id}",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Employee",
)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    changes = payload.model_dump(exclude_unset=True)
    # Only manager_id may be cleared with null; null for a NOT NULL column means "no change"
    changes = {k: v for k, v in changes.items() if v is not None or k == "manager_id"}
    try:
        employee = employee_service.update_employee(db, employee_id, changes)
    except (EmployeeNotFoundError, EmployeeConflictError, EmployeeValidationError) as exc:
        raise _service_error_to_http(exc)
    return employee_service.serialize_employee(employee, include_salary=True)


# ---------------------------------------------------------------------------
# DELETE /employees/{employee_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{employee_id}",
    response_model=EmployeeDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate Employee (soft delete)",
)
def deactivate_employee(
    employee_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    if current_user.employee_id == employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account.")
    try:
        employee = employee_service.deactivate_employee(db, employee_id)
    except EmployeeNotFoundError as exc:
        raise _service_error_to_http(exc)
    return employee_service.serialize_employee(employee)
