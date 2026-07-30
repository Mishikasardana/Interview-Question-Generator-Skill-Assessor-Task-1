"""
Evidence Evaluation step of the Recruiter Match pipeline — "the core
accuracy fix" per the approved plan.

Runs after the ontology lookup (a deterministic enrichment step, not a
numbered stage): for every requirement from the Requirement Understanding
step, an evidence shortlist from recruiter_intelligence.skill_ontology is
injected into the prompt so the LLM confirms/refines an already-identified
relationship with real resume evidence rather than re-deriving it from
scratch.

This step never invents an aggregate number — it only scores individual,
fixed requirement_ids with mandatory evidence. It DOES fold project quality
and recency directly into each requirement's score (a weak vs.
production-quality project, or old vs. current evidence, only mean
something in the context of the specific evidence being read, which is
exactly what this step already does) — see the evidence evaluation prompt
and the approved "One Recruiter Match Score" plan, section 3.1/5. Weighting
and aggregation are the deterministic scoring step's job, not this one's.

Reuses semantic_matching's GLM config and mirrors requirement_extraction.py's
retry/validation plumbing exactly, rather than sharing a premature helper —
consistent with this package's existing pattern of small per-stage modules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import httpx
from pydantic import ValidationError as PydanticValidationError

from recruiter_intelligence.exceptions import (
    EvidenceEvaluationValidationError,
    GLMEvidenceEvaluationError,
    PromptBuildError,
)
from recruiter_intelligence.schema import RequirementScore, StageAResult, StageCResult
from recruiter_intelligence.skill_ontology import load_ontology
from resume_processing.schema import ParsedResume
from semantic_matching.config import get_glm_api_key, get_glm_api_url, get_glm_model

_PROMPT_PATH = Path(__file__).parent / "prompts" / "evidence_evaluation_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEMPERATURE = 0.1
_MAX_ATTEMPTS = 2
_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE,
)


# ── Prompt building ─────────────────────────────────────────────────────────


def _format_list(items: list[str]) -> str:
    if not items:
        return "  (none listed)"
    return "\n".join(f"  - {item}" for item in items)


def _format_numbered_list(items: list[str]) -> str:
    if not items:
        return "  (none listed)"
    return "\n".join(f"  [{i}] {item}" for i, item in enumerate(items))


_DECAY_RATE_GUIDANCE = {
    "fast": "this skill area moves quickly -- discount old evidence more than you normally would",
    "moderate": "this skill area moves at a moderate pace",
    "slow": "this skill area is foundational/slow-moving -- old evidence doesn't need much discount",
}


def _format_requirements(stage_a: StageAResult, resume_skills: list[str]) -> str:
    ontology = load_ontology()
    lines: list[str] = []
    for req in stage_a.requirements:
        kind = "REQUIRED" if req.is_required else "PREFERRED"
        lines.append(f'  - id={req.id} [{kind}] "{req.text}" (category: {req.category})')
        candidates = ontology.find_evidence_candidates(req.text, resume_skills)
        if candidates:
            hints = ", ".join(
                f"{c.resume_skill} ({c.relationship.replace('_', ' ')})" for c in candidates[:5]
            )
            lines.append(f"      ontology suggests: {hints}")
        decay_rate = ontology.decay_rate(req.text)
        if decay_rate:
            lines.append(f"      recency guidance: {_DECAY_RATE_GUIDANCE[decay_rate]}")
    return "\n".join(lines) if lines else "  (no requirements)"


def build_evidence_evaluation_prompt(stage_a: StageAResult, resume: ParsedResume) -> str:
    """Build the user-facing prompt for Stage C from Stage A's requirements and the resume."""
    if not isinstance(stage_a, StageAResult):
        raise PromptBuildError(f"Expected a StageAResult, got {type(stage_a).__name__}.")
    if not isinstance(resume, ParsedResume):
        raise PromptBuildError(f"Expected a ParsedResume, got {type(resume).__name__}.")

    return (
        f"ROLE ARCHETYPE: {stage_a.role_archetype}\n\n"
        f"REQUIREMENTS TO SCORE (score every id, do not skip any):\n"
        f"{_format_requirements(stage_a, resume.skills)}\n\n"
        f"CANDIDATE RESUME CONTEXT:\n\n"
        f"Skills:\n{_format_list(resume.skills)}\n\n"
        f"Projects:\n{_format_numbered_list(resume.projects)}\n\n"
        f"Experience:\n{_format_numbered_list(resume.experience)}\n\n"
        f"Education:\n{_format_list(resume.education)}\n\n"
        f"Certifications:\n{_format_list(resume.certifications)}\n"
    )


