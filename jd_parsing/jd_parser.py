"""
GLM-based job description parser module.

Purpose:
    Send raw job description text to the GLM API and receive structured JSON.
    This module is isolated — it knows about the LLM and prompt, nothing else.
    It performs exactly one API call per invocation; retry logic lives in
    ``output_validator.py`` so the "call" and "validate-with-retry" concerns
    stay separate, matching the pattern used by ``resume_parser.py`` and
    ``generate_questions.py``.

Inputs:
    Raw job description text (``str``).

Outputs:
    Raw JSON string from the model (not yet validated).

Example usage:
    >>> from jd_parsing.jd_parser import parse_jd_text
    >>> raw_json = parse_jd_text(jd_text)

Design notes:
    - Prompt lives in ``prompts/jd_parser_prompt.txt`` (separate from code),
      loaded via ``Path(__file__).parent`` so it resolves correctly
      regardless of the process's current working directory.
    - Uses ``httpx`` for HTTP calls, same as the rest of the project — no
      extra HTTP client dependency is introduced.
    - Returns raw string; validation happens in ``output_validator.py``.

Assumptions:
    - GLM API credentials are configured via ``config.py``.
    - Model is instructed to return JSON only (no markdown, no explanations).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from jd_parsing.config import get_glm_api_key, get_glm_api_url, get_glm_model
from jd_parsing.exceptions import JDParsingError
from glm_http import post_with_retry

_PROMPT_PATH = Path(__file__).parent / "prompts" / "jd_parser_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 30.0
_DEFAULT_TEMPERATURE = 0.1
_MAX_OUTPUT_TOKENS = 2048


def _load_system_prompt() -> str:
    """Load the JD parser prompt from disk."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise JDParsingError(
            f"Failed to load parser prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def parse_jd_text(jd_text: str, *, strict: bool = False) -> str:
    """
    Parse raw job description text into structured JSON using the GLM API.

    Args:
        jd_text: Raw job description text (pasted or extracted from a file).
        strict: When ``True``, appends an extra instruction reinforcing that
            only raw JSON must be returned. Used on retry attempts.

    Returns:
        Raw JSON string from the LLM (may still need schema validation).

    Raises:
        JDParsingError: If input is empty, the API call fails, or the model
            returns no usable content.
    """
    if not isinstance(jd_text, str):
        raise JDParsingError(
            f"Expected str for JD parsing, got {type(jd_text).__name__}."
        )

    if not jd_text.strip():
        raise JDParsingError("Cannot parse empty job description text.")

    system_prompt = _load_system_prompt()
    if strict:
        system_prompt += (
            "\n\nIMPORTANT: Return ONLY valid JSON. "
            "Do not include markdown, explanations, comments, or code fences."
        )

    payload = {
        "model": get_glm_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": jd_text},
        ],
        "temperature": _DEFAULT_TEMPERATURE,
        "max_tokens": _MAX_OUTPUT_TOKENS,
    }
    headers = {
        "Authorization": f"Bearer {get_glm_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = post_with_retry(
            get_glm_api_url(),
            headers=headers,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPStatusError as exc:
        raise JDParsingError(
            f"GLM API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise JDParsingError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise JDParsingError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise JDParsingError("GLM API returned empty content.")

    return str(content)
