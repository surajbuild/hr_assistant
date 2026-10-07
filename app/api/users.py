"""
app/api/users.py
----------------
User (login account) administration routes — Admin only.

Endpoints
---------
GET   /users            — List login accounts with linked employee info (optional limit/offset, X-Total-Count).
PATCH /users/{user_id}  — Change a user's role and/or status.
                          Admins cannot change their own role or deactivate themselves.
"""

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.services import user_service
from app.utils.dependencies import require_role
from app.utils.pagination import set_total_count

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


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List Users",
)
def list_users(
    response: Response,
    limit: Optional[int] = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users, total = user_service.list_users(db, limit=limit, offset=offset)
    set_total_count(response, total)
    return [user_service.serialize_user(u) for u in users]


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
    try:
        user = user_service.update_user(db, current_user, user_id, role=payload.role, status=payload.status)
    except user_service.UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except user_service.SelfModificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return user_service.serialize_user(user)
