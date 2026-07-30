"""
Stage A of the Recruiter Intelligence Engine: JD requirement extraction.

Runs on the JD ALONE, before any resume is shown — deliberately, to avoid
anchoring bias where a strong or weak candidate could subtly influence how
"important" a requirement is judged to be (see the approved plan).

Reuses semantic_matching's GLM config and retry/validation plumbing rather
than reimplementing it, per the plan's migration strategy. Does not touch
matching_engine or semantic_matching's own contracts.

Pipeline within this one LLM call:
    ParsedJD (already has required_skills/preferred_skills split by
    jd_parsing, Phase 1)
        -> build_requirement_extraction_prompt() consults the skill ontology
           for a base_difficulty hint per skill
        -> one GLM call -> StageALLMResponse (validated, retried once)
        -> resolve_requirements() matches each judgment back to its source
           list by text (not position), assigns stable ids, and fills in a
           safe default for any skill the model dropped
        -> StageAResult
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import httpx
from pydantic import ValidationError as PydanticValidationError

from jd_parsing.schema import ParsedJD
from recruiter_intelligence.exceptions import (
    GLMRequirementExtractionError,
    PromptBuildError,
    RequirementExtractionValidationError,
)
from recruiter_intelligence.schema import (
    Requirement,
    RequirementJudgment,
    StageAResult,
    StageALLMResponse,
)
from recruiter_intelligence.skill_ontology import load_ontology
from semantic_matching.config import get_glm_api_key, get_glm_api_url, get_glm_model

_PROMPT_PATH = Path(__file__).parent / "prompts" / "requirement_extraction_prompt.txt"
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


def build_requirement_extraction_prompt(jd: ParsedJD) -> str:
    """Build the user-facing prompt for Stage A from an already-parsed JD."""
    if not isinstance(jd, ParsedJD):
        raise PromptBuildError(f"Expected a ParsedJD, got {type(jd).__name__}.")

    ontology = load_ontology()
    hint_lines = []
    for skill in [*jd.required_skills, *jd.preferred_skills]:
        base = ontology.base_difficulty(skill)
        if base:
            hint_lines.append(f"  - {skill}: baseline difficulty = {base}")
    hints_section = (
        "\n".join(hint_lines) if hint_lines else "  (no baseline hints available)"
    )

    return (
        f"Role: {jd.role or '(not provided)'}\n"
        f"Experience Level: {jd.experience_level or '(not specified)'}\n"
        f"Education Requirement: {jd.education_requirement or '(not specified)'}\n\n"
        f"Responsibilities (context only, not something to judge individually):\n"
        f"{_format_list(jd.responsibilities)}\n\n"
        f"REQUIRED SKILLS (already classified — judge each, do not reclassify):\n"
        f"{_format_list(jd.required_skills)}\n\n"
        f"PREFERRED SKILLS (already classified — judge each, do not reclassify):\n"
        f"{_format_list(jd.preferred_skills)}\n\n"
        f"BASELINE DIFFICULTY HINTS (from the skill ontology, starting points only):\n"
        f"{hints_section}\n"
    )


# ── GLM call ─────────────────────────────────────────────────────────────


def _load_system_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GLMRequirementExtractionError(
            f"Failed to load requirement extraction prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def extract_requirements_text(jd: ParsedJD, *, strict: bool = False) -> str:
    """One raw GLM call. Returns unvalidated JSON text."""
    user_prompt = build_requirement_extraction_prompt(jd)
    system_prompt = _load_system_prompt()
    if strict:
        system_prompt += (
            "\n\nIMPORTANT: Return ONLY valid JSON. Do not include markdown, "
            "explanations, comments, or code fences. Every skill given to "
            "you must appear exactly once in requirement_judgments."
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
        raise GLMRequirementExtractionError(
            f"GLM API returned HTTP {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GLMRequirementExtractionError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GLMRequirementExtractionError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise GLMRequirementExtractionError("GLM API returned empty content.")

    return str(content)


# ── Output validation with retry ────────────────────────────────────────────


def strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    return match.group(1).strip() if match else stripped


def validate_stage_a_json(raw_json: str) -> StageALLMResponse:
    if not isinstance(raw_json, str) or not raw_json.strip():
        raise RequirementExtractionValidationError("Cannot validate empty response.")

    cleaned = strip_markdown_fences(raw_json)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RequirementExtractionValidationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise RequirementExtractionValidationError(
            f"Expected JSON object at root, got {type(data).__name__}."
        )

    try:
        return StageALLMResponse.model_validate(data)
    except PydanticValidationError as exc:
        raise RequirementExtractionValidationError(f"Schema validation failed: {exc}") from exc


def validate_with_retry(generate_once: Callable[[bool], str]) -> StageALLMResponse:
    last_error: RequirementExtractionValidationError | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        raw_json = generate_once(attempt > 1)
        try:
            return validate_stage_a_json(raw_json)
        except RequirementExtractionValidationError as exc:
            last_error = exc

    assert last_error is not None
    raise RequirementExtractionValidationError(
        f"Requirement extraction validation failed after {_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


# ── Orchestration: resolve LLM judgments back against the source lists ─────


def _normalize_for_match(skill: str) -> str:
    return re.sub(r"\s+", " ", skill.strip().lower())


def _default_judgment(skill: str) -> RequirementJudgment:
    """Safe fallback for a skill the model dropped from its response."""
    base_difficulty = load_ontology().base_difficulty(skill)
    return RequirementJudgment(
        skill=skill,
        category="Other",
        difficulty_tier=base_difficulty or "medium",
        why_it_matters="(no model judgment provided; using a neutral default)",
    )


def resolve_requirements(jd: ParsedJD, llm_response: StageALLMResponse) -> StageAResult:
    """
    Match each LLM judgment back to its source list by normalized text
    (never by position — a dropped or reordered item must not silently
    misalign everything after it), assign stable sequential ids, and fill
    in a default judgment for anything the model missed.
    """
    ontology = load_ontology()
    judgments_by_skill = {
        _normalize_for_match(j.skill): j for j in llm_response.requirement_judgments
    }

    requirements: list[Requirement] = []
    next_id = 1
    for is_required, source_list in (
        (True, jd.required_skills), (False, jd.preferred_skills),
    ):
        for skill in source_list:
            judgment = judgments_by_skill.get(_normalize_for_match(skill)) or _default_judgment(skill)
            requirements.append(Requirement(
                id=f"req_{next_id}",
                text=skill,
                is_required=is_required,
                category=judgment.category,
                difficulty_tier=judgment.difficulty_tier,
                why_it_matters=judgment.why_it_matters,
                ontology_base_difficulty=ontology.base_difficulty(skill),
            ))
            next_id += 1

    return StageAResult(role_archetype=llm_response.role_archetype, requirements=requirements)


def extract_requirements(jd: ParsedJD) -> StageAResult:
    """
    Public entry point: extract role_archetype and per-requirement judgments
    for an already-parsed JD, resolved against its own required/preferred
    skill lists.
    """
    llm_response = validate_with_retry(lambda strict: extract_requirements_text(jd, strict=strict))
    return resolve_requirements(jd, llm_response)
