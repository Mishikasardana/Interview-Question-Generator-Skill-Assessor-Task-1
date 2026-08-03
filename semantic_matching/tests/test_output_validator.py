"""Tests for semantic_matching.output_validator."""

from __future__ import annotations

import json

import pytest

from semantic_matching.exceptions import SemanticMatchValidationError
from semantic_matching.output_validator import (
    strip_markdown_fences,
    validate_semantic_match_json,
    validate_with_retry,
)

VALID_PAYLOAD = {
    "overall_score": 82,
    "category_scores": {"LLMs": 90, "Prompt Engineering": 75},
    "strengths": ["Built Claude AI applications"],
    "missing_skills": ["Kubernetes"],
    "reasoning": ["Awarded 75% for Prompt Engineering via Claude AI project."],
    "recommendations": ["Add a project explicitly labeled RAG."],
}
VALID_JSON = json.dumps(VALID_PAYLOAD)


def test_strip_markdown_fences_removes_json_fence():
    fenced = f"```json\n{VALID_JSON}\n```"
    assert strip_markdown_fences(fenced) == VALID_JSON


def test_strip_markdown_fences_leaves_plain_json_untouched():
    assert strip_markdown_fences(VALID_JSON) == VALID_JSON


def test_validate_semantic_match_json_success():
    result = validate_semantic_match_json(VALID_JSON)
    assert result.overall_score == 82
    assert result.category_scores["LLMs"] == 90


def test_validate_semantic_match_json_rejects_empty_string():
    with pytest.raises(SemanticMatchValidationError, match="empty"):
        validate_semantic_match_json("")


def test_validate_semantic_match_json_rejects_invalid_json():
    with pytest.raises(SemanticMatchValidationError, match="Invalid JSON"):
        validate_semantic_match_json("not json at all")


def test_validate_semantic_match_json_rejects_non_object_root():
    with pytest.raises(SemanticMatchValidationError, match="JSON object"):
        validate_semantic_match_json("[1, 2, 3]")


def test_validate_semantic_match_json_rejects_out_of_range_score():
    bad_payload = dict(VALID_PAYLOAD, category_scores={"LLMs": 150})
    with pytest.raises(SemanticMatchValidationError, match="schema validation failed"):
        validate_semantic_match_json(json.dumps(bad_payload))


def test_validate_with_retry_succeeds_on_first_attempt():
    calls = []

    def generate_once(strict: bool) -> str:
        calls.append(strict)
        return VALID_JSON

    result = validate_with_retry(generate_once)
    assert result.overall_score == 82
    assert calls == [False]


def test_validate_with_retry_succeeds_on_second_attempt():
    calls = []
    responses = iter(["not json", VALID_JSON])

    def generate_once(strict: bool) -> str:
        calls.append(strict)
        return next(responses)

    result = validate_with_retry(generate_once)
    assert result.overall_score == 82
    assert calls == [False, True]


def test_validate_with_retry_raises_after_exhausting_attempts():
    def generate_once(strict: bool) -> str:
        return "still not json"

    with pytest.raises(SemanticMatchValidationError, match="after 2 attempts"):
        validate_with_retry(generate_once)
