"""
Best-effort persistence wrapper.

Purpose:
    The AI/business logic in this platform (resume parsing, JD parsing,
    matching, question generation, answer evaluation) should keep working
    even when PostgreSQL isn't configured or is temporarily unreachable —
    persistence is valuable for history/reporting, but it is not a hard
    dependency for the core product experience.

    ``safe_call`` makes every repository call "best effort": on any
    database-related failure it logs and returns ``None`` instead of
    raising, so callers (the Streamlit app) can check for ``None`` and show
    a small "not saved — database not configured" notice rather than
    crashing the whole page.

Example usage:
    >>> from database.safe import safe_call
    >>> from database.repositories import save_resume
    >>> resume = safe_call(save_resume, user_id=user.id, ...)
    >>> if resume is None:
    ...     print("Not persisted — database unavailable.")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import SQLAlchemyError

from database.connection import DatabaseNotConfigured

logger = logging.getLogger("iip.database")

T = TypeVar("T")


def safe_call(func: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
    """
    Call a repository function, returning ``None`` instead of raising on any
    database-related failure.

    Args:
        func: A function from ``database.repositories`` (or any callable
            that touches the database).
        *args, **kwargs: Forwarded to ``func``.

    Returns:
        Whatever ``func`` returns, or ``None`` if the database is not
        configured or the call fails.
    """
    try:
        return func(*args, **kwargs)
    except DatabaseNotConfigured:
        logger.info(
            "Database not configured — skipping persistence for %s.",
            getattr(func, "__name__", repr(func)),
        )
        return None
    except SQLAlchemyError as exc:
        logger.warning(
            "Database error in %s: %s", getattr(func, "__name__", repr(func)), exc
        )
        return None
