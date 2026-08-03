"""Tests for centralized API exception handlers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from answer_evaluation.exceptions import AnswerEvaluationError
from api.exception_handlers import register_exception_handlers
from jd_parsing.exceptions import JDParsingError
from matching_engine.exceptions import MatchingEngineError
from recruiter_intelligence.exceptions import RecruiterIntelligenceError
from semantic_matching.exceptions import SemanticMatchValidationError


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/matching-error")
    def matching_error():
        raise MatchingEngineError("resume_json must be a dict")

    @app.get("/jd-error")
    def jd_error():
        raise JDParsingError("GLM API call failed")

    @app.get("/evaluation-error")
    def evaluation_error():
        raise AnswerEvaluationError("Cannot evaluate an empty candidate answer.")

    @app.get("/recruiter-intelligence-error")
    def recruiter_intelligence_error():
        raise RecruiterIntelligenceError("GLM API returned HTTP 429")

    @app.get("/semantic-match-error")
    def semantic_match_error():
        raise SemanticMatchValidationError("Semantic match schema validation failed")

    @app.get("/unexpected-error")
    def unexpected_error():
        raise RuntimeError("something broke internally")

    return app


def test_client_facing_errors_return_422_with_error_type():
    client = TestClient(_build_test_app())

    response = client.get("/matching-error")

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "MatchingEngineError"
    assert "resume_json" in body["detail"]


def test_jd_parsing_errors_use_same_error_shape():
    client = TestClient(_build_test_app())

    response = client.get("/jd-error")

    assert response.status_code == 422
    assert response.json()["error_type"] == "JDParsingError"


def test_evaluation_errors_use_same_error_shape():
    client = TestClient(_build_test_app())

    response = client.get("/evaluation-error")

    assert response.status_code == 422
    assert response.json()["error_type"] == "AnswerEvaluationError"


def test_recruiter_intelligence_errors_use_same_error_shape():
    client = TestClient(_build_test_app())

    response = client.get("/recruiter-intelligence-error")

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "RecruiterIntelligenceError"
    assert "429" in body["detail"]


def test_semantic_match_errors_use_same_error_shape():
    client = TestClient(_build_test_app())

    response = client.get("/semantic-match-error")

    assert response.status_code == 422
    assert response.json()["error_type"] == "SemanticMatchValidationError"


def test_unhandled_exceptions_return_500_without_leaking_internals():
    client = TestClient(_build_test_app(), raise_server_exceptions=False)

    response = client.get("/unexpected-error")

    assert response.status_code == 500
    body = response.json()
    assert body["error_type"] == "InternalServerError"
    assert body["detail"] == "An unexpected error occurred."