# ── GLM call ─────────────────────────────────────────────────────────────


def _load_system_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GLMEvidenceEvaluationError(
            f"Failed to load evidence evaluation prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def evaluate_evidence_text(stage_a: StageAResult, resume: ParsedResume, *, strict: bool = False) -> str:
    """One raw GLM call. Returns unvalidated JSON text."""
    user_prompt = build_evidence_evaluation_prompt(stage_a, resume)
    system_prompt = _load_system_prompt()
    if strict:
        system_prompt += (
            "\n\nIMPORTANT: Return ONLY valid JSON. Do not include markdown, "
            "explanations, comments, or code fences. Every requirement id "
            "given to you must appear exactly once in requirement_scores."
        )

    payload = {
        "model": get_glm_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": _DEFAULT_TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {get_glm_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            get_glm_api_url(), headers=headers, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GLMEvidenceEvaluationError(
            f"GLM API returned HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GLMEvidenceEvaluationError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GLMEvidenceEvaluationError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise GLMEvidenceEvaluationError("GLM API returned empty content.")

    return str(content)


# ── Output validation with retry ────────────────────────────────────────────


def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    return match.group(1).strip() if match else stripped


def validate_stage_c_json(raw_json: str) -> StageCResult:
    if not isinstance(raw_json, str) or not raw_json.strip():
        raise EvidenceEvaluationValidationError("Cannot validate empty response.")

    cleaned = strip_markdown_fences(raw_json)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise EvidenceEvaluationValidationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise EvidenceEvaluationValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return StageCResult.model_validate(data)
    except PydanticValidationError as exc:
        raise EvidenceEvaluationValidationError(f"Schema validation failed: {exc}") from exc


def validate_with_retry(generate_once: Callable[[bool], str]) -> StageCResult:
    last_error: EvidenceEvaluationValidationError | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        raw_json = generate_once(attempt > 1)
        try:
            return validate_stage_c_json(raw_json)
        except EvidenceEvaluationValidationError as exc:
            last_error = exc

    assert last_error is not None
    raise EvidenceEvaluationValidationError(
        f"Evidence evaluation validation failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


# ── Orchestration: resolve LLM output back against Stage A and the resume ──


def _default_requirement_score(requirement_id: str) -> RequirementScore:
    """Safe fallback for a requirement id the model dropped from its response."""
    return RequirementScore(
        requirement_id=requirement_id, score=0, evidence=[],
        reasoning="(no model judgment provided; defaulting to no evidence found)",
    )


def resolve_requirement_scores(stage_a: StageAResult, llm_result: StageCResult) -> list[RequirementScore]:
    """
    Guarantee exactly one score per Stage A requirement id, in Stage A's own
    order — matched by id (never by position), with a safe default for
    anything the model dropped, mirroring resolve_requirements() in
    requirement_extraction.py.
    """
    scores_by_id = {score.requirement_id: score for score in llm_result.requirement_scores}
    return [
        scores_by_id.get(req.id) or _default_requirement_score(req.id)
        for req in stage_a.requirements
    ]


def evaluate_evidence(stage_a: StageAResult, resume: ParsedResume) -> StageCResult:
    """
    Public entry point: score every requirement against the resume, using
    the ontology's evidence shortlist and recency guidance where available.
    Project quality and recency are already folded into each score by the
    prompt — nothing further to extract or resolve here.
    """
    llm_result = validate_with_retry(
        lambda strict: evaluate_evidence_text(stage_a, resume, strict=strict)
    )
    return StageCResult(
        requirement_scores=resolve_requirement_scores(stage_a, llm_result),
    )
