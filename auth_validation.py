"""
Pure input-validation helpers for email/password authentication.

No DB access, no I/O — these only inspect the strings a form submitted, so
they're trivial to unit-test in isolation and safe to call before ever
touching the database.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-()]{6,19}$")
_MIN_PASSWORD_LENGTH = 8
_MAX_PASSWORD_LENGTH = 128


def is_valid_phone(phone: str) -> bool:
    """
    Practical phone-format check: optional leading +, 7-20 digits with
    common separators (spaces, hyphens, parentheses) allowed. Not a
    carrier-verified check — same spirit as is_valid_email above.
    """
    return bool(_PHONE_RE.match(phone.strip()))


def is_valid_email(email: str) -> bool:
    """
    Practical email-format check, not an exhaustive RFC 5322 parser.

    Real proof that someone owns an address comes from the verification
    link, not from a stricter regex here — this only exists to catch
    obvious typos before hitting the database.
    """
    return bool(_EMAIL_RE.match(email.strip()))


def validate_password_strength(password: str) -> list[str]:
    """
    Return a list of violated password rules ([] means it passes).

    Rules: at least 8 characters, at least one uppercase letter, one
    lowercase letter, one digit, and one special (non-alphanumeric)
    character. Also flags passwords over 128 characters as a friendly
    error rather than silently relying on hash_password's 72-byte
    bcrypt truncation.
    """
    violations = []
    if len(password) < _MIN_PASSWORD_LENGTH:
        violations.append(f"At least {_MIN_PASSWORD_LENGTH} characters")
    if len(password) > _MAX_PASSWORD_LENGTH:
        violations.append(f"No more than {_MAX_PASSWORD_LENGTH} characters")
    if not re.search(r"[a-z]", password):
        violations.append("At least one lowercase letter")
    if not re.search(r"[A-Z]", password):
        violations.append("At least one uppercase letter")
    if not re.search(r"\d", password):
        violations.append("At least one number")
    if not re.search(r"[^A-Za-z0-9]", password):
        violations.append("At least one special character")
    return violations


def passwords_match(password: str, confirm_password: str) -> bool:
    """Whether a signup/reset form's two password fields match."""
    return password == confirm_password
