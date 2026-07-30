"""Tests for auth_validation — pure logic, no mocking needed."""

from __future__ import annotations

from auth_validation import (
    is_valid_email,
    passwords_match,
    validate_password_strength,
)


def test_is_valid_email_accepts_ordinary_addresses():
    assert is_valid_email("jane@example.com")
    assert is_valid_email("  jane@example.com  ")
    assert is_valid_email("jane.doe+tag@sub.example.co")


def test_is_valid_email_rejects_malformed_addresses():
    assert not is_valid_email("not-an-email")
    assert not is_valid_email("missing-domain@")
    assert not is_valid_email("@missing-local.com")
    assert not is_valid_email("has spaces@example.com")
    assert not is_valid_email("")


def test_validate_password_strength_passes_a_strong_password():
    assert validate_password_strength("StrongPass1!") == []


def test_validate_password_strength_flags_too_short():
    violations = validate_password_strength("Ab1!")
    assert any("8 characters" in v for v in violations)


def test_validate_password_strength_flags_too_long():
    violations = validate_password_strength("Aa1!" * 40)
    assert any("128 characters" in v for v in violations)


def test_validate_password_strength_flags_missing_lowercase():
    violations = validate_password_strength("STRONGPASS1!")
    assert any("lowercase" in v for v in violations)


def test_validate_password_strength_flags_missing_uppercase():
    violations = validate_password_strength("strongpass1!")
    assert any("uppercase" in v for v in violations)


def test_validate_password_strength_flags_missing_digit():
    violations = validate_password_strength("StrongPassword!")
    assert any("number" in v for v in violations)


def test_validate_password_strength_flags_missing_special_character():
    violations = validate_password_strength("StrongPass1")
    assert any("special character" in v for v in violations)


def test_passwords_match():
    assert passwords_match("secret123", "secret123")
    assert not passwords_match("secret123", "different")
