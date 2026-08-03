"""
Request/response models for the API layer.

These are separate from each module's internal ``schema.py`` (e.g.
``resume_processing.schema.ParsedResume``) on purpose: the API contract
should be free to evolve (add pagination, wrap in an envelope, rename a
request field) without forcing changes on the internal processing modules,
and vice versa.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, StrictInt


class ErrorResponse(BaseModel):
    """Uniform error shape returned by every endpoint on failure."""

    error_type: str
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "Interview Intelligence Platform API"


# ── JD Parsing ────────────────────────────────────────────────────────────


class JDParseRequest(BaseModel):
    jd_text: str = Field(..., min_length=1, description="Raw job description text.")


# ── Matching Engine ─────────────────────────────────────────────────────────


class MatchRequest(BaseModel):
    resume_json: dict[str, Any] = Field(
        ..., description="Parsed resume JSON (output of /resume/parse)."
    )
    jd_json: dict[str, Any] = Field(
        ..., description="Parsed JD JSON (output of /jd/parse)."
    )


# ── Question Generation ─────────────────────────────────────────────────────


class QuestionGenerateRequest(BaseModel):
    resume_json: dict[str, Any]
    jd_json: dict[str, Any]
    match_result_json: dict[str, Any]
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    question_count: StrictInt = Field(default=5, ge=1, le=20)


# ── Answer Evaluation ────────────────────────────────────────────────────────


class EvaluateAnswerRequest(BaseModel):
    question: str = Field(..., min_length=1)
    candidate_answer: str = Field(..., min_length=1)
    job_role: str = ""
    required_skills: list[str] = Field(default_factory=list)


# ── Combined pipeline ────────────────────────────────────────────────────────


class PipelineAnalyzeResponse(BaseModel):
    resume: dict[str, Any]
    jd: dict[str, Any]
    match: dict[str, Any]
