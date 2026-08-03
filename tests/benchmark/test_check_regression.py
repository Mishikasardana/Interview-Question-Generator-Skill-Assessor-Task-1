"""
Tests for the regression gate's comparison logic -- pure logic, no real
benchmark run, no network. Confirms the "if recruiter accuracy decreases,
the change fails" gate (approved "One Recruiter Match Score" plan, section
8.6) actually fails when it should, and doesn't cry wolf when it shouldn't.
"""

from __future__ import annotations

from tests.benchmark.check_regression import (
    MAX_MAE_INCREASE,
    MAX_PASS_RATE_DROP,
    check_regression,
)

_BASELINE = {"recruiter_mean_abs_error": 10.0, "recruiter_pass_rate": 70.0}


def test_check_regression_passes_when_metrics_identical():
    regressed, _messages = check_regression(dict(_BASELINE), _BASELINE)
    assert regressed is False


def test_check_regression_passes_when_metrics_improve():
    current = {"recruiter_mean_abs_error": 8.0, "recruiter_pass_rate": 80.0}
    regressed, _messages = check_regression(current, _BASELINE)
    assert regressed is False


def test_check_regression_passes_within_tolerance():
    current = {
        "recruiter_mean_abs_error": _BASELINE["recruiter_mean_abs_error"] + MAX_MAE_INCREASE,
        "recruiter_pass_rate": _BASELINE["recruiter_pass_rate"] - MAX_PASS_RATE_DROP,
    }
    regressed, _messages = check_regression(current, _BASELINE)
    assert regressed is False


def test_check_regression_fails_when_mae_increases_beyond_tolerance():
    current = {
        "recruiter_mean_abs_error": _BASELINE["recruiter_mean_abs_error"] + MAX_MAE_INCREASE + 0.1,
        "recruiter_pass_rate": _BASELINE["recruiter_pass_rate"],
    }
    regressed, messages = check_regression(current, _BASELINE)
    assert regressed is True
    assert any("MAE increased" in m for m in messages)


def test_check_regression_fails_when_pass_rate_drops_beyond_tolerance():
    current = {
        "recruiter_mean_abs_error": _BASELINE["recruiter_mean_abs_error"],
        "recruiter_pass_rate": _BASELINE["recruiter_pass_rate"] - MAX_PASS_RATE_DROP - 0.1,
    }
    regressed, messages = check_regression(current, _BASELINE)
    assert regressed is True
    assert any("pass rate dropped" in m for m in messages)


def test_check_regression_reports_both_failures_at_once():
    current = {
        "recruiter_mean_abs_error": _BASELINE["recruiter_mean_abs_error"] + MAX_MAE_INCREASE + 5,
        "recruiter_pass_rate": _BASELINE["recruiter_pass_rate"] - MAX_PASS_RATE_DROP - 5,
    }
    regressed, messages = check_regression(current, _BASELINE)
    assert regressed is True
    assert any("MAE increased" in m for m in messages)
    assert any("pass rate dropped" in m for m in messages)
