"""Tests for answer_evaluation.evaluate_answer orchestration."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from answer_evaluation.evaluate_answer import evaluate_answer
from answer_evaluation.exceptions import AnswerValidationError

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
        "ideal_answer": "A model answer would cover REST principles.",
    }
)


@patch(
    "answer_evaluation.evaluate_answer.evaluate_answer_text",
    return_value=VALID_EVALUATION_JSON,
)
def test_evaluate_answer_returns_validated_model(mock_evaluate: object):
    result = evaluate_answer(
        question="Explain REST vs GraphQL",
        candidate_answer="REST uses fixed endpoints.",
        job_role="Backend Engineer",
        required_skills=["Python", "REST API"],
    )

    assert result.overall_score == 78
    assert result.feedback == "Solid answer overall."
    mock_evaluate.assert_called()


@patch(
    "answer_evaluation.evaluate_answer.evaluate_answer_text",
    side_effect=["not json", VALID_EVALUATION_JSON],
)
def test_evaluate_answer_retries_once_on_invalid_output(mock_evaluate: object):
    result = evaluate_answer(
        question="Explain REST APIs.",
        candidate_answer="REST is ...",
        job_role="Backend Engineer",
        required_skills=["Python"],
    )

    assert result.overall_score == 78
    assert mock_evaluate.call_count == 2


@patch(
    "answer_evaluation.evaluate_answer.evaluate_answer_text",
    return_value="still not json",
)
def test_evaluate_answer_raises_after_retry_exhausted(mock_evaluate: object):
    with pytest.raises(AnswerValidationError):
        evaluate_answer(
            question="Explain REST APIs.",
            candidate_answer="REST is ...",
            job_role="Backend Engineer",
            required_skills=["Python"],
        )

    assert mock_evaluate.call_count == 2
