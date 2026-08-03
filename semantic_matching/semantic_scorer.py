"""
GLM-based semantic (conceptual) match evaluator module.

Purpose:
    Send resume + JD context to the GLM API and receive a structured,
    explainable semantic match evaluation. This module is isolated — it
    knows about the LLM and prompt, nothing else. It performs exactly one
    API call per invocation; retry logic lives in ``output_validator.py``,
    matching the pattern used everywhere else in this project.

Inputs:
    Parsed resume JSON and parsed JD JSON.

Outputs:
    Raw JSON string from the model (not yet validated).

Example usage:
    >>> from semantic_matching.semantic_scorer import evaluate_semantic_match_text
    >>> raw_json = evaluate_semantic_match_text(resume_json, jd_json)

Design notes:
    - Prompt lives in ``prompts/semantic_match_prompt.txt``, loaded via
      ``Path(__file__).parent`` so it resolves correctly regardless of the
      process's current working directory.
    - Uses ``httpx`` for HTTP calls, same as the rest of the project.
    - This is an ADDITIONAL, separate evaluation alongside
      ``matching_engine.run_matching`` — it does not replace or modify the
      deterministic MatchResult contract that question_generation and the
      UI already depend on.

Assumptions:
    - GLM API credentials are configured via ``config.py``.
    - Model is instructed to return JSON only (no markdown, no explanations).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from semantic_matching.config import get_glm_api_key, get_glm_api_url, get_glm_model
from semantic_matching.exceptions import GLMSemanticMatchingError
from semantic_matching.prompt_builder import build_semantic_match_prompt

_PROMPT_PATH = Path(__file__).parent / "prompts" / "semantic_match_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEMPERATURE = 0.1


def _load_system_prompt() -> str:
    """Load the semantic match system prompt from disk."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise GLMSemanticMatchingError(
            f"Failed to load semantic match prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def evaluate_semantic_match_text(
    resume_json: dict[str, Any],
    jd_json: dict[str, Any],
    *,
    strict: bool = False,
) -> str:
    """
    Ask GLM to semantically score a resume against a JD.

    Args:
        resume_json: Parsed resume JSON.
        jd_json: Parsed JD JSON.
        strict: When ``True``, appends an extra instruction reinforcing that
            only raw JSON must be returned and every field must be present.
            Used on retry attempts.

    Returns:
        Raw JSON string from the LLM (may still need schema validation).

    Raises:
        PromptBuildError: If ``resume_json``/``jd_json`` is not a dict
            (propagated from ``prompt_builder``).
        GLMSemanticMatchingError: If the API call fails or the model
            returns no usable content.
    """
    user_prompt = build_semantic_match_prompt(resume_json, jd_json)

    system_prompt = _load_system_prompt()
    if strict:
        system_prompt += (
            "\n\nIMPORTANT: Return ONLY valid JSON. Do not include markdown, "
            "explanations, comments, or code fences. Ensure every field from "
            "the schema is present, and that category_scores contains only "
            "integer values from 0 to 100."
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
            get_glm_api_url(),
            headers=headers,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GLMSemanticMatchingError(
            f"GLM API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise GLMSemanticMatchingError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GLMSemanticMatchingError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise GLMSemanticMatchingError("GLM API returned empty content.")

    return str(content)
