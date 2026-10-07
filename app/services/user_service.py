"""
app/services/user_service.py
----------------------------
Business logic for login-account administration (Admin only, enforced by the router).

Functions
---------
list_users(db, limit, offset)       — accounts with linked employee info + total count.
update_user(db, actor, user_id, …)  — change role and/or status; an admin cannot change their own role
                                      or deactivate themselves.
serialize_user(user)                — dict for the API schema.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.database.models import User


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class UserNotFoundError(Exception):
    """Raised when a user id does not exist."""


class SelfModificationError(Exception):
    """Raised when an admin tries to change their own role or deactivate their own account."""


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def serialize_user(user: User) -> Dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Queries / commands
# ---------------------------------------------------------------------------

def list_users(
    db: Session, *, limit: Optional[int] = None, offset: int = 0
) -> Tuple[List[User], int]:
    """Return (page of users ordered by id, total number of users)."""
    query = db.query(User).order_by(User.id.asc())
    total = query.count()
    query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return query.all(), total


def update_user(
    db: Session,
    actor: User,
    user_id: int,
    *,
    role: Optional[str] = None,
    status: Optional[str] = None,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError("User not found.")
    if user.id == actor.id and ((role and role != user.role) or status == "inactive"):
        raise SelfModificationError("You cannot change your own role or deactivate your own account.")
    if role:
        user.role = role
    if status:
        user.status = status
    db.commit()
    db.refresh(user)
    return user
