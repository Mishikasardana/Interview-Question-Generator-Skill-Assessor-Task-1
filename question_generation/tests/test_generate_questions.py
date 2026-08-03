"""Unit tests for generate_questions.py."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from question_generation.exceptions import GLMQuestionGenerationError
from question_generation.generate_questions import generate_questions

VALID_RESPONSE = """
{
  "questions": [
    {
      "question": "How would you apply Python to this backend role?",
      "category": "Technical",
      "difficulty": "medium",
      "reason": "Python is present in the candidate profile and JD."
    }
  ]
}
"""


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


@patch("question_generation.generate_questions.get_glm_api_key", return_value="test-key")
@patch("question_generation.generate_questions.httpx.post")
def test_generate_questions_success(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    mock_post.return_value = _mock_response(VALID_RESPONSE)

    result = generate_questions(
        resume_json={"skills": ["Python"]},
        jd_json={"required_skills": ["Python"]},
        match_result_json={"matched_skills": ["Python"]},
        difficulty="medium",
        question_count=1,
    )

    assert len(result.questions) == 1
    assert result.questions[0].difficulty == "medium"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


@patch("question_generation.generate_questions.get_glm_api_key", return_value="test-key")
@patch("question_generation.generate_questions.httpx.post")
def test_generate_questions_retries_once_on_malformed_output(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    mock_post.side_effect = [
        _mock_response("{bad json"),
        _mock_response(VALID_RESPONSE),
    ]

    result = generate_questions({}, {}, {}, "medium", 1)

    assert len(result.questions) == 1
    assert mock_post.call_count == 2


@patch("question_generation.generate_questions.get_glm_api_key", return_value="test-key")
@patch("question_generation.generate_questions.httpx.post")
def test_generate_questions_retries_when_far_fewer_questions_than_requested(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    five_questions = """
    {
      "questions": [
        {"question": "Q1?", "category": "Technical", "difficulty": "medium", "reason": "R"},
        {"question": "Q2?", "category": "Technical", "difficulty": "medium", "reason": "R"},
        {"question": "Q3?", "category": "Technical", "difficulty": "medium", "reason": "R"},
        {"question": "Q4?", "category": "Technical", "difficulty": "medium", "reason": "R"},
        {"question": "Q5?", "category": "Technical", "difficulty": "medium", "reason": "R"}
      ]
    }
    """
    # Schema-valid but far short of the 5 requested (1 out of 5) — should
    # trigger a retry rather than being silently accepted.
    mock_post.side_effect = [
        _mock_response(VALID_RESPONSE),  # 1 question
        _mock_response(five_questions),  # 5 questions
    ]

    result = generate_questions(
        resume_json={}, jd_json={}, match_result_json={},
        difficulty="medium", question_count=5,
    )

    assert len(result.questions) == 5
    assert mock_post.call_count == 2


@patch("question_generation.generate_questions.get_glm_api_key", return_value="test-key")
@patch("question_generation.generate_questions.httpx.post")
def test_generate_questions_raises_on_http_error(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    mock_post.return_value = _mock_response("Unauthorized", status_code=401)

    with pytest.raises(GLMQuestionGenerationError, match="HTTP 401"):
        generate_questions({}, {}, {}, "easy", 1)
