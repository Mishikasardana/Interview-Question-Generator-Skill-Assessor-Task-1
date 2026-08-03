"""Tests for jd_parsing.parse_jd orchestration."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from jd_parsing.exceptions import JDValidationError
from jd_parsing.parse_jd import parse_jd

VALID_JD_JSON = json.dumps(
    {
        "role": "Backend Engineer",
        "required_skills": ["Python", "PostgreSQL"],
        "preferred_skills": ["Docker"],
        "responsibilities": ["Build REST APIs"],
        "experience_level": "2-4 years",
        "education_requirement": "Bachelor's degree",
    }
)


@patch("jd_parsing.parse_jd.parse_jd_text", return_value=VALID_JD_JSON)
def test_parse_jd_returns_validated_model(mock_parse: object):
    parsed = parse_jd("We are hiring a backend engineer.")

    assert parsed.role == "Backend Engineer"
    assert parsed.required_skills == ["Python", "PostgreSQL"]
    mock_parse.assert_called()


@patch("jd_parsing.parse_jd.parse_jd_text", side_effect=["not json", VALID_JD_JSON])
def test_parse_jd_retries_once_on_invalid_output(mock_parse: object):
    parsed = parse_jd("We are hiring.")

    assert parsed.role == "Backend Engineer"
    assert mock_parse.call_count == 2


@patch("jd_parsing.parse_jd.parse_jd_text", return_value="still not json")
def test_parse_jd_raises_after_retry_exhausted(mock_parse: object):
    with pytest.raises(JDValidationError):
        parse_jd("We are hiring.")

    assert mock_parse.call_count == 2
