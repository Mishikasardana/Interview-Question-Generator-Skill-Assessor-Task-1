"""PostgreSQL connection and session helpers."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base

load_dotenv()


class DatabaseNotConfigured(RuntimeError):
    """Raised when DATABASE_URL is missing."""


def get_database_url() -> str:
    """Return the PostgreSQL DATABASE_URL from the environment."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise DatabaseNotConfigured(
            "DATABASE_URL is not set. Add your PostgreSQL URL to .env."
        )
    return database_url


@lru_cache
def get_engine():
    """Create and cache the SQLAlchemy engine."""
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """
    Create and cache the session factory.

    ``expire_on_commit=False`` is why repository functions (see
    ``database/repositories.py``) can return an ORM object after their
    ``with get_session() as session:`` block has already closed the
    session, and callers can still read its plain columns (``user.name``,
    ``user.email``, etc.) safely.

    It does NOT cover relationships (``User.resumes``, ``Resume.user``,
    ``QuestionSet.questions``, ...) — those are lazy-loaded by default, so
    touching one for the first time *after* the session has closed raises
    ``sqlalchemy.orm.exc.DetachedInstanceError``. Nothing in this codebase
    does that today (every relationship access happens inside an open
    session — see ``list_recent_reports``/``get_report_detail`` in
    repositories.py for the pattern), but new code reaching into a
    relationship on an object returned from a repository function must
    either do so inside its own ``with get_session()`` block, or add a
    dedicated repository function that eager-loads what it needs
    (``selectinload``/``joinedload``) rather than relying on lazy loading.
    """
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def _ensure_user_oauth_columns() -> None:
    """
    Idempotently retrofit `users` for Google OAuth on a database that was
    already provisioned before this column existed — create_all() only
    creates missing TABLES, it never alters an existing table's columns.
    Every statement here is safe to re-run (already-nullable / IF NOT
    EXISTS), so this is not a migration framework, just idempotent DDL for
    this one schema change.
    """
    with get_engine().begin() as conn:
        conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)"))
        conn.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id)")
        )


def _ensure_user_email_auth_columns() -> None:
    """
    Idempotently retrofit `users` for email/password auth (verification +
    last-login tracking) on a database that was already provisioned before
    these columns existed. Same rationale as `_ensure_user_oauth_columns`.

    Backfills is_verified=TRUE for any row that already has a google_id —
    a Google-authenticated account's email was already verified by Google,
    so it should never show the "please verify your email" reminder.
    """
    with get_engine().begin() as conn:
        conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE")
        )
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ"))
        conn.execute(
            text("UPDATE users SET is_verified = TRUE WHERE google_id IS NOT NULL AND is_verified = FALSE")
        )


def init_db() -> None:
    """Create all database tables declared in database.models."""
    Base.metadata.create_all(bind=get_engine())
    _ensure_user_oauth_columns()
    _ensure_user_email_auth_columns()


def get_session() -> Session:
    """Return a new SQLAlchemy session."""
    return get_session_factory()()
