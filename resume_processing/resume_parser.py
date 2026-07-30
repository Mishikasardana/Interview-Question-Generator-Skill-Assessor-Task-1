"""
GLM-based resume parser module.

Purpose:
    Send cleaned resume text to the GLM API and receive structured JSON.
    This module is isolated — it knows about the LLM and prompt, nothing else.

Inputs:
    Cleaned resume text (``str``).

Outputs:
    Raw JSON string from the model (not yet validated).

Example usage:
    >>> from resume_processing.resume_parser import parse_resume_text
    >>> raw_json = parse_resume_text(cleaned_text)

Design notes:
    - Prompt lives in ``prompts/resume_parser_prompt.txt`` (separate from code).
    - Uses ``httpx`` for HTTP calls (async-ready, modern API).
    - Returns raw string; validation happens in ``validator.py``.

Assumptions:
    - GLM API credentials are configured via ``config.py``.
    - Model is instructed to return JSON only (no markdown, no explanations).
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from resume_processing.config import get_glm_api_key, get_glm_api_url, get_glm_model
from resume_processing.exceptions import ResumeParsingError

_PROMPT_PATH = Path(__file__).parent / "prompts" / "resume_parser_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEMPERATURE = 0.1

_MARKDOWN_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _load_system_prompt() -> str:
    """Load the resume parser prompt from disk."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ResumeParsingError(
            f"Failed to load parser prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def strip_markdown_fences(text: str) -> str:
    """
    Remove optional markdown code fences from model output.

    Args:
        text: Raw model response string.

    Returns:
        Inner content without ```json fences, or the original trimmed text.
    """
    stripped = text.strip()
    match = _MARKDOWN_FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def parse_resume_text(cleaned_text: str) -> str:
    """
    Parse cleaned resume text into structured JSON using the GLM API.

    Args:
        cleaned_text: Whitespace-normalized resume text.

    Returns:
        Raw JSON string from the LLM (may still need schema validation).

    Raises:
        ResumeParsingError: If input is empty, the API call fails, or the
            model returns no usable content.
    """
    if not isinstance(cleaned_text, str):
        raise ResumeParsingError(
            f"Expected str for resume parsing, got {type(cleaned_text).__name__}."
        )

    if not cleaned_text.strip():
        raise ResumeParsingError("Cannot parse empty resume text.")

    system_prompt = _load_system_prompt()
    payload = {
        "model": get_glm_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": cleaned_text},
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
        raise ResumeParsingError(
            f"GLM API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ResumeParsingError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ResumeParsingError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise ResumeParsingError("GLM API returned empty content.")

    return strip_markdown_fences(str(content))
