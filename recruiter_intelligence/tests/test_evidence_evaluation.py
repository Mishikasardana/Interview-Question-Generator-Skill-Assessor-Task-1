"""Tests for recruiter_intelligence.evidence_evaluation — mocked GLM calls, no network."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from recruiter_intelligence.exceptions import (
    EvidenceEvaluationValidationError,
    GLMEvidenceEvaluationError,
    PromptBuildError,
)
from recruiter_intelligence.evidence_evaluation import (
    build_evidence_evaluation_prompt,
    evaluate_evidence,
    evaluate_evidence_text,
    resolve_requirement_scores,
    strip_markdown_fences,
    validate_stage_c_json,
    validate_with_retry,
)
from recruiter_intelligence.schema import Requirement, StageAResult, StageCResult
from resume_processing.schema import ParsedResume

_STAGE_A = StageAResult(
    role_archetype="backend",
    requirements=[
        Requirement(
            id="req_1", text="FastAPI", is_required=True, category="Backend Engineering",
            difficulty_tier="medium", why_it_matters="Core framework",
        ),
        Requirement(
            id="req_2", text="PostgreSQL", is_required=True, category="Databases",
            difficulty_tier="easy", why_it_matters="Primary datastore",
        ),
        Requirement(
            id="req_3", text="Kubernetes", is_required=False, category="DevOps & CI/CD",
            difficulty_tier="hard", why_it_matters="Nice to have",
        ),
    ],
)

_RESUME = ParsedResume(
    name="Jane Doe",
    skills=["Express.js", "Node.js", "PostgreSQL"],
    projects=["Built a production REST API with Express.js serving 10,000 daily users."],
    experience=["Backend Engineer at Acme Corp, 2022-2024."],
    education=["B.S. Computer Science"],
    certifications=[],
)

_VALID_LLM_JSON = json.dumps({
    "requirement_scores": [
        {
            "requirement_id": "req_1", "score": 85,
            "evidence": [{"category": "skills", "snippet": "Express.js", "approximate_recency": "current"}],
            "reasoning": "Express.js is an equivalent backend framework to FastAPI.",
        },
        {
            "requirement_id": "req_2", "score": 100,
            "evidence": [{"category": "skills", "snippet": "PostgreSQL", "approximate_recency": "current"}],
            "reasoning": "Direct match.",
        },
        {
            "requirement_id": "req_3", "score": 10, "evidence": [],
            "reasoning": "No evidence of Kubernetes or containerization anywhere.",
        },
    ],
})


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    response.raise_for_status = MagicMock()
    return response


# --- Prompt building ---


def test_build_evidence_evaluation_prompt_includes_requirements_and_resume():
    prompt = build_evidence_evaluation_prompt(_STAGE_A, _RESUME)
    assert "req_1" in prompt
    assert "FastAPI" in prompt
    assert "Express.js" in prompt
    assert "10,000 daily users" in prompt


def test_build_evidence_evaluation_prompt_includes_ontology_hint():
    # FastAPI and Express.js are both in skill_ontology.yaml's
    # backend_frameworks category -- confirm the shortlist actually surfaces
    # this, directly targeting the original FastAPI/Express.js bug report.
    prompt = build_evidence_evaluation_prompt(_STAGE_A, _RESUME)
    assert "ontology suggests" in prompt
    assert "Express.js" in prompt.split("ontology suggests")[1].split("\n")[0]


def test_build_evidence_evaluation_prompt_includes_recency_guidance_hint():
    # backend_frameworks (FastAPI's category) has decay_rate: moderate --
    # confirm the recency-guidance hint actually surfaces per requirement.
    prompt = build_evidence_evaluation_prompt(_STAGE_A, _RESUME)
    assert "recency guidance" in prompt


def test_build_evidence_evaluation_prompt_rejects_non_stage_a_result():
    with pytest.raises(PromptBuildError):
        build_evidence_evaluation_prompt({"not": "a StageAResult"}, _RESUME)  # type: ignore[arg-type]


def test_build_evidence_evaluation_prompt_rejects_non_parsed_resume():
    with pytest.raises(PromptBuildError):
        build_evidence_evaluation_prompt(_STAGE_A, {"not": "a ParsedResume"})  # type: ignore[arg-type]


# --- GLM call ---


@patch("recruiter_intelligence.evidence_evaluation.httpx.post")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.evidence_evaluation.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_url", return_value="https://example/api")
def test_evaluate_evidence_text_success(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    result = evaluate_evidence_text(_STAGE_A, _RESUME)

    assert result == _VALID_LLM_JSON
    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["messages"][1]["content"] == build_evidence_evaluation_prompt(_STAGE_A, _RESUME)


@patch("recruiter_intelligence.evidence_evaluation.httpx.post")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.evidence_evaluation.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_url", return_value="https://example/api")
def test_evaluate_evidence_text_raises_on_http_error(_url, _model, _key, mock_post):
    request = httpx.Request("POST", "https://example/api")
    response = httpx.Response(401, request=request, text='{"error": "unauthorized"}')
    mock_post.side_effect = httpx.HTTPStatusError("401", request=request, response=response)

    with pytest.raises(GLMEvidenceEvaluationError):
        evaluate_evidence_text(_STAGE_A, _RESUME)


@patch("recruiter_intelligence.evidence_evaluation.httpx.post")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.evidence_evaluation.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_url", return_value="https://example/api")
def test_evaluate_evidence_text_strict_mode_appends_instruction(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    evaluate_evidence_text(_STAGE_A, _RESUME, strict=True)

    sent_payload = mock_post.call_args.kwargs["json"]
    assert "IMPORTANT" in sent_payload["messages"][0]["content"]


# --- Output validation ---


def test_strip_markdown_fences_removes_fence():
    fenced = f"```json\n{_VALID_LLM_JSON}\n```"
    assert strip_markdown_fences(fenced) == _VALID_LLM_JSON


def test_validate_stage_c_json_success():
    result = validate_stage_c_json(_VALID_LLM_JSON)
    assert len(result.requirement_scores) == 3


def test_validate_stage_c_json_rejects_invalid_json():
    with pytest.raises(EvidenceEvaluationValidationError):
        validate_stage_c_json("not json")


def test_validate_stage_c_json_rejects_score_above_missing_band_without_evidence():
    bad = json.dumps({
        "requirement_scores": [
            {"requirement_id": "req_1", "score": 90, "evidence": [], "reasoning": "trust me"},
        ],
    })
    with pytest.raises(EvidenceEvaluationValidationError):
        validate_stage_c_json(bad)


def test_validate_stage_c_json_accepts_low_score_with_no_evidence():
    # Below the 0-20% missing band -- absent evidence is expected, not an error.
    ok = json.dumps({
        "requirement_scores": [
            {"requirement_id": "req_3", "score": 5, "evidence": [], "reasoning": "No evidence at all."},
        ],
    })
    result = validate_stage_c_json(ok)
    assert result.requirement_scores[0].score == 5


def test_validate_stage_c_json_rejects_unknown_field():
    # project_quality no longer exists on StageCResult -- confirms the old
    # shape is actually gone, not just unused.
    bad = json.dumps({
        "requirement_scores": [],
        "project_quality": [{"entry_category": "projects", "entry_index": 0}],
    })
    with pytest.raises(EvidenceEvaluationValidationError):
        validate_stage_c_json(bad)


def test_validate_with_retry_succeeds_on_second_attempt():
    calls: list[bool] = []

    def fake_generate(strict: bool) -> str:
        calls.append(strict)
        return "not json" if len(calls) == 1 else _VALID_LLM_JSON

    result = validate_with_retry(fake_generate)

    assert len(result.requirement_scores) == 3
    assert calls == [False, True]


def test_validate_with_retry_raises_after_exhausting_attempts():
    with pytest.raises(EvidenceEvaluationValidationError):
        validate_with_retry(lambda strict: "still not json")


# --- Resolution against Stage A ---


def test_resolve_requirement_scores_matches_by_id_in_stage_a_order():
    llm_result = StageCResult.model_validate(json.loads(_VALID_LLM_JSON))

    scores = resolve_requirement_scores(_STAGE_A, llm_result)

    assert [s.requirement_id for s in scores] == ["req_1", "req_2", "req_3"]
    assert scores[0].score == 85


def test_resolve_requirement_scores_fills_default_for_id_the_model_dropped():
    llm_result = StageCResult.model_validate(json.loads(json.dumps({
        "requirement_scores": [
            {"requirement_id": "req_1", "score": 85,
             "evidence": [{"category": "skills", "snippet": "Express.js"}], "reasoning": "ok"},
        ],
    })))

    scores = resolve_requirement_scores(_STAGE_A, llm_result)

    assert len(scores) == 3
    req_2_score = next(s for s in scores if s.requirement_id == "req_2")
    assert req_2_score.score == 0
    assert "default" in req_2_score.reasoning


# --- Full orchestration ---


@patch("recruiter_intelligence.evidence_evaluation.httpx.post")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_key", return_value="key")
@patch("recruiter_intelligence.evidence_evaluation.get_recruiter_glm_model", return_value="glm-4.5-flash")
@patch("recruiter_intelligence.evidence_evaluation.get_glm_api_url", return_value="https://example/api")
def test_evaluate_evidence_end_to_end(_url, _model, _key, mock_post):
    mock_post.return_value = _mock_response(_VALID_LLM_JSON)

    result = evaluate_evidence(_STAGE_A, _RESUME)

    assert len(result.requirement_scores) == 3
    assert result.requirement_scores[0].requirement_id == "req_1"
