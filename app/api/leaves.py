"""
app/api/leaves.py
-----------------
Leave management routes.

Endpoints
---------
POST /leaves                    — Create a new leave request (status=pending).
GET /leaves/me                  — Get leave requests for the authenticated employee.
GET /leaves/balance/me          — Leave balance per type for the authenticated employee.
GET /leaves                     — List requests (HR / Admin: all, Manager: team).
PATCH /leaves/{leave_id}/status — Approve or reject a pending leave request
                                  (HR / Admin: any, Manager: team only; never own leave).
POST /leaves/{leave_id}/cancel  — Cancel own pending request.
GET /leaves/{employee_id}       — Get leave records for a specific employee (HR / Admin).
"""

from datetime import date, datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import LeaveType, User
from app.services import employee_service, leave_service
from app.services.leave_service import (
    EmployeeNotFoundError,
    InvalidLeaveDateError,
    LeaveNotFoundError,
    LeaveStatusError,
)
from app.utils.dependencies import get_current_user, require_role

router = APIRouter(prefix="/leaves", tags=["Leaves"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LeaveCreateRequest(BaseModel):
    """Payload for submitting a leave request."""
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "LeaveCreateRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        return self


class LeaveResponse(BaseModel):
    """Schema for returning a leave record."""
    id: int
    employee_id: int
    leave_type: str
    from_date: date
    to_date: date
    status: str
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class LeaveStatusUpdate(BaseModel):
    """Payload for approving/rejecting a leave."""
    status: Literal["approved", "rejected"]


# ---------------------------------------------------------------------------
# POST /leaves
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Leave Request",
    description="Submits a new leave request for the authenticated employee.",
)
def create_leave_request(
    body: LeaveCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate leave creation to leave_service.
    3. Return persisted leave record.
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    try:
        return leave_service.create_leave_request(
            db,
            employee_id=current_user.employee.id,
            leave_type=body.leave_type.value,
            from_date=body.start_date,
            to_date=body.end_date,
            reason=body.reason,
        )
    except InvalidLeaveDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /leaves/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=List[LeaveResponse],
    status_code=status.HTTP_200_OK,
    summary="Get My Leaves",
    description="Returns all leave requests for the authenticated employee.",
)
def get_my_leaves(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has an employee record.
    2. Delegate retrieval to leave_service.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    return leave_service.get_my_leaves(
        db,
        employee_id=current_user.employee.id,
    )


# ---------------------------------------------------------------------------
# PATCH /leaves/{leave_id}/status
# ---------------------------------------------------------------------------

@router.patch(
    "/{leave_id}/status",
    response_model=LeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or Reject Leave",
    description="Allows HR, Managers, or Admins to approve or reject a pending leave request.",
)
def update_leave_status(
    leave_id: int,
    body: LeaveStatusUpdate,
    current_user: User = Depends(require_role("hr", "manager", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr', 'manager' or 'admin' role (enforced by dependency).
    2. Managers may only act on leaves of their direct reports; nobody approves their own leave.
    3. Delegate state transition and persistence to leave_service.
    4. Catch domain exceptions and map to appropriate HTTP status codes.
    """
    leave = leave_service.get_leave_by_id(db, leave_id)
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found.")
    if leave.employee_id == current_user.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot approve or reject your own leave request.",
        )
    if not employee_service.can_access_employee(db, current_user, leave.employee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only act on leave requests from your team.",
        )
    try:
        return leave_service.update_leave_status(
            db,
            leave_id=leave_id,
            status=body.status,
            approved_by_user_id=current_user.id,
        )
    except LeaveNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except LeaveStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# POST /leaves/{leave_id}/cancel
# ---------------------------------------------------------------------------

@router.post(
    "/{leave_id}/cancel",
    response_model=LeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel My Pending Leave",
)
def cancel_leave(
    leave_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found for the current user.")
    try:
        return leave_service.cancel_leave(db, leave_id=leave_id, employee_id=current_user.employee.id)
    except LeaveNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except LeaveStatusError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /leaves/balance/me
# ---------------------------------------------------------------------------

class LeaveBalanceItem(BaseModel):
    leave_type: str
    year: int
    entitled: int
    used: int
    pending: int
    remaining: int


@router.get(
    "/balance/me",
    response_model=List[LeaveBalanceItem],
    status_code=status.HTTP_200_OK,
    summary="Get My Leave Balance",
    description="Entitled / used / pending / remaining working days per leave type for a calendar year.",
)
def get_my_leave_balance(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile not found for the current user.")
    return leave_service.get_leave_balance(db, current_user.employee.id, year)


# ---------------------------------------------------------------------------
# GET /leaves  (HR / Admin: all, Manager: team)
# ---------------------------------------------------------------------------

class LeaveListItem(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    employee_code: str
    department: str
    leave_type: str
    from_date: date
    to_date: date
    days: int
    status: str
    reason: Optional[str] = None
    applied_at: Optional[datetime] = None


@router.get(
    "",
    response_model=List[LeaveListItem],
    status_code=status.HTTP_200_OK,
    summary="List Leave Requests",
    description="HR/Admin see all requests; managers see their team's requests.",
)
def list_leaves(
    status_filter: Optional[Literal["pending", "approved", "rejected", "cancelled"]] = Query(None, alias="status"),
    employee_id: Optional[int] = None,
    current_user: User = Depends(require_role("hr", "admin", "manager")),
    db: Session = Depends(get_db),
):
    scope = employee_service.get_scope_employee_ids(db, current_user)
    return leave_service.list_leaves(db, scope_ids=scope, status=status_filter, employee_id=employee_id)


# ---------------------------------------------------------------------------
# GET /leaves/{employee_id}
# ---------------------------------------------------------------------------

@router.get(
    "/{employee_id}",
    response_model=List[LeaveResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Employee Leaves",
    description="Allows HR or Admin to fetch leave records for a specific employee.",
)
def get_employee_leaves(
    employee_id: int,
    current_user: User = Depends(require_role("hr", "admin")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'admin' role (enforced by dependency).
    2. Delegate employee verification and leave retrieval to leave_service.
    3. Return list of leave records, or 404 if employee does not exist.
    """
    try:
        return leave_service.get_leaves_for_employee(
            db,
            employee_id=employee_id,
        )
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
