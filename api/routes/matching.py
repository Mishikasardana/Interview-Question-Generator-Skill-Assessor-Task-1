"""
Matching route — compare a parsed resume against a parsed JD.

One endpoint, one score. matching_engine's deterministic score and
semantic_matching's freeform score used to be served here as two
additional routes (/match/semantic, /match/recruiter alongside a bare
/match); both are gone (see the approved "One Recruiter Match Score"
plan). matching_engine/semantic_matching remain importable internally
(benchmark comparison, migration safety net) but are not reachable through
this API anymore.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError as PydanticValidationError

from api.schemas import MatchRequest
from jd_parsing.schema import ParsedJD
from recruiter_intelligence import (
    RecruiterIntelligenceError,
    aggregate,
    evaluate_evidence,
    evaluate_hard_requirements,
    extract_requirements,
)
from resume_processing.schema import ParsedResume

router = APIRouter(prefix="/api/v1/match", tags=["Matching"])


def _run_recruiter_pipeline(resume_json: dict[str, Any], jd_json: dict[str, Any]) -> dict[str, Any]:
    try:
        jd = ParsedJD.model_validate(jd_json)
        resume = ParsedResume.model_validate(resume_json)
    except PydanticValidationError as exc:
        raise RecruiterIntelligenceError(f"Invalid resume_json/jd_json shape: {exc}") from exc

    stage_a = extract_requirements(jd)
    hard_gate = evaluate_hard_requirements(jd, resume)
    stage_c = evaluate_evidence(stage_a, resume)
    result = aggregate(stage_a, stage_c, hard_gate, resume)
    return result.model_dump()


@router.post("", summary="Compute the Recruiter Match Score between a resume and a JD")
async def match_route(payload: MatchRequest) -> dict[str, Any]:
    """
    Compute the single Recruiter Match Score: JD requirement extraction, a
    deterministic hard-requirement gate, per-requirement evidence
    evaluation, and deterministic weighted aggregation — the backend
    computes the score from cited evidence, the LLM never sets it directly.

    Makes two blocking GLM calls (requirement extraction, evidence
    evaluation) — offloaded to a worker thread.
    """
    return await run_in_threadpool(_run_recruiter_pipeline, payload.resume_json, payload.jd_json)
