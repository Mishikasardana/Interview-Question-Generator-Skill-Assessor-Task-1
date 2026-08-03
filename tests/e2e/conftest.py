"""E2E fixtures — gating for the tests that need a real database.

Most Streamlit E2E tests drive the UI with `session_state` pre-populated
and never touch PostgreSQL. The auth flows (signup, login, password reset,
email verification) are different: they exercise `app`'s own repository
calls, which read `DATABASE_URL` and talk to a real database — there is no
mock in between, deliberately, since the point of those tests is that the
whole path works end to end.

So they're marked `needs_db` and skipped when no database is reachable,
rather than failing with a misleading "auth_user is None". CI runs them for
real: the `unit` job in .github/workflows/test.yml provisions a PostgreSQL
service and sets DATABASE_URL.
"""

from __future__ import annotations

from functools import lru_cache

import pytest
from sqlalchemy import text

from database.connection import get_session, init_db


@lru_cache(maxsize=1)
def _database_available() -> bool:
    """Whether DATABASE_URL points at a reachable, initialized database."""
    try:
        init_db()
        with get_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _skip_without_database(request: pytest.FixtureRequest) -> None:
    if request.node.get_closest_marker("needs_db") and not _database_available():
        pytest.skip("needs a reachable DATABASE_URL (see .env.example)")
