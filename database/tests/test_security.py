"""Tests for database.security — pure functions, no database needed."""

from __future__ import annotations

import pytest

from database.security import hash_password, verify_password


def test_hash_password_produces_different_hash_than_input():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_hash_password_rejects_empty_password():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_password_accepts_correct_password():
    hashed = hash_password("hunter2")
    assert verify_password("hunter2", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("hunter2")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_empty_password():
    hashed = hash_password("hunter2")
    assert verify_password("", hashed) is False


def test_verify_password_handles_malformed_hash_gracefully():
    assert verify_password("hunter2", "not-a-real-bcrypt-hash") is False


def test_hash_password_produces_unique_salts():
    # Same password hashed twice should not produce the same hash — proves
    # bcrypt's per-call salt is actually being used, not a fixed one.
    hashed_a = hash_password("hunter2")
    hashed_b = hash_password("hunter2")
    assert hashed_a != hashed_b
    assert verify_password("hunter2", hashed_a) is True
    assert verify_password("hunter2", hashed_b) is True
