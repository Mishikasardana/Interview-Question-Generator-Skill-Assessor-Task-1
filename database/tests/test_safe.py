"""Tests for database.safe.safe_call — no live database connection needed."""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

from database.connection import DatabaseNotConfigured
from database.safe import safe_call


def test_safe_call_returns_function_result_on_success():
    def add(a, b):
        return a + b

    assert safe_call(add, 2, 3) == 5


def test_safe_call_returns_none_when_database_not_configured():
    def raises_not_configured():
        raise DatabaseNotConfigured("DATABASE_URL is not set.")

    assert safe_call(raises_not_configured) is None


def test_safe_call_returns_none_on_sqlalchemy_error():
    def raises_db_error():
        raise SQLAlchemyError("connection refused")

    assert safe_call(raises_db_error) is None


def test_safe_call_forwards_kwargs():
    def greet(*, name):
        return f"hello {name}"

    assert safe_call(greet, name="Mishika") == "hello Mishika"


def test_safe_call_does_not_swallow_unrelated_exceptions():
    def raises_type_error():
        raise TypeError("this is not a database error")

    try:
        safe_call(raises_type_error)
        raised = False
    except TypeError:
        raised = True

    assert raised, "safe_call should only swallow database-related errors"
