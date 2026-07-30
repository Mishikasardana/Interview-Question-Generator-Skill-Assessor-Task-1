"""Tests for semantic_matching.evaluate_semantic_match orchestration."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from semantic_matching.evaluate_semantic_match import evaluate_semantic_match
from semantic_matching.exceptions import SemanticMatchValidationError

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


@patch(
    "semantic_matching.evaluate_semantic_match.evaluate_semantic_match_text",
    return_value=VALID_SEMANTIC_JSON,
)
def test_evaluate_semantic_match_returns_validated_model(mock_call):
    result = evaluate_semantic_match(resume_json={"skills": ["Python"]}, jd_json={})

    assert result.overall_score == 82
    assert result.category_scores["LLMs"] == 90
    mock_call.assert_called()


@patch(
    "semantic_matching.evaluate_semantic_match.evaluate_semantic_match_text",
    side_effect=["not json", VALID_SEMANTIC_JSON],
)
def test_evaluate_semantic_match_retries_once_on_invalid_output(mock_call):
    result = evaluate_semantic_match(resume_json={}, jd_json={})

    assert result.overall_score == 82
    assert mock_call.call_count == 2


@patch(
    "semantic_matching.evaluate_semantic_match.evaluate_semantic_match_text",
    return_value="still not json",
)
def test_evaluate_semantic_match_raises_after_retry_exhausted(mock_call):
    with pytest.raises(SemanticMatchValidationError):
        evaluate_semantic_match(resume_json={}, jd_json={})

    assert mock_call.call_count == 2
