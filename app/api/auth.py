"""
app/api/auth.py
---------------
Authentication routes.

Endpoints
---------
POST /auth/login   — email + password → JWT access token
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import UserStatus
from app.database.queries import get_user_by_email
from app.utils.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Credentials submitted by the client."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Successful login response."""
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Shared rejection helper — intentionally vague to prevent user enumeration
# ---------------------------------------------------------------------------

def _reject_credentials() -> None:
    """Raise 401 with a generic message that reveals no account details."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Email / password login",
    description=(
        "Authenticate with email and password. "
        "Returns a Bearer JWT access token on success."
    ),
)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Login flow
    ----------
    1. Look up the user by email.
    2. Verify the password against the stored bcrypt hash.
    3. Confirm the account is active.
    4. Issue a signed JWT access token.
    """
    # Step 1 — find the user
    user = get_user_by_email(db, body.email)
    if not user:
        _reject_credentials()

    # Step 2 — verify password (also guards OAuth-only accounts that have no hash)
    if not verify_password(body.password, user.password_hash or ""):
        _reject_credentials()

    # Step 3 — account must be active
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please contact HR.",
        )

    # Step 4 — issue token
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")
