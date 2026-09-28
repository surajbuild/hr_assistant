"""
app/api/leaves.py
-----------------
Leave management routes.

Endpoints
---------
POST /leaves  — Create a new leave request (status=pending).
"""

from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Leave, LeaveStatus, LeaveType, User
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
    2. Map start_date/end_date to from_date/to_date.
    3. Force status to PENDING.
    4. Save to database.
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    leave = Leave(
        employee_id=current_user.employee.id,
        leave_type=body.leave_type.value,
        from_date=body.start_date,
        to_date=body.end_date,
        reason=body.reason,
        status=LeaveStatus.PENDING.value,
    )

    db.add(leave)
    db.commit()
    db.refresh(leave)
    
    return leave


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
    2. Query Leave table for records belonging to this employee.
    3. Return list (empty list if none found).
    """
    if not current_user.employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found for the current user.",
        )

    leaves = db.query(Leave).filter(Leave.employee_id == current_user.employee.id).all()
    return leaves


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
    1. Verify current user has 'hr' or 'manager' role (handled by dependency).
    2. Find the leave by ID.
    3. Ensure it is currently 'pending'.
    4. Update status and approved_by.
    5. Save and return.
    """
    leave = db.query(Leave).filter(Leave.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found.",
        )
    
    if leave.status != LeaveStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update leave status. Current status is '{leave.status}'.",
        )
    
    leave.status = body.status
    leave.approved_by = current_user.id
    
    db.commit()
    db.refresh(leave)
    
    return leave
