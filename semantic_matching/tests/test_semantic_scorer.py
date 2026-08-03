"""Tests for semantic_matching.semantic_scorer — GLM call layer (mocked)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from semantic_matching.exceptions import GLMSemanticMatchingError
from semantic_matching.semantic_scorer import evaluate_semantic_match_text

VALID_SEMANTIC_JSON = json.dumps(
    {
        "overall_score": 82,
        "category_scores": {"LLMs": 90, "Prompt Engineering": 75},
        "strengths": ["Built Claude AI applications"],
        "missing_skills": ["Kubernetes"],
        "reasoning": ["Awarded 75% for Prompt Engineering via Claude AI project."],
        "recommendations": ["Add a project explicitly labeled RAG."],
    }
)


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = content
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response,
        )
    else:
        response.raise_for_status.return_value = None
    return response


@patch("semantic_matching.semantic_scorer.get_glm_api_key", return_value="test-key")
@patch("semantic_matching.semantic_scorer.httpx.post")
def test_evaluate_semantic_match_text_success(mock_post: MagicMock, _mock_key: MagicMock):
    mock_post.return_value = _mock_response(VALID_SEMANTIC_JSON)

    result = evaluate_semantic_match_text(
        resume_json={"skills": ["Python"]}, jd_json={"required_skills": ["Python"]},
    )

    assert result == VALID_SEMANTIC_JSON
    user_message = mock_post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "CANDIDATE RESUME" in user_message


@patch("semantic_matching.semantic_scorer.get_glm_api_key", return_value="test-key")
@patch("semantic_matching.semantic_scorer.httpx.post")
def test_evaluate_semantic_match_text_raises_on_http_error(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response("Unauthorized", status_code=401)

    with pytest.raises(GLMSemanticMatchingError, match="HTTP 401"):
        evaluate_semantic_match_text({}, {})


@patch("semantic_matching.semantic_scorer.get_glm_api_key", return_value="test-key")
@patch("semantic_matching.semantic_scorer.httpx.post")
def test_evaluate_semantic_match_text_raises_on_empty_content(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response("")

    with pytest.raises(GLMSemanticMatchingError, match="empty content"):
        evaluate_semantic_match_text({}, {})


@patch("semantic_matching.semantic_scorer.get_glm_api_key", return_value="test-key")
@patch("semantic_matching.semantic_scorer.httpx.post")
def test_evaluate_semantic_match_text_strict_mode_appends_instruction(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response(VALID_SEMANTIC_JSON)

    evaluate_semantic_match_text({}, {}, strict=True)

    system_message = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "Ensure every field from the schema is present" in system_message
