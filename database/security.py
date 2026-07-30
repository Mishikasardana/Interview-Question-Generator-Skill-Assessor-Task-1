"""
Password hashing utilities.

Purpose:
    Isolate password hashing (bcrypt) behind two small functions so
    ``repositories.py`` never touches a raw password or a hashing library
    directly, and so this is the one place to change if the hashing scheme
    ever needs to be upgraded.

Design notes:
    - bcrypt has a built-in per-password salt (embedded in its output), so
      no separate salt column is needed.
    - bcrypt truncates input at 72 bytes; passwords are capped at 72
      characters before hashing so behavior is explicit rather than a
      silent bcrypt implementation detail.
"""

from __future__ import annotations

import bcrypt

_MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """
    Hash a plaintext password for storage.

    Args:
        password: Plaintext password.

    Returns:
        A bcrypt hash string, safe to store in the database.

    Raises:
        ValueError: If the password is empty.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    password_bytes = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Check a plaintext password against a stored bcrypt hash.

    Args:
        password: Plaintext password to check.
        password_hash: Previously stored hash from ``hash_password``.

    Returns:
        True if the password matches, False otherwise (including on any
        malformed-hash error — never raises for bad input, since this sits
        directly on the login path).
    """
    if not password or not password_hash:
        return False

    try:
        password_bytes = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
