"""
app/utils/security.py
---------------------
Password hashing and verification utilities.

Uses bcrypt (work factor = 12) via the `bcrypt` library.

Functions
---------
hash_password(password)        -> str   (bcrypt hash, safe to store in DB)
verify_password(plain, hashed) -> bool  (constant-time comparison)

Passwords are NEVER logged, returned in plain text, or stored raw.
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
