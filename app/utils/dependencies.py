"""
app/utils/dependencies.py
--------------------------
Reusable FastAPI dependencies.

get_current_user()
    Reads the Authorization: Bearer <token> header,
    validates the JWT, fetches the user from the database,
    and returns the authenticated User ORM object.

    Inject with:  user: User = Depends(get_current_user)
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, UserStatus
from app.database.queries import get_user_by_id
from app.utils.security import InvalidTokenError, decode_access_token

# HTTPBearer handles extracting the Authorization header and
# enforcing the "Bearer <token>" format. auto_error=False lets us
# return a clean 401 rather than the default 403.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validate Bearer JWT and return the User.

    Flow
    ----
    1. Verify the Authorization header is present and scheme is "Bearer".
    2. Extract the raw token string.
    3. Call decode_access_token() to validate signature and expiry.
    4. Fetch the user row from the database by user_id in the token.
    5. Confirm the user account is still active.
    6. Return the User ORM object.

    Raises
    ------
    HTTP 401  — missing header, malformed header, invalid/expired token,
                user not found in database.
    HTTP 403  — user exists but is inactive.
    """
    # Step 1 — require the Authorization: Bearer header
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 2 — decode and validate the JWT
    try:
        token_data = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Step 3 — fetch the user from the database
    user = get_user_by_id(db, token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User belonging to this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 4 — account must still be active
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please contact HR.",
        )

    return user
