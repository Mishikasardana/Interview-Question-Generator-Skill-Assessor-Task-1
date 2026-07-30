"""
Output validation (with retry) for the Semantic Matching Module.

Purpose:
    Parse and validate the raw JSON string returned by GLM against
    ``SemanticMatchResult``, retrying once (with a stricter prompt) if the
    first attempt is invalid — matching the retry pattern already used by
    ``jd_parsing``, ``question_generation``, and ``answer_evaluation``.

Inputs:
    A zero-argument-except-strict-flag callable that performs one GLM call
    and returns raw content (``semantic_scorer.evaluate_semantic_match_text``
    curried by the caller).

Outputs:
    A validated ``SemanticMatchResult``.

Example usage:
    >>> from semantic_matching.output_validator import validate_with_retry
    >>> result = validate_with_retry(lambda strict: raw_json_call(strict))
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from pydantic import ValidationError as PydanticValidationError

from semantic_matching.exceptions import SemanticMatchValidationError
from semantic_matching.schema import SemanticMatchResult

_MAX_ATTEMPTS = 2
_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def strip_markdown_fences(text: str) -> str:
    """Remove optional markdown code fences from model output."""
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def validate_semantic_match_json(raw_json: str) -> SemanticMatchResult:
    """
    Parse and validate raw semantic match JSON.

    Args:
        raw_json: Raw JSON string returned by GLM.

    Returns:
        Validated ``SemanticMatchResult``.

    Raises:
        SemanticMatchValidationError: If JSON parsing or schema validation
            fails.
    """
    if not isinstance(raw_json, str) or not raw_json.strip():
        raise SemanticMatchValidationError("Cannot validate empty semantic match JSON.")

    cleaned_json = strip_markdown_fences(raw_json)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise SemanticMatchValidationError(
            f"Invalid JSON from semantic matcher: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise SemanticMatchValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return SemanticMatchResult.model_validate(data)
    except PydanticValidationError as exc:
        raise SemanticMatchValidationError(
            f"Semantic match schema validation failed: {exc}"
        ) from exc


def validate_with_retry(generate_once: Callable[[bool], str]) -> SemanticMatchResult:
    """
    Call a generator function and validate its output, retrying once if
    invalid.

    Args:
        generate_once: Callable taking a ``strict`` flag and returning raw
            JSON from GLM. Called with ``strict=False`` on the first
            attempt and ``strict=True`` on the retry.

    Returns:
        Validated ``SemanticMatchResult``.

    Raises:
        SemanticMatchValidationError: If all attempts return invalid output.
    """
    last_error: SemanticMatchValidationError | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        raw_json = generate_once(attempt > 1)
        try:
            return validate_semantic_match_json(raw_json)
        except SemanticMatchValidationError as exc:
            last_error = exc

    assert last_error is not None
    raise SemanticMatchValidationError(
        f"Semantic match validation failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error
