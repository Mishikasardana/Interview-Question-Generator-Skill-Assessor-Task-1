"""
Output validation for parsed job descriptions.

The model response is treated as untrusted text. This module strips markdown
fences, parses JSON, and validates it against the canonical Pydantic schema —
retrying once (with a stricter prompt) if the first attempt fails, exactly
like ``question_generation.output_validator``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError as PydanticValidationError

from jd_parsing.exceptions import JDValidationError
from jd_parsing.schema import ParsedJD

_MAX_PARSE_ATTEMPTS = 2
_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def strip_markdown_fences(text: str) -> str:
    """
    Remove optional markdown code fences from model output.

    Args:
        text: Raw model response string.

    Returns:
        Inner content without ```json fences, or the original trimmed text.
    """
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def validate_jd_json(raw_json: str) -> ParsedJD:
    """
    Parse and validate raw JD JSON.

    Raises:
        JDValidationError: If JSON parsing or schema validation fails.
    """
    if not isinstance(raw_json, str):
        raise JDValidationError(
            f"Expected str for JD JSON, got {type(raw_json).__name__}."
        )

    if not raw_json.strip():
        raise JDValidationError("Cannot validate empty JD JSON.")

    cleaned_json = strip_markdown_fences(raw_json)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise JDValidationError(f"Invalid JSON from JD parser: {exc}") from exc

    if not isinstance(data, dict):
        raise JDValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return ParsedJD.model_validate(data)
    except PydanticValidationError as exc:
        raise JDValidationError(f"JD schema validation failed: {exc}") from exc


def validate_with_retry(generate_once: Callable[[bool], str]) -> ParsedJD:
    """
    Call a generator function and validate its output, retrying once if invalid.

    Args:
        generate_once: Callable taking a ``strict`` flag and returning raw
            JSON from GLM. Called with ``strict=False`` on the first attempt
            and ``strict=True`` on the retry.

    Returns:
        Validated parsed JD.

    Raises:
        JDValidationError: If all attempts return invalid output.
    """
    last_error: JDValidationError | None = None

    for attempt in range(1, _MAX_PARSE_ATTEMPTS + 1):
        raw_json = generate_once(attempt > 1)
        try:
            return validate_jd_json(raw_json)
        except JDValidationError as exc:
            last_error = exc
            if attempt == _MAX_PARSE_ATTEMPTS:
                break

    assert last_error is not None
    raise JDValidationError(
        f"JD validation failed after {_MAX_PARSE_ATTEMPTS} attempts: {last_error}"
    ) from last_error
