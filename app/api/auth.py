"""
app/api/auth.py
---------------
Authentication routes.

Endpoints
---------
POST /auth/login            — email + password → JWT access token
GET  /auth/me               — Current user + linked employee profile
GET  /auth/google/login     — Redirect user to Google OAuth authorization page
                              (?next=frontend makes the callback redirect to the SPA)
GET  /auth/google/callback  — Exchange Google code, resolve user, return JWT
                              (JSON by default; redirect to FRONTEND_URL/login#token=... when requested)
"""

import os
from datetime import date
from typing import Optional
from urllib.parse import quote

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, UserStatus
from app.database.queries import get_user_by_email
from app.services import auth_service
from app.services.auth_service import InactiveUserError, OAuthAccountConflictError
from app.utils import rate_limit
from app.utils.oauth import oauth, GOOGLE_REDIRECT_URI
from app.utils.dependencies import get_current_user
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


class GoogleAuthResponse(BaseModel):
    """Successful Google OAuth authentication response."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str


class MeEmployee(BaseModel):
    id: int
    employee_code: str
    name: str
    department: str
    designation: str
    joining_date: date
    status: str
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None


class MeResponse(BaseModel):
    """Identity of the authenticated user (used by the frontend on load)."""
    user_id: int
    email: str
    role: str
    status: str
    employee: Optional[MeEmployee] = None


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
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login flow
    ----------
    0. Rate limit: attempts per client IP, failed attempts per (IP, email) — 429 (D-031).
    1. Look up the user by email.
    2. Verify the password against the stored bcrypt hash.
    3. Confirm the account is active.
    4. Issue a signed JWT access token.
    """
    ip = rate_limit.client_ip(request)
    failure_key = f"{ip}|{body.email.lower()}"
    rate_limit.enforce(rate_limit.login_ip_limiter, ip, "login attempts")
    rate_limit.enforce(rate_limit.login_failure_limiter, failure_key, "failed login attempts", record=False)

    # Step 1 — find the user
    user = get_user_by_email(db, body.email)
    if not user:
        rate_limit.login_failure_limiter.hit(failure_key)
        _reject_credentials()

    # Step 2 — verify password (also guards OAuth-only accounts that have no hash)
    if not verify_password(body.password, user.password_hash or ""):
        rate_limit.login_failure_limiter.hit(failure_key)
        _reject_credentials()
    rate_limit.login_failure_limiter.reset(failure_key)

    # Step 3 — account must be active
    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Please contact HR.",
        )

    # Step 4 — issue token
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, token_type="bearer")


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Current user",
    description="Return the authenticated user's identity, role and linked employee profile.",
)
def me(current_user: User = Depends(get_current_user)):
    emp = current_user.employee
    employee = None
    if emp:
        employee = MeEmployee(
            id=emp.id,
            employee_code=emp.employee_code,
            name=emp.name,
            department=emp.department,
            designation=emp.designation,
            joining_date=emp.joining_date,
            status=emp.status,
            manager_id=emp.manager_id,
            manager_name=emp.manager.name if emp.manager else None,
        )
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        status=current_user.status,
        employee=employee,
    )


# ---------------------------------------------------------------------------
# GET /auth/google/login
# ---------------------------------------------------------------------------

@router.api_route(
    "/google/login",
    methods=["GET", "HEAD"],
    summary="Google OAuth login",
    description="Redirects user to Google OAuth 2.0 authorization screen.",
)
async def google_login(request: Request):
    """
    Initiate the Google OAuth/OIDC authorization-code flow.
    Authlib generates a secure state parameter and saves it to the session cookie.
    Uses explicit authorization endpoint without remote metadata discovery.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID") or oauth.google.client_id
    if client_id:
        oauth.google.client_id = client_id
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or oauth.google.client_secret
    if client_secret:
        oauth.google.client_secret = client_secret

    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or GOOGLE_REDIRECT_URI or str(request.url_for("google_callback"))
    # Remember whether the SPA wants the token handed back via redirect
    if request.query_params.get("next") == "frontend":
        request.session["oauth_next"] = "frontend"
    else:
        request.session.pop("oauth_next", None)
    return await oauth.google.authorize_redirect(request, redirect_uri)


# ---------------------------------------------------------------------------
# GET /auth/google/callback
# ---------------------------------------------------------------------------

@router.get(
    "/google/callback",
    response_model=GoogleAuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Google OAuth callback",
    description="Handles Google OAuth redirect, verifies token/claims, and issues application JWT.",
)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    """
    Google OAuth Callback Flow
    --------------------------
    1. Verify state and exchange code for Google tokens.
    2. Extract identity claims (sub, email, name).
    3. Delegate to auth_service to resolve, link, or provision local user.
    4. Issue the application's existing JWT.
    5. Return JWT token response.
    """
    # Step 1 — Exchange authorization code for tokens
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {exc.description or exc.error}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authorization error: {str(exc)}",
        )

    # Step 2 — Extract user identity claims
    userinfo = token.get("userinfo")
    if not userinfo and "id_token" in token:
        try:
            userinfo = await oauth.google.parse_id_token(request, token)
        except Exception:
            pass

    if not userinfo and "access_token" in token:
        try:
            resp = await oauth.google.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                token=token,
            )
            userinfo = resp.json()
        except Exception:
            pass

    if not userinfo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user identity from Google.",
        )

    google_id = userinfo.get("sub") or userinfo.get("id")
    email = userinfo.get("email")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete Google user profile (missing ID or email).",
        )

    # Step 3 — Resolve, link, or provision local user in the database
    try:
        user = auth_service.resolve_or_create_google_user(
            db,
            google_id=str(google_id),
            email=email,
            name=userinfo.get("name"),
        )
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except OAuthAccountConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    # Step 4 — Issue our application's standard JWT
    jwt_token = create_access_token(user_id=user.id, role=user.role)

    # Step 5 — Hand the token to the SPA if the login was started from it
    if request.session.pop("oauth_next", None) == "frontend":
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return RedirectResponse(f"{frontend_url}/login#token={quote(jwt_token)}", status_code=302)

    return GoogleAuthResponse(
        access_token=jwt_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        role=user.role,
    )
