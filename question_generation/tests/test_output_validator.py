"""Unit tests for output_validator.py."""

import json

import pytest

from question_generation.exceptions import QuestionValidationError
from question_generation.output_validator import (
    strip_markdown_fences,
    validate_question_json,
    validate_with_retry,
)
from question_generation.schema import GeneratedQuestions

VALID_QUESTIONS_JSON = """
{
  "questions": [
    {
      "question": "How did you use Python in your resume project?",
      "category": "Technical",
      "difficulty": "medium",
      "reason": "Python appears in both the resume and job description."
    }
  ]
}
"""


def test_validate_question_json_success() -> None:
    result = validate_question_json(VALID_QUESTIONS_JSON)

    assert isinstance(result, GeneratedQuestions)
    assert len(result.questions) == 1
    assert result.questions[0].category == "Technical"


def test_validate_question_json_rejects_invalid_json() -> None:
    with pytest.raises(QuestionValidationError, match="Invalid JSON"):
        validate_question_json("{bad json")


def test_validate_question_json_rejects_extra_fields() -> None:
    raw_json = """
    {
      "questions": [
        {
          "question": "Q?",
          "category": "Technical",
          "difficulty": "easy",
          "reason": "Relevant",
          "score": 10
        }
      ]
    }
    """

    with pytest.raises(QuestionValidationError, match="schema validation failed"):
        validate_question_json(raw_json)


def test_strip_markdown_fences() -> None:
    fenced = f"```json\n{VALID_QUESTIONS_JSON}\n```"

    assert strip_markdown_fences(fenced).startswith("{")


def test_validate_with_retry_succeeds_on_second_attempt() -> None:
    outputs = iter(["{bad json", VALID_QUESTIONS_JSON])

    result = validate_with_retry(lambda: next(outputs))

    assert len(result.questions) == 1


def test_validate_with_retry_fails_after_two_attempts() -> None:
    with pytest.raises(QuestionValidationError, match="after 2 attempts"):
        validate_with_retry(lambda: "{bad json")


def test_validate_with_retry_ignores_count_when_not_given() -> None:
    # Without question_count, a short batch is accepted as-is — this is
    # the pre-existing behavior, preserved for callers that don't pass it.
    result = validate_with_retry(lambda: VALID_QUESTIONS_JSON)
    assert len(result.questions) == 1


def test_validate_with_retry_retries_on_undershoot_then_succeeds() -> None:
    short_batch = VALID_QUESTIONS_JSON  # 1 question
    full_batch = json.dumps(
        {
            "questions": [
                {
                    "question": f"Question {i}?",
                    "category": "Technical",
                    "difficulty": "medium",
                    "reason": "Relevant",
                }
                for i in range(5)
            ]
        }
    )
    outputs = iter([short_batch, full_batch])

    result = validate_with_retry(lambda: next(outputs), question_count=5)

    # 1 out of 5 requested (20%) is well under the 80% floor, so the first
    # attempt is rejected and the retry's full batch is returned instead.
    assert len(result.questions) == 5


def test_validate_with_retry_accepts_small_undershoot_without_retrying() -> None:
    calls = []

    def generate_once() -> str:
        calls.append(1)
        return VALID_QUESTIONS_JSON  # 1 question

    # Requesting 1 question and getting 1 back is a full match (100% >= 80%
    # floor) — should succeed on the first attempt, no retry.
    result = validate_with_retry(generate_once, question_count=1)

    assert len(result.questions) == 1
    assert len(calls) == 1


def test_validate_with_retry_fails_after_two_short_attempts() -> None:
    with pytest.raises(QuestionValidationError, match="after 2 attempts"):
        validate_with_retry(lambda: VALID_QUESTIONS_JSON, question_count=10)


def test_validate_question_json_rejects_unrecognized_difficulty() -> None:
    # difficulty is a closed set (easy/medium/hard) — an out-of-set or
    # inconsistently-cased value from the model should fail validation
    # (and thus trigger a retry) instead of silently passing through.
    raw_json = """
    {
      "questions": [
        {
          "question": "Q?",
          "category": "Technical",
          "difficulty": "Medium",
          "reason": "Relevant"
        }
      ]
    }
    """

    with pytest.raises(QuestionValidationError, match="schema validation failed"):
        validate_question_json(raw_json)
