"""Unit tests for validator.py."""

from unittest.mock import patch

import pytest

from resume_processing.exceptions import ValidationError
from resume_processing.schema import ParsedResume
from resume_processing.validator import parse_and_validate_resume, validate_resume_json

VALID_RESUME_JSON = """
{
    "name": "Jane Doe",
    "email": "jane@email.com",
    "phone": "+1-555-0100",
    "linkedin": "linkedin.com/in/janedoe",
    "github": "github.com/janedoe",
    "skills": ["Python", "JavaScript"],
    "education": ["B.S. Computer Science, State University, 2022"],
    "experience": ["Software Engineer Intern, Tech Corp, 2023"],
    "projects": ["Interview Prep Tracker"],
    "certifications": ["AWS Cloud Practitioner"]
}
"""


def test_validate_resume_json_success() -> None:
    result = validate_resume_json(VALID_RESUME_JSON)

    assert isinstance(result, ParsedResume)
    assert result.name == "Jane Doe"
    assert result.skills == ["Python", "JavaScript"]
    # Not present in VALID_RESUME_JSON -- defaults to None, not 0, since a
    # missing estimate is a different fact than a genuine zero.
    assert result.estimated_total_experience_years is None


def test_validate_resume_json_accepts_estimated_total_experience_years() -> None:
    payload = VALID_RESUME_JSON.rstrip().rstrip("}") + ', "estimated_total_experience_years": 3.25}'
    result = validate_resume_json(payload)

    assert result.estimated_total_experience_years == 3.25


def test_validate_resume_json_accepts_null_experience_years() -> None:
    payload = VALID_RESUME_JSON.rstrip().rstrip("}") + ', "estimated_total_experience_years": null}'
    result = validate_resume_json(payload)

    assert result.estimated_total_experience_years is None


def test_validate_resume_json_rejects_invalid_json() -> None:
    with pytest.raises(ValidationError, match="Invalid JSON"):
        validate_resume_json("{not valid json")


def test_validate_resume_json_rejects_wrong_types() -> None:
    bad_json = '{"name": "Jane", "skills": "Python"}'

    with pytest.raises(ValidationError, match="schema validation failed"):
        validate_resume_json(bad_json)


def test_validate_resume_json_rejects_extra_fields() -> None:
    bad_json = '{"name": "Jane", "skills": [], "summary": "extra"}'

    with pytest.raises(ValidationError, match="schema validation failed"):
        validate_resume_json(bad_json)


def test_validate_resume_json_rejects_non_string_input() -> None:
    with pytest.raises(ValidationError, match="Expected str"):
        validate_resume_json({"name": "Jane"})  # type: ignore[arg-type]


def test_validate_resume_json_rejects_non_object_root() -> None:
    with pytest.raises(ValidationError, match="JSON object"):
        validate_resume_json('["not", "an", "object"]')


@patch("resume_processing.validator.parse_resume_text")
def test_parse_and_validate_resume_success(mock_parse) -> None:
    mock_parse.return_value = VALID_RESUME_JSON

    result = parse_and_validate_resume("Jane Doe\nPython")

    assert result.name == "Jane Doe"
    mock_parse.assert_called_once()


@patch("resume_processing.validator.parse_resume_text")
def test_parse_and_validate_resume_retries_once(mock_parse) -> None:
    mock_parse.side_effect = [
        "{invalid json",
        VALID_RESUME_JSON,
    ]

    result = parse_and_validate_resume("Jane Doe")

    assert result.email == "jane@email.com"
    assert mock_parse.call_count == 2


@patch("resume_processing.validator.parse_resume_text")
def test_parse_and_validate_resume_fails_after_two_attempts(mock_parse) -> None:
    mock_parse.return_value = "{still bad"

    with pytest.raises(ValidationError, match="after 2 attempts"):
        parse_and_validate_resume("Jane Doe")

    assert mock_parse.call_count == 2
