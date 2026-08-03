"""End-to-end API pipeline tests with external dependencies mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jd_parsing.schema import ParsedJD
from jd_parsing.exceptions import JDParsingError
from question_generation.exceptions import GLMQuestionGenerationError
from recruiter_intelligence.schema import (
    HardGateResult,
    RecruiterMatchResult,
    Requirement,
    RequirementScore,
    StageAResult,
    StageCResult,
)
from resume_processing.exceptions import FileValidationError
from resume_processing.schema import ParsedResume

pytestmark = pytest.mark.e2e


def _recruiter_match_result(*, score: int, recommendation: str, critical_missing_skills=None) -> RecruiterMatchResult:
    """A minimal, valid RecruiterMatchResult for mocking api.routes.matching.aggregate."""
    return RecruiterMatchResult(
        recruiter_match_score=score,
        confidence="High",
        confidence_reason="mocked for testing",
        recommendation=recommendation,
        hard_gate=HardGateResult(overall_status="pass", results=[]),
        role_archetype="backend",
        critical_missing_skills=critical_missing_skills or [],
        narrative=f"Recommendation: {recommendation}",
    )


@patch("api.routes.evaluation.evaluate_answer")
def test_evaluate_endpoint_success(mock_evaluate: MagicMock, api_client, valid_evaluation_json):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = valid_evaluation_json
    mock_evaluate.return_value = mock_result

    response = api_client.post(
        "/api/v1/interview/evaluate",
        json={
            "question": "Explain REST vs GraphQL",
            "candidate_answer": "REST uses resource-based endpoints.",
            "job_role": "Backend Engineer",
            "required_skills": ["Python"],
        },
    )

    assert response.status_code == 200
    assert response.json()["overall_score"] == valid_evaluation_json["overall_score"]


@patch("api.routes.questions.generate_questions")
def test_questions_generate_endpoint_success(
    mock_generate: MagicMock, api_client, valid_questions_json
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = valid_questions_json
    mock_generate.return_value = mock_result

    response = api_client.post(
        "/api/v1/questions/generate",
        json={
            "resume_json": {"skills": ["Python"]},
            "jd_json": {"required_skills": ["Python"]},
            "match_result_json": {"score": 0.8},
            "difficulty": "medium",
            "question_count": 1,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 1


@patch("api.routes.jd.parse_jd")
def test_jd_parse_endpoint_success(mock_parse_jd: MagicMock, api_client, valid_jd_json):
    mock_parse_jd.return_value = ParsedJD.model_validate(valid_jd_json)

    response = api_client.post(
        "/api/v1/jd/parse",
        json={"jd_text": "We are hiring a backend engineer with Python experience."},
    )

    assert response.status_code == 200
    assert response.json()["role"] == valid_jd_json["role"]


@patch("api.routes.matching.aggregate")
@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
@patch("api.routes.pipeline.parse_jd")
@patch("api.routes.pipeline.process_resume")
def test_pipeline_analyze_happy_path(
    mock_process_resume: MagicMock,
    mock_parse_jd: MagicMock,
    mock_extract_requirements: MagicMock,
    mock_evaluate_hard_requirements: MagicMock,
    mock_evaluate_evidence: MagicMock,
    mock_aggregate: MagicMock,
    api_client,
    valid_jd_json,
    valid_resume_json,
    tmp_path,
):
    mock_process_resume.return_value = ParsedResume.model_validate(valid_resume_json)
    mock_parse_jd.return_value = ParsedJD.model_validate(valid_jd_json)
    # /api/v1/pipeline/analyze's "match" key now comes from the same
    # Recruiter Match pipeline as /api/v1/match (api.routes.matching's
    # _run_recruiter_pipeline) -- mocked here to avoid a real GLM call.
    mock_extract_requirements.return_value = StageAResult(role_archetype="backend", requirements=[])
    mock_evaluate_hard_requirements.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evaluate_evidence.return_value = StageCResult(requirement_scores=[])
    mock_aggregate.return_value = _recruiter_match_result(score=88, recommendation="Strong Hire")

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nJane Doe\nSkills: Python, Docker")

    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/api/v1/pipeline/analyze",
            files={
                "resume_file": ("resume.pdf", handle, "application/pdf"),
            },
            data={"jd_text": "Backend engineer with Python and SQL."},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["resume"]["name"] == valid_resume_json["name"]
    assert body["jd"]["role"] == valid_jd_json["role"]
    assert body["match"]["recruiter_match_score"] == 88
    assert body["match"]["recommendation"] == "Strong Hire"


@patch("api.routes.matching.aggregate")
@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
@patch("api.routes.jd.parse_jd")
@patch("api.routes.resume.process_resume")
def test_full_api_pipeline_sequence(
    mock_resume_route_process_resume: MagicMock,
    mock_jd_route_parse_jd: MagicMock,
    mock_extract_requirements: MagicMock,
    mock_evaluate_hard_requirements: MagicMock,
    mock_evaluate_evidence: MagicMock,
    mock_aggregate: MagicMock,
    api_client,
    valid_jd_json,
    valid_resume_json,
    valid_questions_json,
    valid_evaluation_json,
    tmp_path,
):
    """Exercise the documented curl walkthrough as one chained flow."""
    mock_resume_route_process_resume.return_value = ParsedResume.model_validate(valid_resume_json)
    mock_jd_route_parse_jd.return_value = ParsedJD.model_validate(valid_jd_json)
    # /api/v1/match now runs the Recruiter Match pipeline (two GLM calls) --
    # mocked here so this test exercises routing/wiring, not a real network call.
    mock_extract_requirements.return_value = StageAResult(role_archetype="backend", requirements=[])
    mock_evaluate_hard_requirements.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evaluate_evidence.return_value = StageCResult(requirement_scores=[])
    mock_aggregate.return_value = _recruiter_match_result(score=75, recommendation="Consider")

    jd_response = api_client.post(
        "/api/v1/jd/parse",
        json={"jd_text": "Backend engineer with Python and SQL."},
    )
    assert jd_response.status_code == 200
    jd_json = jd_response.json()

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nJane Doe\nSkills: Python, Docker")
    with pdf_path.open("rb") as handle:
        resume_response = api_client.post(
            "/api/v1/resume/parse",
            files={"file": ("resume.pdf", handle, "application/pdf")},
        )
    assert resume_response.status_code == 200
    resume_json = resume_response.json()

    match_response = api_client.post(
        "/api/v1/match",
        json={"resume_json": resume_json, "jd_json": jd_json},
    )
    assert match_response.status_code == 200
    match_json = match_response.json()

    with patch("api.routes.questions.generate_questions") as mock_questions:
        mock_questions.return_value = MagicMock(
            model_dump=lambda: valid_questions_json,
        )
        questions_response = api_client.post(
            "/api/v1/questions/generate",
            json={
                "resume_json": resume_json,
                "jd_json": jd_json,
                "match_result_json": match_json,
                "difficulty": "medium",
                "question_count": 1,
            },
        )
    assert questions_response.status_code == 200

    with patch("api.routes.evaluation.evaluate_answer") as mock_evaluate:
        mock_evaluate.return_value = MagicMock(
            model_dump=lambda: valid_evaluation_json,
        )
        evaluate_response = api_client.post(
            "/api/v1/interview/evaluate",
            json={
                "question": valid_questions_json["questions"][0]["question"],
                "candidate_answer": "REST exposes resources over HTTP.",
                "job_role": jd_json["role"],
                "required_skills": jd_json["required_skills"],
            },
        )
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["overall_score"] == valid_evaluation_json["overall_score"]


@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
@patch("api.routes.jd.parse_jd")
@patch("api.routes.resume.process_resume")
def test_api_pipeline_sequence_surfaces_low_match_gaps(
    mock_resume_route_process_resume: MagicMock,
    mock_jd_route_parse_jd: MagicMock,
    mock_extract_requirements: MagicMock,
    mock_evaluate_hard_requirements: MagicMock,
    mock_evaluate_evidence: MagicMock,
    api_client,
    valid_jd_json,
    valid_resume_json,
    tmp_path,
):
    """Chain parse + match and assert missing required skills drive a low Recruiter Match Score.

    Only the GLM-calling steps (requirement extraction, evidence
    evaluation) are mocked -- the deterministic scoring step
    (api.routes.matching.aggregate) runs for real here, so this still
    exercises the actual scoring math, not just a canned result.
    """
    resume_json = {**valid_resume_json, "skills": ["HTML"], "projects": [], "experience": []}
    jd_json = {
        **valid_jd_json,
        "required_skills": ["Python", "SQL", "Docker"],
        "preferred_skills": ["Kubernetes"],
    }
    mock_resume_route_process_resume.return_value = ParsedResume.model_validate(resume_json)
    mock_jd_route_parse_jd.return_value = ParsedJD.model_validate(jd_json)

    requirements = [
        Requirement(id="req_1", text="Python", is_required=True, category="Backend Engineering",
                    difficulty_tier="medium", why_it_matters="Core language"),
        Requirement(id="req_2", text="SQL", is_required=True, category="Databases",
                    difficulty_tier="easy", why_it_matters="Core datastore skill"),
        Requirement(id="req_3", text="Docker", is_required=True, category="DevOps & CI/CD",
                    difficulty_tier="medium", why_it_matters="Deployment"),
        Requirement(id="req_4", text="Kubernetes", is_required=False, category="Cloud & Infrastructure",
                    difficulty_tier="hard", why_it_matters="Nice to have"),
    ]
    mock_extract_requirements.return_value = StageAResult(role_archetype="backend", requirements=requirements)
    mock_evaluate_hard_requirements.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evaluate_evidence.return_value = StageCResult(requirement_scores=[
        RequirementScore(requirement_id=req.id, score=0, evidence=[], reasoning="No evidence found.")
        for req in requirements
    ])

    jd_response = api_client.post(
        "/api/v1/jd/parse",
        json={"jd_text": "Backend engineer with Python, SQL, Docker, and Kubernetes."},
    )
    assert jd_response.status_code == 200

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nJane Doe\nSkills: HTML")
    with pdf_path.open("rb") as handle:
        resume_response = api_client.post(
            "/api/v1/resume/parse",
            files={"file": ("resume.pdf", handle, "application/pdf")},
        )
    assert resume_response.status_code == 200

    match_response = api_client.post(
        "/api/v1/match",
        json={"resume_json": resume_response.json(), "jd_json": jd_response.json()},
    )

    assert match_response.status_code == 200
    match_json = match_response.json()
    # All required skills are missing -- the real (unmocked) deterministic
    # scoring step should reflect that as a low score and a weak/no-hire
    # recommendation.
    assert match_json["recruiter_match_score"] < 50
    assert match_json["recommendation"] in ("Weak Match", "Not Recommended")
    missing_texts = {item["text"] for item in match_json["requirement_breakdown"] if item["is_missing"]}
    assert missing_texts == {"Python", "SQL", "Docker", "Kubernetes"}


@patch("api.routes.resume.process_resume")
def test_api_pipeline_stops_when_resume_parse_fails(
    mock_resume_route_process_resume: MagicMock,
    api_client,
    tmp_path,
):
    """A failed resume parse should return a clean error before match/questions."""
    mock_resume_route_process_resume.side_effect = FileValidationError("resume is encrypted")

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nencrypted")
    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/api/v1/resume/parse",
            files={"file": ("resume.pdf", handle, "application/pdf")},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error_type": "FileValidationError",
        "detail": "resume is encrypted",
    }


@patch("api.routes.pipeline.parse_jd")
@patch("api.routes.pipeline.process_resume")
def test_pipeline_analyze_returns_jd_error_after_resume_parse(
    mock_process_resume: MagicMock,
    mock_parse_jd: MagicMock,
    api_client,
    valid_resume_json,
    tmp_path,
):
    mock_process_resume.return_value = ParsedResume.model_validate(valid_resume_json)
    mock_parse_jd.side_effect = JDParsingError("JD text is too vague")

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nJane Doe\nSkills: Python")
    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/api/v1/pipeline/analyze",
            files={"resume_file": ("resume.pdf", handle, "application/pdf")},
            data={"jd_text": "Hiring."},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error_type": "JDParsingError",
        "detail": "JD text is too vague",
    }
    mock_process_resume.assert_called_once()
    mock_parse_jd.assert_called_once_with("Hiring.")


@patch("api.routes.matching.aggregate")
@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
@patch("api.routes.evaluation.evaluate_answer")
@patch("api.routes.questions.generate_questions")
@patch("api.routes.jd.parse_jd")
@patch("api.routes.resume.process_resume")
def test_full_api_pipeline_stops_when_question_generation_fails(
    mock_resume_route_process_resume: MagicMock,
    mock_jd_route_parse_jd: MagicMock,
    mock_generate_questions: MagicMock,
    mock_evaluate_answer: MagicMock,
    mock_extract_requirements: MagicMock,
    mock_evaluate_hard_requirements: MagicMock,
    mock_evaluate_evidence: MagicMock,
    mock_aggregate: MagicMock,
    api_client,
    valid_jd_json,
    valid_resume_json,
    tmp_path,
):
    mock_resume_route_process_resume.return_value = ParsedResume.model_validate(valid_resume_json)
    mock_jd_route_parse_jd.return_value = ParsedJD.model_validate(valid_jd_json)
    mock_generate_questions.side_effect = GLMQuestionGenerationError("question service unavailable")
    mock_extract_requirements.return_value = StageAResult(role_archetype="backend", requirements=[])
    mock_evaluate_hard_requirements.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evaluate_evidence.return_value = StageCResult(requirement_scores=[])
    mock_aggregate.return_value = _recruiter_match_result(score=70, recommendation="Consider")

    jd_response = api_client.post("/api/v1/jd/parse", json={"jd_text": "Backend engineer."})
    assert jd_response.status_code == 200

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nJane Doe\nSkills: Python, Docker")
    with pdf_path.open("rb") as handle:
        resume_response = api_client.post(
            "/api/v1/resume/parse",
            files={"file": ("resume.pdf", handle, "application/pdf")},
        )
    assert resume_response.status_code == 200

    match_response = api_client.post(
        "/api/v1/match",
        json={"resume_json": resume_response.json(), "jd_json": jd_response.json()},
    )
    assert match_response.status_code == 200

    questions_response = api_client.post(
        "/api/v1/questions/generate",
        json={
            "resume_json": resume_response.json(),
            "jd_json": jd_response.json(),
            "match_result_json": match_response.json(),
            "difficulty": "medium",
            "question_count": 1,
        },
    )

    assert questions_response.status_code == 422
    assert questions_response.json() == {
        "error_type": "GLMQuestionGenerationError",
        "detail": "question service unavailable",
    }
    mock_evaluate_answer.assert_not_called()
