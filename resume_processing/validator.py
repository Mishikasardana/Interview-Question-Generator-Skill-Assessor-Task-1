"""
JSON validation module.

Purpose:
    Never trust LLM output. Parse raw JSON, validate against ``ParsedResume``
    schema, and retry once on failure before raising an exception.

Inputs:
    Raw JSON string from ``resume_parser.py``, or cleaned text for the
    combined parse-and-validate flow.

Outputs:
    Validated ``ParsedResume`` instance (pre-normalization).

Example usage:
    >>> from resume_processing.validator import parse_and_validate_resume
    >>> parsed = parse_and_validate_resume(cleaned_text)

Design notes:
    - Validation is separate from parsing so we can unit-test schema rules
      without mocking the GLM API.
    - ``parse_and_validate_resume`` retries the full GLM call once when
      validation fails.
"""

from __future__ import annotations

import json

from pydantic import ValidationError as PydanticValidationError

from resume_processing.exceptions import ValidationError
from resume_processing.resume_parser import parse_resume_text, strip_markdown_fences
from resume_processing.schema import ParsedResume

_MAX_PARSE_ATTEMPTS = 2


def validate_resume_json(raw_json: str) -> ParsedResume:
    """
    Parse and validate raw LLM JSON output against the resume schema.

    Args:
        raw_json: JSON string returned by the resume parser.

    Returns:
        A validated ``ParsedResume`` instance.

    Raises:
        ValidationError: If JSON is invalid or schema validation fails.
    """
    if not isinstance(raw_json, str):
        raise ValidationError(
            f"Expected str for resume JSON, got {type(raw_json).__name__}."
        )

    if not raw_json or not raw_json.strip():
        raise ValidationError("Cannot validate empty JSON string.")

    cleaned_json = strip_markdown_fences(raw_json)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON from resume parser: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return ParsedResume.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f"Resume schema validation failed: {exc}") from exc


def parse_and_validate_resume(cleaned_text: str) -> ParsedResume:
    """
    Parse resume text via GLM and validate the result, with one retry.

    Calls ``parse_resume_text`` up to two times. If validation fails on
    the first attempt, the parser is invoked again before giving up.

    Args:
        cleaned_text: Whitespace-normalized resume text.

    Returns:
        A validated ``ParsedResume`` instance.

    Raises:
        ResumeParsingError: If the GLM API call fails.
        ValidationError: If validation fails after all attempts.
    """
    last_error: ValidationError | None = None

    for attempt in range(1, _MAX_PARSE_ATTEMPTS + 1):
        raw_json = parse_resume_text(cleaned_text)
        try:
            return validate_resume_json(raw_json)
        except ValidationError as exc:
            last_error = exc
            if attempt == _MAX_PARSE_ATTEMPTS:
                break

    assert last_error is not None
    raise ValidationError(
        f"Resume validation failed after {_MAX_PARSE_ATTEMPTS} attempts: "
        f"{last_error}"
    ) from last_error
