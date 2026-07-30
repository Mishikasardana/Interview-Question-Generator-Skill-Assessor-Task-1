"""Tests for answer_evaluation.evaluator — GLM call layer (mocked)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from answer_evaluation.evaluator import evaluate_answer_text
from answer_evaluation.exceptions import AnswerEvaluationError

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


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = content
    response.json.return_value = {"choices": [{"message": {"content": content}}]}

    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=MagicMock(),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None

    return response


def test_evaluate_answer_text_rejects_empty_question():
    with pytest.raises(AnswerEvaluationError, match="empty question"):
        evaluate_answer_text("", "Some answer", "Backend Engineer", ["Python"])


def test_evaluate_answer_text_rejects_empty_answer():
    with pytest.raises(AnswerEvaluationError, match="empty candidate answer"):
        evaluate_answer_text(
            "Explain REST APIs.",
            "   ",
            "Backend Engineer",
            ["Python"],
        )


@patch("answer_evaluation.evaluator.get_glm_api_key", return_value="test-key")
@patch("answer_evaluation.evaluator.httpx.post")
def test_evaluate_answer_text_success(mock_post: MagicMock, _mock_key: MagicMock):
    mock_post.return_value = _mock_response(VALID_EVALUATION_JSON)

    result = evaluate_answer_text(
        question="Explain REST vs GraphQL",
        candidate_answer="REST uses fixed endpoints.",
        job_role="Backend Engineer",
        required_skills=["Python", "REST API"],
    )

    assert result == VALID_EVALUATION_JSON
    user_message = mock_post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "Explain REST vs GraphQL" in user_message
    assert "REST uses fixed endpoints." in user_message


@patch("answer_evaluation.evaluator.get_glm_api_key", return_value="test-key")
@patch("answer_evaluation.evaluator.httpx.post")
def test_evaluate_answer_text_raises_on_http_error(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response("Unauthorized", status_code=401)

    with pytest.raises(AnswerEvaluationError, match="HTTP 401"):
        evaluate_answer_text(
            "Explain REST APIs.",
            "REST is ...",
            "Backend Engineer",
            ["Python"],
        )


@patch("answer_evaluation.evaluator.get_glm_api_key", return_value="test-key")
@patch("answer_evaluation.evaluator.httpx.post")
def test_evaluate_answer_text_accepts_none_required_skills(
    mock_post: MagicMock, _mock_key: MagicMock
):
    # required_skills=None used to hit an unguarded ', '.join(None) and
    # raise a bare TypeError instead of a clean AnswerEvaluationError.
    mock_post.return_value = _mock_response(VALID_EVALUATION_JSON)

    result = evaluate_answer_text(
        question="Explain REST APIs.",
        candidate_answer="REST is stateless.",
        job_role="Backend Engineer",
        required_skills=None,  # type: ignore[arg-type]
    )

    assert result == VALID_EVALUATION_JSON


@patch("answer_evaluation.evaluator.get_glm_api_key", return_value="test-key")
@patch("answer_evaluation.evaluator.httpx.post")
def test_evaluate_answer_text_strict_mode_appends_instruction(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response(VALID_EVALUATION_JSON)

    evaluate_answer_text(
        "Explain REST APIs.",
        "REST is ...",
        "Backend Engineer",
        ["Python"],
        strict=True,
    )

    system_message = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "Ensure every field from the schema is present" in system_message
