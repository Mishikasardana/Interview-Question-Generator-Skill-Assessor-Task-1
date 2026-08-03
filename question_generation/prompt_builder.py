"""
Prompt builder for personalized interview question generation.

This module prepares the final user prompt sent to GLM. It does not call the
model and does not validate model output.
"""

from __future__ import annotations

import json
from typing import Any

from question_generation.exceptions import PromptBuildError

_ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}


def _ensure_json_object(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate that an input is a JSON-like dictionary."""
    if not isinstance(value, dict):
        raise PromptBuildError(
            f"Expected {field_name} to be a dict, got {type(value).__name__}."
        )
    return value


def _normalize_difficulty(difficulty: str) -> str:
    """Validate and normalize the requested question difficulty."""
    if not isinstance(difficulty, str):
        raise PromptBuildError(
            f"Expected difficulty to be a str, got {type(difficulty).__name__}."
        )

    normalized = difficulty.strip().lower()
    if normalized not in _ALLOWED_DIFFICULTIES:
        allowed = ", ".join(sorted(_ALLOWED_DIFFICULTIES))
        raise PromptBuildError(
            f"Difficulty must be one of: {allowed}. Got: {difficulty!r}."
        )
    return normalized


def _normalize_question_count(question_count: int) -> int:
    """Validate the requested number of questions."""
    if not isinstance(question_count, int) or isinstance(question_count, bool):
        raise PromptBuildError(
            "Expected question_count to be an int, "
            f"got {type(question_count).__name__}."
        )

    if question_count < 1 or question_count > 20:
        raise PromptBuildError("question_count must be between 1 and 20.")
    return question_count


def build_question_prompt(
    resume_json: dict[str, Any],
    jd_json: dict[str, Any],
    match_result_json: dict[str, Any],
    difficulty: str,
    question_count: int,
) -> str:
    """
    Build the final prompt for GLM.

    Args:
        resume_json: Parsed resume JSON from the resume module.
        jd_json: Parsed job description JSON from the JD parser.
        match_result_json: Match result JSON from the matching engine.
        difficulty: Requested difficulty: easy, medium, or hard.
        question_count: Number of questions to generate.

    Returns:
        A prompt string containing all generation inputs.

    Raises:
        PromptBuildError: If any input has an invalid type or value.
    """
    resume = _ensure_json_object(resume_json, "resume_json")
    jd = _ensure_json_object(jd_json, "jd_json")
    match_result = _ensure_json_object(match_result_json, "match_result_json")
    normalized_difficulty = _normalize_difficulty(difficulty)
    normalized_count = _normalize_question_count(question_count)

    payload = {
        "parsed_resume": resume,
        "parsed_jd": jd,
        "match_result": match_result,
        "difficulty": normalized_difficulty,
        "question_count": normalized_count,
    }

    return (
        "Generate personalized interview questions using the input JSON below.\n"
        "Return only valid JSON that matches the required output schema.\n\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}"
    )
