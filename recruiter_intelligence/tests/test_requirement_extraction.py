"""Tests for recruiter_intelligence.requirement_extraction — mocked GLM calls, no network."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from jd_parsing.schema import ParsedJD
from recruiter_intelligence.exceptions import (
    GLMRequirementExtractionError,
    PromptBuildError,
    RequirementExtractionValidationError,
)
from recruiter_intelligence.requirement_extraction import (
    build_requirement_extraction_prompt,
    extract_requirements,
    extract_requirements_text,
    resolve_requirements,
    strip_markdown_fences,
    validate_stage_a_json,
    validate_with_retry,
)
from recruiter_intelligence.schema import RequirementJudgment, StageALLMResponse

_JD = ParsedJD(
    role="Senior Backend Engineer",
    required_skills=["FastAPI", "PostgreSQL"],
    preferred_skills=["Docker"],
    responsibilities=["Design APIs"],
    experience_level="Senior (5+ years)",
)

_VALID_LLM_JSON = json.dumps({
    "role_archetype": "backend",
    "requirement_judgments": [
        {"skill": "FastAPI", "category": "Backend Engineering",
         "difficulty_tier": "medium", "why_it_matters": "Core framework"},
        {"skill": "PostgreSQL", "category": "Databases",
         "difficulty_tier": "easy", "why_it_matters": "Primary datastore"},
        {"skill": "Docker", "category": "DevOps & CI/CD",
         "difficulty_tier": "easy", "why_it_matters": "Nice to have for deployment"},
    ],
})


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    response.raise_for_status = MagicMock()
    return response


# --- Prompt building ---


def test_build_requirement_extraction_prompt_includes_required_and_preferred():
    prompt = build_requirement_extraction_prompt(_JD)
    assert "FastAPI" in prompt
    assert "PostgreSQL" in prompt
    assert "Docker" in prompt
    assert "Senior Backend Engineer" in prompt


def test_build_requirement_extraction_prompt_includes_ontology_hint():
    # FastAPI is in skill_ontology.yaml's backend_frameworks category
    # (base_difficulty: medium) -- confirm the hint actually surfaces.
    prompt = build_requirement_extraction_prompt(_JD)
    assert "FastAPI: baseline difficulty" in prompt


def test_build_requirement_extraction_prompt_rejects_non_parsed_jd():
    with pytest.raises(PromptBuildError):
        build_requirement_extraction_prompt({"role": "not a ParsedJD"})  # type: ignore[arg-type]


# --- GLM call ---


@patch("recruiter_intelligence.requirement_extraction.httpx.post")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.requirement_extraction.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_url", return_value="https://example/api")
def test_extract_requirements_text_success(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    result = extract_requirements_text(_JD)

    assert result == _VALID_LLM_JSON
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["messages"][1]["content"] == build_requirement_extraction_prompt(_JD)


@patch("recruiter_intelligence.requirement_extraction.httpx.post")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.requirement_extraction.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_url", return_value="https://example/api")
def test_extract_requirements_text_raises_on_http_error(_url, _model, _key, mock_post):
    request = httpx.Request("POST", "https://example/api")
    response = httpx.Response(401, request=request, text='{"error": "unauthorized"}')
    mock_post.side_effect = httpx.HTTPStatusError("401", request=request, response=response)

    with pytest.raises(GLMRequirementExtractionError):
        extract_requirements_text(_JD)


@patch("recruiter_intelligence.requirement_extraction.httpx.post")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.requirement_extraction.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_url", return_value="https://example/api")
def test_extract_requirements_text_strict_mode_appends_instruction(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    extract_requirements_text(_JD, strict=True)

    sent_payload = mock_post.call_args.kwargs["json"]
    assert "IMPORTANT" in sent_payload["messages"][0]["content"]


# --- Output validation ---


def test_strip_markdown_fences_removes_fence():
    fenced = f"```json\n{_VALID_LLM_JSON}\n```"
    assert strip_markdown_fences(fenced) == _VALID_LLM_JSON


def test_validate_stage_a_json_success():
    result = validate_stage_a_json(_VALID_LLM_JSON)
    assert result.role_archetype == "backend"
    assert len(result.requirement_judgments) == 3


def test_validate_stage_a_json_rejects_invalid_json():
    with pytest.raises(RequirementExtractionValidationError):
        validate_stage_a_json("not json")


def test_validate_stage_a_json_rejects_invalid_difficulty_tier():
    bad = json.dumps({
        "role_archetype": "backend",
        "requirement_judgments": [
            {"skill": "FastAPI", "category": "Backend Engineering", "difficulty_tier": "impossible"},
        ],
    })
    with pytest.raises(RequirementExtractionValidationError):
        validate_stage_a_json(bad)


def test_validate_stage_a_json_rejects_invalid_category():
    bad = json.dumps({
        "role_archetype": "backend",
        "requirement_judgments": [{"skill": "FastAPI", "category": "Not A Real Category"}],
    })
    with pytest.raises(RequirementExtractionValidationError):
        validate_stage_a_json(bad)


def test_validate_with_retry_succeeds_on_second_attempt():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        return "not json" if len(calls) == 1 else _VALID_LLM_JSON

    result = validate_with_retry(fake_generate)

    assert result.role_archetype == "backend"
    assert calls == [False, True]


def test_validate_with_retry_raises_after_exhausting_attempts():
    with pytest.raises(RequirementExtractionValidationError):
        validate_with_retry(lambda strict: "still not json")


# --- Resolution against the source JD lists ---


def test_resolve_requirements_matches_by_text_and_assigns_ids():
    llm_response = StageALLMResponse.model_validate(json.loads(_VALID_LLM_JSON))

    result = resolve_requirements(_JD, llm_response)

    assert result.role_archetype == "backend"
    assert [r.text for r in result.requirements] == ["FastAPI", "PostgreSQL", "Docker"]
    assert [r.id for r in result.requirements] == ["req_1", "req_2", "req_3"]
    assert result.requirements[0].is_required is True   # from required_skills
    assert result.requirements[2].is_required is False  # from preferred_skills
    assert result.requirements[0].category == "Backend Engineering"


def test_resolve_requirements_matching_is_case_and_whitespace_insensitive():
    llm_response = StageALLMResponse(
        role_archetype="backend",
        requirement_judgments=[
            RequirementJudgment(skill="  fastapi  ", category="Backend Engineering"),
        ],
    )
    jd = ParsedJD(role="Backend Engineer", required_skills=["FastAPI"])

    result = resolve_requirements(jd, llm_response)

    assert result.requirements[0].category == "Backend Engineering"


def test_resolve_requirements_fills_default_for_skill_the_model_dropped():
    # The model's response is missing "PostgreSQL" entirely.
    llm_response = StageALLMResponse(
        role_archetype="backend",
        requirement_judgments=[
            RequirementJudgment(skill="FastAPI", category="Backend Engineering"),
        ],
    )
    jd = ParsedJD(role="Backend Engineer", required_skills=["FastAPI", "PostgreSQL"])

    result = resolve_requirements(jd, llm_response)

    assert len(result.requirements) == 2
    postgres_req = next(r for r in result.requirements if r.text == "PostgreSQL")
    assert postgres_req.category == "Other"
    assert "default" in postgres_req.why_it_matters


def test_resolve_requirements_populates_ontology_base_difficulty():
    llm_response = StageALLMResponse.model_validate(json.loads(_VALID_LLM_JSON))

    result = resolve_requirements(_JD, llm_response)

    fastapi_req = next(r for r in result.requirements if r.text == "FastAPI")
    assert fastapi_req.ontology_base_difficulty == "medium"


# --- Full orchestration ---


@patch("recruiter_intelligence.requirement_extraction.httpx.post")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.requirement_extraction.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.requirement_extraction.get_glm_api_url", return_value="https://example/api")
def test_extract_requirements_end_to_end(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    result = extract_requirements(_JD)

    assert result.role_archetype == "backend"
    assert len(result.requirements) == 3
    assert result.requirements[0].id == "req_1"
