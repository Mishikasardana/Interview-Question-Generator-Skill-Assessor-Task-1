"""Tests for rate_limiter — in-memory, so each test resets its module state."""

from __future__ import annotations

import pytest

import rate_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    rate_limiter._login_attempts.clear()
    rate_limiter._reset_attempts.clear()
    yield
    rate_limiter._login_attempts.clear()
    rate_limiter._reset_attempts.clear()


def test_login_not_blocked_under_threshold():
    email = "jane@example.com"
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS - 1):
        rate_limiter.record_failed_login(email)

    assert not rate_limiter.is_login_blocked(email)


def test_login_blocked_at_threshold():
    email = "jane@example.com"
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        rate_limiter.record_failed_login(email)

    assert rate_limiter.is_login_blocked(email)


def test_login_block_lifts_after_window_expires():
    email = "jane@example.com"
    now = 1_000_000.0
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        rate_limiter.record_failed_login(email, now=now)

    assert rate_limiter.is_login_blocked(email, now=now)

    later = now + rate_limiter.LOGIN_WINDOW_SECONDS + 1
    assert not rate_limiter.is_login_blocked(email, now=later)


def test_successful_login_clears_failed_attempt_counter():
    email = "jane@example.com"
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        rate_limiter.record_failed_login(email)
    assert rate_limiter.is_login_blocked(email)

    rate_limiter.record_successful_login(email)

    assert not rate_limiter.is_login_blocked(email)


def test_login_lockout_is_case_and_whitespace_insensitive_by_email():
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        rate_limiter.record_failed_login("Jane@Example.com")

    assert rate_limiter.is_login_blocked("  jane@example.com  ")


def test_password_reset_not_blocked_under_threshold():
    email = "jane@example.com"
    for _ in range(rate_limiter.RESET_MAX_ATTEMPTS - 1):
        rate_limiter.record_password_reset_request(email)

    assert not rate_limiter.is_password_reset_blocked(email)


def test_password_reset_blocked_at_threshold():
    email = "jane@example.com"
    for _ in range(rate_limiter.RESET_MAX_ATTEMPTS):
        rate_limiter.record_password_reset_request(email)

    assert rate_limiter.is_password_reset_blocked(email)


def test_password_reset_counter_independent_from_login_counter():
    email = "jane@example.com"
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        rate_limiter.record_failed_login(email)

    assert rate_limiter.is_login_blocked(email)
    assert not rate_limiter.is_password_reset_blocked(email)
