"""
app/api/leaves.py
-----------------
Leave management routes.

Endpoints
---------
POST /leaves                    — Create a new leave request (status=pending).
GET /leaves/me                  — Get leave requests for the authenticated employee.
PATCH /leaves/{leave_id}/status — Approve or reject a pending leave request (HR / Manager).
"""

from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import LeaveType, User
from app.services import leave_service
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
    description="Allows HR or Managers to approve or reject a pending leave request.",
)
def update_leave_status(
    leave_id: int,
    body: LeaveStatusUpdate,
    current_user: User = Depends(require_role("hr", "manager")),
    db: Session = Depends(get_db),
):
    """
    1. Verify current user has 'hr' or 'manager' role (enforced by dependency).
    2. Delegate state transition and persistence to leave_service.
    3. Catch domain exceptions and map to appropriate HTTP status codes.
    """
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
