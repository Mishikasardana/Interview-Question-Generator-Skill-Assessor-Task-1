"""
In-memory rate limiting for login attempts and password-reset requests.

Keyed by normalized email rather than IP (Streamlit's session context
doesn't cleanly expose a client IP, and email-keyed limiting directly
protects a specific account from credential stuffing). Streamlit runs each
browser session in its own thread within one server process, so this
module-level state is genuinely shared, mutable state across concurrent
sessions — every read-modify-write is guarded by a lock.

Known limitations (accepted, not hidden):
  - Per-process only: resets on server restart, and does not coordinate
    across multiple server replicas if this app is ever horizontally
    scaled. A shared store (Redis, a DB table) would be needed at that
    point — out of scope while this is a single-process app.
  - Keyed by email only, so it protects one targeted account from
    brute-force, but doesn't stop an attacker probing many different
    emails at a low per-email rate. Acceptable at this app's scale.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60

RESET_MAX_ATTEMPTS = 3
RESET_WINDOW_SECONDS = 60 * 60

_lock = threading.Lock()
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_reset_attempts: dict[str, deque[float]] = defaultdict(deque)


def _normalize(email: str) -> str:
    return email.strip().lower()


def _prune(bucket: deque[float], *, window_seconds: float, now: float) -> None:
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()


def is_login_blocked(email: str, *, now: float | None = None) -> bool:
    """Whether `email` has had too many failed logins within the window."""
    now = time.time() if now is None else now
    key = _normalize(email)
    with _lock:
        bucket = _login_attempts[key]
        _prune(bucket, window_seconds=LOGIN_WINDOW_SECONDS, now=now)
        return len(bucket) >= LOGIN_MAX_ATTEMPTS


def record_failed_login(email: str, *, now: float | None = None) -> None:
    """Count one failed login attempt against `email`."""
    now = time.time() if now is None else now
    key = _normalize(email)
    with _lock:
        bucket = _login_attempts[key]
        _prune(bucket, window_seconds=LOGIN_WINDOW_SECONDS, now=now)
        bucket.append(now)


def record_successful_login(email: str) -> None:
    """Clear the failed-attempt counter for `email` after a successful login."""
    key = _normalize(email)
    with _lock:
        _login_attempts.pop(key, None)


def is_password_reset_blocked(email: str, *, now: float | None = None) -> bool:
    """Whether `email` has requested too many password resets within the window."""
    now = time.time() if now is None else now
    key = _normalize(email)
    with _lock:
        bucket = _reset_attempts[key]
        _prune(bucket, window_seconds=RESET_WINDOW_SECONDS, now=now)
        return len(bucket) >= RESET_MAX_ATTEMPTS


def record_password_reset_request(email: str, *, now: float | None = None) -> None:
    """Count one password-reset request against `email`."""
    now = time.time() if now is None else now
    key = _normalize(email)
    with _lock:
        bucket = _reset_attempts[key]
        _prune(bucket, window_seconds=RESET_WINDOW_SECONDS, now=now)
        bucket.append(now)
