"""
Output validation for generated interview questions.

The model response is treated as untrusted text. This module parses JSON and
validates it against the canonical Pydantic schema.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable

from pydantic import ValidationError as PydanticValidationError

from question_generation.exceptions import QuestionValidationError
from question_generation.schema import GeneratedQuestions

_MAX_GENERATION_ATTEMPTS = 2

# A response is only treated as "too short to use" (and thus retried) if it
# falls meaningfully below what was requested — tolerating the model
# returning e.g. 9 when 10 were asked for avoids retry-thrashing (and the
# extra GLM call) over a trivial off-by-one, while 0-2 out of 10 still
# triggers a retry.
_MIN_ACCEPTABLE_COUNT_RATIO = 0.8


def _count_is_acceptable(actual: int, requested: int) -> bool:
    return actual >= max(1, math.ceil(requested * _MIN_ACCEPTABLE_COUNT_RATIO))
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
        Inner content without JSON fences, or the original trimmed text.
    """
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def validate_question_json(raw_json: str) -> GeneratedQuestions:
    """
    Parse and validate raw question JSON.

    Raises:
        QuestionValidationError: If JSON parsing or schema validation fails.
    """
    if not isinstance(raw_json, str):
        raise QuestionValidationError(
            f"Expected str for question JSON, got {type(raw_json).__name__}."
        )

    if not raw_json.strip():
        raise QuestionValidationError("Cannot validate empty question JSON.")

    cleaned_json = strip_markdown_fences(raw_json)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        raise QuestionValidationError(
            f"Invalid JSON from question generator: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise QuestionValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return GeneratedQuestions.model_validate(data)
    except PydanticValidationError as exc:
        raise QuestionValidationError(
            f"Question schema validation failed: {exc}"
        ) from exc


def validate_with_retry(
    generate_once: Callable[[], str],
    *,
    question_count: int | None = None,
) -> GeneratedQuestions:
    """
    Call a generator function and validate its output, retrying once if invalid.

    Args:
        generate_once: Callable that returns raw JSON from GLM.
        question_count: Number of questions originally requested. When
            given, a schema-valid response with too few questions (see
            ``_MIN_ACCEPTABLE_COUNT_RATIO``) is treated as invalid and
            retried too, instead of silently returning a short batch.

    Returns:
        Validated generated questions.

    Raises:
        QuestionValidationError: If all attempts return invalid output (or
            an unacceptably short one, when ``question_count`` is given).
    """
    last_error: QuestionValidationError | None = None

    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        raw_json = generate_once()
        try:
            result = validate_question_json(raw_json)
        except QuestionValidationError as exc:
            last_error = exc
            if attempt == _MAX_GENERATION_ATTEMPTS:
                break
            continue

        if question_count is not None and not _count_is_acceptable(
            len(result.questions), question_count
        ):
            last_error = QuestionValidationError(
                f"Requested {question_count} questions but received "
                f"{len(result.questions)}."
            )
            if attempt == _MAX_GENERATION_ATTEMPTS:
                break
            continue

        return result

    assert last_error is not None
    raise QuestionValidationError(
        "Question validation failed after "
        f"{_MAX_GENERATION_ATTEMPTS} attempts: {last_error}"
    ) from last_error
