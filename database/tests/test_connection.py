"""Tests for database.connection helpers."""

from __future__ import annotations

import pytest

from database.connection import DatabaseNotConfigured, get_database_url


def test_get_database_url_raises_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(DatabaseNotConfigured, match="DATABASE_URL is not set"):
        get_database_url()


def test_get_database_url_returns_stripped_value(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "  postgresql+psycopg://localhost/test  ")

    # Clear lru_cache on get_engine/get_session_factory if imported elsewhere;
    # get_database_url itself is not cached.
    assert get_database_url() == "postgresql+psycopg://localhost/test"
