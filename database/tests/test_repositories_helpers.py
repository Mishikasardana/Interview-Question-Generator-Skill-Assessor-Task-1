"""Tests for the pure-logic helper in database.repositories (no DB needed)."""

from __future__ import annotations

from database.repositories import _optional_float


def test_optional_float_passes_through_none():
    assert _optional_float(None) is None


def test_optional_float_converts_int():
    assert _optional_float(7) == 7.0


def test_optional_float_converts_string_number():
    assert _optional_float("12.5") == 12.5
