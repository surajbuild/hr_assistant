"""
app/utils/security.py
---------------------
Security utilities for the AI HR Assistant.

Sections
--------
1. Password hashing / verification  (bcrypt, work factor 12)
2. JWT access-token creation / decoding  (PyJWT, HS256)

Environment variables required for JWT
---------------------------------------
JWT_SECRET_KEY                  — long random string, keep secret
JWT_ALGORITHM                   — signing algorithm, default HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES — token lifetime, default 60 minutes

Passwords and secrets are NEVER logged or returned in plain text.
"""

import bcrypt

# Work factor / cost factor.
# 12 is the recommended baseline (2024+).
# Increase to 13-14 on faster hardware for stricter security.
_ROUNDS: int = 12


def hash_password(password: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    Returns a UTF-8 string (e.g. '$2b$12$...') that is safe to persist
    directly in the `users.password_hash` column.

    Args:
        password: The plain-text password supplied by the user.

    Returns:
        A bcrypt hash string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=_ROUNDS)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Uses a constant-time comparison internally, making it safe
    against timing-based side-channel attacks.

    Args:
        plain_password:  The password the user just submitted.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        True  if the password matches the hash.
        False if it does not match, or if either argument is empty/None.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        # Malformed hash or other bcrypt error — treat as mismatch
        return False


# =============================================================================
# Section 2 — JWT Access Tokens
# =============================================================================

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv

load_dotenv()

# ── Configuration (read once at import time) ──────────────────────────────────
_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

if not _SECRET_KEY:
    raise EnvironmentError(
        "JWT_SECRET_KEY is not set. "
        "Add it to your .env file before starting the application."
    )


# ── Structured token payload ──────────────────────────────────────────────────

@dataclass
class TokenData:
    """Decoded, validated JWT payload returned by decode_access_token()."""
    user_id: int
    role: str
    # ISO-8601 expiry for callers that need to inspect it
    expires_at: datetime


# ── Custom exception ──────────────────────────────────────────────────────────

class InvalidTokenError(Exception):
    """
    Raised by decode_access_token() when the token is missing,
    expired, tampered with, or otherwise unacceptable.

    The message is safe to surface to the API caller.
    """


# ── Public functions ──────────────────────────────────────────────────────────

def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    The token payload contains:
      - ``sub``  : str(user_id)  — standard JWT subject claim
      - ``role`` : user's role string (e.g. "employee", "hr", "admin")
      - ``iat``  : issued-at timestamp (UTC)
      - ``exp``  : expiry timestamp (UTC)

    Args:
        user_id:       Primary key from the ``users`` table.
        role:          The user's role string.
        expires_delta: Optional custom lifetime; defaults to
                       ``JWT_ACCESS_TOKEN_EXPIRE_MINUTES`` from .env.

    Returns:
        A compact JWT string safe to return in an API response.
    """
    now = datetime.now(tz=timezone.utc)
    delta = expires_delta or timedelta(minutes=_EXPIRE_MINUTES)
    expire = now + delta

    payload = {
        "sub": str(user_id),   # subject — always a string per RFC 7519
        "role": role,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    """
    Validate and decode a JWT access token.

    Verifies:
      - Signature (using ``JWT_SECRET_KEY`` and ``JWT_ALGORITHM``)
      - Expiration (``exp`` claim)
      - Presence of required claims (``sub``, ``role``)

    Args:
        token: The raw JWT string received from the client.

    Returns:
        A :class:`TokenData` instance with ``user_id``, ``role``,
        and ``expires_at``.

    Raises:
        :class:`InvalidTokenError`: For any validation failure —
            expired, bad signature, missing claims, or malformed token.
            The message is safe to forward to the API caller.
    """
    if not token:
        raise InvalidTokenError("No token provided.")
    try:
        payload: dict = jwt.decode(
            token,
            _SECRET_KEY,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "role", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError(f"Invalid token: {exc}") from exc

    # Extract and type-check claims
    try:
        user_id = int(payload["sub"])
        role: str = payload["role"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError(f"Token payload is malformed: {exc}") from exc

    return TokenData(user_id=user_id, role=role, expires_at=expires_at)
