"""
Main orchestrator for question generation.

This module owns the GLM call and wires together prompt building and output
validation. It does not parse resumes, parse JDs, compute matching, store data,
or handle Streamlit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from question_generation.config import get_glm_api_key, get_glm_api_url, get_glm_model
from question_generation.exceptions import GLMQuestionGenerationError
from question_generation.output_validator import validate_with_retry
from question_generation.prompt_builder import build_question_prompt
from question_generation.schema import GeneratedQuestions

_PROMPT_PATH = Path(__file__).parent / "prompts" / "question_generation_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEMPERATURE = 0.4


def _load_system_prompt() -> str:
    """Load the system prompt from disk."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GLMQuestionGenerationError(
            f"Failed to load question generation prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def _call_glm(final_prompt: str) -> str:
    """
    Send the final prompt to GLM and return raw model content.

    Raises:
        GLMQuestionGenerationError: If the API call fails or the response shape
        is not usable.
    """
    payload = {
        "model": get_glm_model(),
        "messages": [
            {"role": "system", "content": _load_system_prompt()},
            {"role": "user", "content": final_prompt},
        ],
        "temperature": _DEFAULT_TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {get_glm_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            get_glm_api_url(),
            headers=headers,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GLMQuestionGenerationError(
            f"GLM API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GLMQuestionGenerationError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GLMQuestionGenerationError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise GLMQuestionGenerationError("GLM API returned empty content.")

    return str(content)


def generate_questions(
    resume_json: dict[str, Any],
    jd_json: dict[str, Any],
    match_result_json: dict[str, Any],
    difficulty: str,
    question_count: int,
) -> GeneratedQuestions:
    """
    Generate personalized interview questions.

    Args:
        resume_json: Parsed resume JSON from the resume module.
        jd_json: Parsed JD JSON from the JD parser.
        match_result_json: Match result JSON from the matching engine.
        difficulty: Requested difficulty: easy, medium, or hard.
        question_count: Number of questions to generate.

    Returns:
        Validated ``GeneratedQuestions``.
    """
    final_prompt = build_question_prompt(
        resume_json=resume_json,
        jd_json=jd_json,
        match_result_json=match_result_json,
        difficulty=difficulty,
        question_count=question_count,
    )

    return validate_with_retry(
        lambda: _call_glm(final_prompt), question_count=question_count
    )
