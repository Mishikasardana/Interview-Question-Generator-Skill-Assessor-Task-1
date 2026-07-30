"""Tests for jd_parsing.output_validator — no network calls required."""

from __future__ import annotations

import json

import pytest

from jd_parsing.exceptions import JDValidationError
from jd_parsing.output_validator import (
    strip_markdown_fences,
    validate_jd_json,
    validate_with_retry,
)

VALID_JD_JSON = json.dumps(
    {
        "role": "Backend Engineer",
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "responsibilities": ["Build REST APIs"],
        "experience_level": "2-4 years",
    }
)


def test_strip_markdown_fences_removes_json_fence():
    fenced = f"```json\n{VALID_JD_JSON}\n```"
    assert strip_markdown_fences(fenced) == VALID_JD_JSON


def test_strip_markdown_fences_noop_on_plain_text():
    assert strip_markdown_fences(VALID_JD_JSON) == VALID_JD_JSON


def test_validate_jd_json_valid_payload():
    parsed = validate_jd_json(VALID_JD_JSON)
    assert parsed.role == "Backend Engineer"
    assert parsed.required_skills == ["Python", "PostgreSQL"]


def test_validate_jd_json_fills_missing_fields_with_defaults():
    parsed = validate_jd_json(json.dumps({"role": "ML Engineer"}))
    assert parsed.required_skills == []
    assert parsed.experience_level == ""
    assert parsed.hard_requirements == []


def test_validate_jd_json_accepts_hard_requirements():
    payload = json.dumps({
        "role": "Backend Engineer",
        "hard_requirements": [
            {
                "type": "min_experience_years",
                "description": "3+ years of Python experience",
                "minimum_value": "3 years",
                "is_mandatory": True,
            },
            {"type": "clearance", "description": "Active Top Secret clearance"},
        ],
    })
    parsed = validate_jd_json(payload)
    assert len(parsed.hard_requirements) == 2
    assert parsed.hard_requirements[0].type == "min_experience_years"
    assert parsed.hard_requirements[0].is_mandatory is True
    # is_mandatory defaults to True when the model omits it
    assert parsed.hard_requirements[1].is_mandatory is True


def test_validate_jd_json_rejects_invalid_hard_requirement_type():
    payload = json.dumps({
        "role": "Backend Engineer",
        "hard_requirements": [{"type": "not_a_real_type", "description": "bogus"}],
    })
    with pytest.raises(JDValidationError):
        validate_jd_json(payload)


def test_validate_jd_json_rejects_empty_string():
    with pytest.raises(JDValidationError):
        validate_jd_json("")


def test_validate_jd_json_rejects_invalid_json():
    with pytest.raises(JDValidationError):
        validate_jd_json("{not valid json")


def test_validate_jd_json_rejects_non_object_root():
    with pytest.raises(JDValidationError):
        validate_jd_json(json.dumps(["role", "skills"]))


def test_validate_with_retry_succeeds_on_first_attempt():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        return VALID_JD_JSON

    parsed = validate_with_retry(fake_generate)
    assert parsed.role == "Backend Engineer"
    assert calls == [False]


def test_validate_with_retry_retries_once_then_succeeds():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        if len(calls) == 1:
            return "not json"
        return VALID_JD_JSON

    parsed = validate_with_retry(fake_generate)
    assert parsed.role == "Backend Engineer"
    assert calls == [False, True]


def test_validate_with_retry_raises_after_exhausting_attempts():
    def always_invalid(strict: bool) -> str:
        return "still not json"

    with pytest.raises(JDValidationError):
        validate_with_retry(always_invalid)
