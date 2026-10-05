"""
app/api/users.py
----------------
User (login account) administration routes — Admin only.

Endpoints
---------
GET   /users            — List all login accounts with linked employee info.
PATCH /users/{user_id}  — Change a user's role and/or status.
                          Admins cannot change their own role or deactivate themselves.
"""

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.utils.dependencies import require_role

router = APIRouter(prefix="/users", tags=["Users"])


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    status: str
    employee_id: int
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    has_password: bool
    has_google: bool
    created_at: Optional[datetime] = None


class UserUpdateRequest(BaseModel):
    role: Optional[Literal["employee", "manager", "hr", "admin"]] = None
    status: Optional[Literal["active", "inactive"]] = None


def _serialize(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "employee_id": user.employee_id,
        "employee_name": user.employee.name if user.employee else None,
        "employee_code": user.employee.employee_code if user.employee else None,
        "has_password": bool(user.password_hash),
        "has_google": bool(user.google_id),
        "created_at": user.created_at,
    }


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List Users",
)
def list_users(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    return [_serialize(u) for u in db.query(User).order_by(User.id.asc()).all()]


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Role / Status",
)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.id == current_user.id and (
        (payload.role and payload.role != user.role) or payload.status == "inactive"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role or deactivate your own account.",
        )
    if payload.role:
        user.role = payload.role
    if payload.status:
        user.status = payload.status
    db.commit()
    db.refresh(user)
    return _serialize(user)
