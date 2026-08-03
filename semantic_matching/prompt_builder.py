"""
Prompt builder for GLM-based semantic match evaluation.

Purpose:
    Format parsed resume + JD JSON into a single, readable user-turn prompt
    so the model can reason over full context (skills, projects, experience
    text, responsibilities) — not just flat skill lists, since that's
    exactly what the deterministic matching_engine's exact-match comparison
    misses.

    This module does not call the model and does not validate model output.

Inputs:
    Parsed resume JSON (resume_processing output) and parsed JD JSON
    (jd_parsing output).

Outputs:
    A single formatted prompt string.

Example usage:
    >>> from semantic_matching.prompt_builder import build_semantic_match_prompt
    >>> prompt = build_semantic_match_prompt(resume_json, jd_json)
"""

from __future__ import annotations

from typing import Any

from semantic_matching.exceptions import PromptBuildError


def _ensure_json_object(value: Any, field_name: str) -> dict[str, Any]:
    """Validate that an input is a JSON-like dictionary."""
    if not isinstance(value, dict):
        raise PromptBuildError(
            f"Expected {field_name} to be a dict, got {type(value).__name__}."
        )
    return value


def _stringify_entry(entry: Any) -> str:
    """
    Render one list entry (a skill/project/experience/education item) as
    text.

    Handles both the flat ``list[str]`` shape resume_processing/jd_parsing
    produce today, and a richer ``list[dict]`` shape (e.g.
    {"role": ..., "description": ...}), so this stays correct if either
    module's schema evolves — mirrors the dict-or-string handling already
    used by matching_engine's free-text scanner.
    """
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        parts = [str(v) for v in entry.values() if isinstance(v, (str, int, float))]
        return " — ".join(parts) if parts else ""
    return str(entry)


def _format_list(label: str, items: list[Any]) -> str:
    if not items:
        return f"{label}: (none listed)"
    rendered = "\n".join(f"  - {_stringify_entry(item)}" for item in items if item)
    return f"{label}:\n{rendered}"


def _format_resume_context(resume: dict[str, Any]) -> str:
    lines = [
        f"Candidate Name: {resume.get('name') or '(not provided)'}",
        _format_list("Listed Skills", resume.get("skills") or []),
        _format_list("Projects", resume.get("projects") or []),
        _format_list("Experience", resume.get("experience") or []),
        _format_list("Education", resume.get("education") or []),
        _format_list("Certifications", resume.get("certifications") or []),
    ]
    return "\n\n".join(lines)


def _format_jd_context(jd: dict[str, Any]) -> str:
    lines = [
        f"Role: {jd.get('role') or '(not provided)'}",
        f"Experience Level: {jd.get('experience_level') or '(not specified)'}",
        f"Education Requirement: {jd.get('education_requirement') or '(not specified)'}",
        _format_list("Required Skills", jd.get("required_skills") or []),
        _format_list("Preferred Skills", jd.get("preferred_skills") or []),
        _format_list("Responsibilities", jd.get("responsibilities") or []),
    ]
    return "\n\n".join(lines)


def build_semantic_match_prompt(resume_json: dict[str, Any], jd_json: dict[str, Any]) -> str:
    """
    Build the final user-turn prompt for GLM semantic match evaluation.

    Args:
        resume_json: Parsed resume JSON (resume_processing output).
        jd_json: Parsed JD JSON (jd_parsing output).

    Returns:
        A prompt string with labeled resume/JD context sections.

    Raises:
        PromptBuildError: If either input is not a dict.
    """
    resume = _ensure_json_object(resume_json, "resume_json")
    jd = _ensure_json_object(jd_json, "jd_json")

    return (
        "Evaluate this candidate's resume against this job description "
        "using the semantic matching rubric in your instructions.\n\n"
        "=== CANDIDATE RESUME ===\n"
        f"{_format_resume_context(resume)}\n\n"
        "=== JOB DESCRIPTION ===\n"
        f"{_format_jd_context(jd)}\n"
    )
