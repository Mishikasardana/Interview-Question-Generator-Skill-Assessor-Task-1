"""Tests for answer_evaluation.output_validator — no network calls required."""

from __future__ import annotations

import json

import pytest

from answer_evaluation.exceptions import AnswerValidationError
from answer_evaluation.output_validator import (
    strip_markdown_fences,
    validate_evaluation_json,
    validate_with_retry,
)

VALID_EVALUATION_JSON = json.dumps(
    {
        "overall_score": 78,
        "correctness": 25,
        "keyword_coverage": 18,
        "clarity": 16,
        "communication": 12,
        "completeness": 7,
        "strengths": ["Clear structure"],
        "improvements": ["More examples"],
        "feedback": "Solid answer overall.",
        "ideal_answer": "A model answer would cover ...",
    }
)


def test_strip_markdown_fences_removes_json_fence():
    fenced = f"```json\n{VALID_EVALUATION_JSON}\n```"
    assert strip_markdown_fences(fenced) == VALID_EVALUATION_JSON


def test_validate_evaluation_json_valid_payload():
    result = validate_evaluation_json(VALID_EVALUATION_JSON)
    assert result.overall_score == 78
    assert result.strengths == ["Clear structure"]


def test_validate_evaluation_json_fills_missing_fields_with_defaults():
    result = validate_evaluation_json(json.dumps({"overall_score": 50}))
    assert result.strengths == []
    assert result.feedback == ""


def test_validate_evaluation_json_no_stray_required_skill_relevance_field():
    # Regression test: an earlier draft's schema accepted a stray
    # "required_skill_relevance" key that the prompt never asks for. The
    # schema now forbids extra fields entirely, so unexpected keys should
    # raise instead of being silently accepted.
    payload = json.loads(VALID_EVALUATION_JSON)
    payload["required_skill_relevance"] = 10
    with pytest.raises(AnswerValidationError):
        validate_evaluation_json(json.dumps(payload))


def test_validate_evaluation_json_recomputes_inconsistent_overall_score():
    # The model can return an overall_score that doesn't match the sum of
    # its own subscores (e.g. a model arithmetic slip). Both would pass
    # each field's independent range check, so the schema now recomputes
    # overall_score from the subscores instead of trusting the model's math.
    payload = json.loads(VALID_EVALUATION_JSON)
    payload["overall_score"] = 12  # inconsistent with the subscores below
    # correctness=25, keyword_coverage=18, clarity=16, communication=12,
    # completeness=7 -> sum = 78, regardless of the stray "12" above.

    result = validate_evaluation_json(json.dumps(payload))

    assert result.overall_score == 78


def test_validate_evaluation_json_rejects_empty_string():
    with pytest.raises(AnswerValidationError):
        validate_evaluation_json("")


def test_validate_evaluation_json_rejects_invalid_json():
    with pytest.raises(AnswerValidationError):
        validate_evaluation_json("{not valid json")


def test_validate_with_retry_retries_once_then_succeeds():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        if len(calls) == 1:
            return "not json"
        return VALID_EVALUATION_JSON

    result = validate_with_retry(fake_generate)
    assert result.overall_score == 78
    assert calls == [False, True]


def test_validate_with_retry_succeeds_on_first_attempt_without_strict_retry():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        return VALID_EVALUATION_JSON

    result = validate_with_retry(fake_generate)

    assert result.overall_score == 78
    assert calls == [False]


def test_validate_with_retry_raises_after_exhausting_attempts():
    def always_invalid(strict: bool) -> str:
        return "still not json"

    with pytest.raises(AnswerValidationError):
        validate_with_retry(always_invalid)
