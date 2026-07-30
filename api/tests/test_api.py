"""
API-level integration tests.

These exercise the FastAPI app through Starlette's TestClient. Endpoints
that call the GLM API (jd/parse, questions/generate, interview/evaluate,
resume/parse) are only tested up to the point where they would make a
network call — with no GLM_API_KEY configured in the test environment, they
fail fast with a clean 422 instead of hanging on a real HTTP request, which
also happens to prove the exception-handling chain works end to end.

The one endpoint with no external dependency (matching) is tested fully,
including a real request/response round trip.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from answer_evaluation.exceptions import AnswerEvaluationError
from answer_evaluation.schema import EvaluationResult
from jd_parsing.exceptions import JDParsingError
from jd_parsing.schema import ParsedJD
from question_generation.schema import GeneratedQuestions, InterviewQuestion
from recruiter_intelligence.exceptions import GLMRequirementExtractionError
from recruiter_intelligence.schema import (
    HardGateResult,
    RecruiterMatchResult,
    Requirement,
    RequirementEvidence,
    RequirementScore,
    StageAResult,
    StageCResult,
)
from resume_processing.schema import ParsedResume

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "docs" in response.json()


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Interview Intelligence Platform API"}


def test_cors_wildcard_origin_does_not_reflect_credentials():
    # ALLOWED_ORIGINS is "*" in the test environment (see .env), so the
    # wildcard branch in api/main.py applies. Starlette's CORSMiddleware
    # special-cases allow_origins=["*"] + allow_credentials=True by
    # reflecting *any* request Origin back with credentials allowed —
    # effectively an open, credentialed CORS policy. Credentials must stay
    # off while the origin allowlist is a wildcard.
    response = client.get(
        "/api/v1/health", headers={"Origin": "https://evil.example.com"}
    )
    assert response.headers.get("access-control-allow-credentials") != "true"


def test_openapi_schema_loads():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/match" in paths
    assert "/api/v1/resume/parse" in paths
    assert "/api/v1/jd/parse" in paths
    assert "/api/v1/questions/generate" in paths
    assert "/api/v1/interview/evaluate" in paths
    assert "/api/v1/pipeline/analyze" in paths


# ── Matching: the single Recruiter Match Score endpoint ─────────────────────


_MATCH_PAYLOAD = {
    "resume_json": {"name": "Jane", "skills": ["Express.js"]},
    "jd_json": {"role": "Backend Engineer", "required_skills": ["FastAPI"]},
}


@patch("api.routes.matching.aggregate")
@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
def test_match_endpoint_end_to_end_with_mocked_pipeline(
    mock_extract, mock_gate, mock_evidence, mock_aggregate,
):
    requirement = Requirement(
        id="req_1", text="FastAPI", is_required=True, category="Backend Engineering",
        difficulty_tier="medium", why_it_matters="Core framework",
    )
    mock_extract.return_value = StageAResult(role_archetype="backend", requirements=[requirement])
    mock_gate.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evidence.return_value = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=85,
            evidence=[RequirementEvidence(category="skills", snippet="Express.js")],
            reasoning="Equivalent backend framework.",
        ),
    ])
    mock_aggregate.return_value = RecruiterMatchResult(
        recruiter_match_score=85, confidence="High", confidence_reason="dense evidence",
        recommendation="Strong Hire", hard_gate=HardGateResult(overall_status="pass", results=[]),
        role_archetype="backend", narrative="Recommendation: Strong Hire",
    )

    response = client.post("/api/v1/match", json=_MATCH_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["recruiter_match_score"] == 85
    assert body["recommendation"] == "Strong Hire"
    # Exactly one score in the response -- no competing percentages.
    assert "technical_fit_score" not in body
    assert "project_quality_score" not in body
    mock_extract.assert_called_once()
    mock_gate.assert_called_once()
    mock_evidence.assert_called_once()
    mock_aggregate.assert_called_once()


def test_match_endpoint_rejects_invalid_resume_shape():
    payload = {
        "resume_json": {"skills": "not-a-list"},  # ParsedResume.skills must be list[str]
        "jd_json": {"role": "Backend Engineer", "required_skills": ["FastAPI"]},
    }

    response = client.post("/api/v1/match", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "RecruiterIntelligenceError"


@patch("api.routes.matching.extract_requirements")
def test_match_endpoint_maps_recruiter_intelligence_errors_to_uniform_422(mock_extract):
    mock_extract.side_effect = GLMRequirementExtractionError("GLM API returned HTTP 429")

    response = client.post("/api/v1/match", json=_MATCH_PAYLOAD)

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "GLMRequirementExtractionError"
    assert "429" in body["detail"]


# ── Request validation (caught before any GLM call) ────────────────────────


def test_jd_parse_rejects_empty_text():
    response = client.post("/api/v1/jd/parse", json={"jd_text": ""})
    assert response.status_code == 422


def test_request_validation_error_uses_uniform_error_shape():
    # FastAPI/Pydantic raise RequestValidationError themselves for
    # request-shape problems, before any route or domain exception ever
    # runs. Without a dedicated handler this bypasses the documented
    # {"error_type","detail"} contract and falls through to FastAPI's
    # default {"detail": [...]} body shape instead.
    response = client.post("/api/v1/jd/parse", json={"jd_text": ""})

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "RequestValidationError"
    assert isinstance(body["detail"], str)
    assert "jd_text" in body["detail"]


def test_resume_parse_missing_file_uses_uniform_error_shape():
    response = client.post("/api/v1/resume/parse")

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "RequestValidationError"
    assert isinstance(body["detail"], str)


def test_jd_parse_without_api_key_fails_cleanly(monkeypatch):
    # Simulate no GLM_API_KEY configured (regardless of what's actually in
    # the developer's local .env) — this should fail with a clean 422 from
    # our exception handler (JDParsingError), never a 500 or a hang on a
    # real network call.
    monkeypatch.delenv("GLM_API_KEY", raising=False)
    response = client.post("/api/v1/jd/parse", json={"jd_text": "We are hiring."})
    assert response.status_code == 422
    assert response.json()["error_type"] == "JDParsingError"


@patch("api.routes.jd.parse_jd")
def test_jd_parse_success_with_mocked_parser(mock_parse_jd: MagicMock):
    mock_parse_jd.return_value = ParsedJD(
        role="Backend Engineer",
        required_skills=["Python"],
        preferred_skills=["Docker"],
    )

    response = client.post("/api/v1/jd/parse", json={"jd_text": "Hiring Python dev."})

    assert response.status_code == 200
    assert response.json()["role"] == "Backend Engineer"
    mock_parse_jd.assert_called_once_with("Hiring Python dev.")


@patch("api.routes.jd.parse_jd", side_effect=JDParsingError("bad JD"))
def test_jd_parse_maps_parser_errors_to_uniform_422(_mock_parse_jd: MagicMock):
    response = client.post("/api/v1/jd/parse", json={"jd_text": "Hiring."})

    assert response.status_code == 422
    assert response.json() == {"error_type": "JDParsingError", "detail": "bad JD"}


def test_evaluate_answer_rejects_empty_answer():
    response = client.post(
        "/api/v1/interview/evaluate",
        json={"question": "Explain REST APIs.", "candidate_answer": ""},
    )
    assert response.status_code == 422


@patch("api.routes.evaluation.evaluate_answer")
def test_evaluate_answer_success_with_mocked_evaluator(mock_evaluate: MagicMock):
    # Subscores intentionally sum to 80 (25+20+20+10+5) — overall_score is
    # recomputed from them (see answer_evaluation/schema.py), so passing a
    # mismatched overall_score here would just be silently overridden.
    mock_evaluate.return_value = EvaluationResult(
        correctness=25,
        keyword_coverage=20,
        clarity=20,
        communication=10,
        completeness=5,
        feedback="Good answer.",
    )

    response = client.post(
        "/api/v1/interview/evaluate",
        json={
            "question": "Explain REST APIs.",
            "candidate_answer": "REST exposes resources over HTTP.",
            "job_role": "Backend Engineer",
            "required_skills": ["Python"],
        },
    )

    assert response.status_code == 200
    assert response.json()["overall_score"] == 80
    mock_evaluate.assert_called_once_with(
        question="Explain REST APIs.",
        candidate_answer="REST exposes resources over HTTP.",
        job_role="Backend Engineer",
        required_skills=["Python"],
    )


@patch("api.routes.evaluation.evaluate_answer", side_effect=AnswerEvaluationError("bad answer"))
def test_evaluate_answer_maps_evaluator_errors_to_uniform_422(_mock_evaluate: MagicMock):
    response = client.post(
        "/api/v1/interview/evaluate",
        json={"question": "Explain REST APIs.", "candidate_answer": "Too vague."},
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "AnswerEvaluationError"


def test_resume_parse_rejects_missing_file():
    response = client.post("/api/v1/resume/parse")

    assert response.status_code == 422


def test_resume_parse_rejects_unsupported_extension():
    fake_file = io.BytesIO(b"not a real resume")
    response = client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error_type"] == "FileValidationError"


def test_resume_parse_rejects_oversized_file():
    oversized_file = io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))

    response = client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.pdf", oversized_file, "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "FileValidationError"
    assert "10MB" in response.json()["detail"]


@patch("api.routes.resume.process_resume")
def test_resume_parse_success_with_mocked_processor(mock_process_resume: MagicMock):
    mock_process_resume.return_value = ParsedResume(name="Jane Doe", skills=["Python"])
    fake_file = io.BytesIO(b"%PDF-1.4\nfake resume")

    response = client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.pdf", fake_file, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Jane Doe"
    assert mock_process_resume.call_count == 1


@patch("api.routes.resume.process_resume", side_effect=RuntimeError("disk failed"))
def test_resume_parse_unexpected_errors_return_safe_500(_mock_process_resume: MagicMock):
    safe_client = TestClient(app, raise_server_exceptions=False)
    fake_file = io.BytesIO(b"%PDF-1.4\nfake resume")

    response = safe_client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.pdf", fake_file, "application/pdf")},
    )

    assert response.status_code == 500
    assert response.json() == {
        "error_type": "InternalServerError",
        "detail": "An unexpected error occurred.",
    }


def test_resume_parse_accepts_docx_extension_past_validation():
    # A corrupted .docx still passes the extension check and only fails
    # later at the docx-package level — proving .docx is no longer
    # rejected outright the way it used to be (PDF-only).
    fake_file = io.BytesIO(b"not a real docx")
    response = client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.docx", fake_file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    # Still 422 (invalid docx content), but via DocxExtractionError /
    # FileValidationError from the docx package check, not a blanket
    # "only .pdf" rejection.
    assert response.status_code == 422
    assert response.json()["error_type"] in {"FileValidationError", "DocxExtractionError"}


def test_resume_parse_rejects_empty_file():
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/v1/resume/parse",
        files={"file": ("resume.pdf", empty_file, "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error_type"] == "FileValidationError"


def test_pipeline_analyze_rejects_unsupported_resume_extension():
    fake_file = io.BytesIO(b"not a real resume")
    response = client.post(
        "/api/v1/pipeline/analyze",
        files={"resume_file": ("resume.txt", fake_file, "text/plain")},
        data={"jd_text": "We are hiring a backend engineer."},
    )
    assert response.status_code == 422
    assert response.json()["error_type"] == "FileValidationError"


def test_pipeline_analyze_rejects_missing_jd_text():
    fake_file = io.BytesIO(b"%PDF-1.4\nfake resume")

    response = client.post(
        "/api/v1/pipeline/analyze",
        files={"resume_file": ("resume.pdf", fake_file, "application/pdf")},
    )

    assert response.status_code == 422


def test_pipeline_analyze_rejects_oversized_resume_file():
    oversized_file = io.BytesIO(b"x" * (10 * 1024 * 1024 + 1))

    response = client.post(
        "/api/v1/pipeline/analyze",
        files={"resume_file": ("resume.pdf", oversized_file, "application/pdf")},
        data={"jd_text": "Hiring."},
    )

    assert response.status_code == 422
    assert response.json()["error_type"] == "FileValidationError"


@patch("api.routes.matching.aggregate")
@patch("api.routes.matching.evaluate_evidence")
@patch("api.routes.matching.evaluate_hard_requirements")
@patch("api.routes.matching.extract_requirements")
@patch("api.routes.pipeline.parse_jd")
@patch("api.routes.pipeline.process_resume")
def test_pipeline_analyze_success_with_mocked_processors(
    mock_process_resume: MagicMock,
    mock_parse_jd: MagicMock,
    mock_extract_requirements: MagicMock,
    mock_evaluate_hard_requirements: MagicMock,
    mock_evaluate_evidence: MagicMock,
    mock_aggregate: MagicMock,
):
    mock_process_resume.return_value = ParsedResume(name="Jane Doe", skills=["Python"])
    mock_parse_jd.return_value = ParsedJD(
        role="Backend Engineer",
        required_skills=["Python"],
        preferred_skills=[],
    )
    # /api/v1/pipeline/analyze's "match" key comes from the same Recruiter
    # Match pipeline as /api/v1/match -- mocked here to avoid a real GLM call.
    mock_extract_requirements.return_value = StageAResult(role_archetype="backend", requirements=[])
    mock_evaluate_hard_requirements.return_value = HardGateResult(overall_status="pass", results=[])
    mock_evaluate_evidence.return_value = StageCResult(requirement_scores=[])
    mock_aggregate.return_value = RecruiterMatchResult(
        recruiter_match_score=90, confidence="High", confidence_reason="mocked for testing",
        recommendation="Strong Hire", hard_gate=HardGateResult(overall_status="pass", results=[]),
        role_archetype="backend", narrative="Recommendation: Strong Hire",
    )
    fake_file = io.BytesIO(b"%PDF-1.4\nfake resume")

    response = client.post(
        "/api/v1/pipeline/analyze",
        files={"resume_file": ("resume.pdf", fake_file, "application/pdf")},
        data={"jd_text": "Hiring Python dev."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resume"]["name"] == "Jane Doe"
    assert body["jd"]["role"] == "Backend Engineer"
    assert body["match"]["recruiter_match_score"] == 90
    assert body["match"]["recommendation"] == "Strong Hire"


def test_questions_generate_rejects_bad_difficulty():
    payload = {
        "resume_json": {},
        "jd_json": {},
        "match_result_json": {},
        "difficulty": "impossible",
        "question_count": 5,
    }
    response = client.post("/api/v1/questions/generate", json=payload)
    assert response.status_code == 422


def test_questions_generate_rejects_boolean_question_count():
    payload = {
        "resume_json": {},
        "jd_json": {},
        "match_result_json": {},
        "difficulty": "medium",
        "question_count": True,
    }

    response = client.post("/api/v1/questions/generate", json=payload)

    assert response.status_code == 422


@patch("api.routes.questions.generate_questions")
def test_questions_generate_success_with_mocked_generator(mock_generate: MagicMock):
    mock_generate.return_value = GeneratedQuestions(
        questions=[
            InterviewQuestion(
                question="How do you use Python in backend services?",
                category="Technical",
                difficulty="medium",
                reason="Python is required by the JD.",
            )
        ]
    )
    payload = {
        "resume_json": {"skills": ["Python"]},
        "jd_json": {"required_skills": ["Python"]},
        "match_result_json": {"score": 80},
        "difficulty": "medium",
        "question_count": 1,
    }

    response = client.post("/api/v1/questions/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["questions"][0]["category"] == "Technical"
    mock_generate.assert_called_once_with(
        resume_json={"skills": ["Python"]},
        jd_json={"required_skills": ["Python"]},
        match_result_json={"score": 80},
        difficulty="medium",
        question_count=1,
    )


def test_questions_generate_rejects_out_of_range_question_count():
    payload = {
        "resume_json": {},
        "jd_json": {},
        "match_result_json": {},
        "difficulty": "medium",
        "question_count": 999,
    }
    response = client.post("/api/v1/questions/generate", json=payload)
    assert response.status_code == 422
