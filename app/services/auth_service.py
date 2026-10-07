"""
app/services/auth_service.py
----------------------------
Service layer for authentication and user management operations.

Encapsulates:
- Resolving local users from Google OAuth identities
- Safe account-linking (matching email links Google identity while preserving local roles/passwords)
- Safe new user provisioning (with nullable password_hash and default employee role)
- Preventing account hijacking and duplicate accounts

This module is independent of FastAPI HTTP concerns (no Request or HTTPException)
so it can be invoked safely by routers, CLI scripts, or agent tools.
"""

import os
import uuid
from datetime import date
from typing import Optional, Set

from sqlalchemy.orm import Session

from app.database.models import Employee, EmployeeStatus, User, UserRole, UserStatus
from app.database.queries import create_employee, get_user_by_email, get_user_by_google_id


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class AuthServiceError(Exception):
    """Base exception for authentication service operations."""
    pass


class InactiveUserError(AuthServiceError):
    """Raised when an inactive user attempts to authenticate."""
    pass


class OAuthAccountConflictError(AuthServiceError):
    """Raised when an email is already linked to a different OAuth identity."""
    pass


class UnverifiedEmailError(AuthServiceError):
    """Raised when Google does not vouch for the email address (email_verified is not true)."""
    pass


class AccountNotProvisionedError(AuthServiceError):
    """Raised when a Google identity has no HRMS account and self-registration is not allowed for its domain."""
    pass


def google_provision_domains() -> Set[str]:
    """
    Email domains whose verified Google accounts may create their own employee account on first sign-in
    (env GOOGLE_ALLOWED_DOMAINS, comma-separated). Empty (the default) = invite-only: HR creates the employee
    with that email first (D-045).
    """
    raw = os.getenv("GOOGLE_ALLOWED_DOMAINS", "")
    return {d.strip().lower().lstrip("@") for d in raw.split(",") if d.strip()}


# ---------------------------------------------------------------------------
# Google OAuth User Resolution & Safe Account Linking
# ---------------------------------------------------------------------------

def resolve_or_create_google_user(
    db: Session,
    *,
    google_id: str,
    email: str,
    name: Optional[str] = None,
    email_verified: bool = False,
) -> User:
    """
    Find, link, or provision a local user from a Google OAuth identity (D-045).

    Rules & Business Logic:
    1. Match by google_id:
       - If an existing user has this google_id, authenticate them.
       - Verify the account is active; raise InactiveUserError if inactive.
       - Preserve their existing role and permissions.

    2. Match by email (Safe Account Linking) — only when Google says the email is verified, otherwise anyone
       could create a Google account carrying a colleague's (unverified) address and take over their HRMS account:
       - If an existing user matches this email:
         - If user.google_id is None -> link this google_id to the existing account.
         - If user.google_id is already set and different -> raise OAuthAccountConflictError
           to prevent accidental account hijacking.
         - Verify account is active; raise InactiveUserError if inactive.
         - Preserve their existing role and existing password hash (if any).

    3. New User Provisioning — invite-only by default:
       - Only for a verified email whose domain is in GOOGLE_ALLOWED_DOMAINS; otherwise
         AccountNotProvisionedError (HR creates the employee with that email first).
       - Provision an associated Employee profile with default status 'active'.
       - Create the User record with password_hash = NULL (Google-only user).
       - Default role is strictly 'employee' (never permit elevated roles on registration).

    Raises:
        InactiveUserError: If the resolved user account is marked inactive.
        OAuthAccountConflictError: If email is already linked to another Google identity.
        UnverifiedEmailError: If the identity is new to us and Google did not verify its email.
        AccountNotProvisionedError: If nobody has this email and self-registration is not allowed for it.

    Returns:
        User: The authenticated User ORM record.
    """
    normalized_email = email.strip().lower()

    # Rule 1 — Match by google_id
    user = get_user_by_google_id(db, google_id)
    if user:
        if user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("Your account is inactive. Please contact HR.")
        return user

    if not email_verified:
        raise UnverifiedEmailError(
            "Your Google account's email address is not verified, so it cannot be used to sign in."
        )

    # Rule 2 — Match by (verified) email
    user = get_user_by_email(db, normalized_email)
    if user:
        if user.google_id and user.google_id != google_id:
            raise OAuthAccountConflictError(
                "This email is already associated with a different Google account."
            )

        # Link Google ID to existing account if not yet linked
        if not user.google_id:
            user.google_id = google_id
            db.commit()
            db.refresh(user)

        if user.status != UserStatus.ACTIVE.value:
            raise InactiveUserError("Your account is inactive. Please contact HR.")
        return user

    # Rule 3 — Provision new employee and user (only for allow-listed domains)
    domain = normalized_email.rsplit("@", 1)[-1]
    if domain not in google_provision_domains():
        raise AccountNotProvisionedError(
            "There is no HR account for this Google account. Ask HR to add you with this email address, "
            "then sign in with Google again."
        )
    emp_code = f"EMP-GGL-{uuid.uuid4().hex[:6].upper()}"
    display_name = name.strip() if name and name.strip() else normalized_email.split("@")[0].capitalize()

    employee = create_employee(
        db,
        employee_code=emp_code,
        name=display_name,
        department="General",
        designation="Employee",
        joining_date=date.today(),
    )

    new_user = User(
        employee_id=employee.id,
        email=normalized_email,
        password_hash=None,  # Google-only account (nullable)
        google_id=google_id,
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
