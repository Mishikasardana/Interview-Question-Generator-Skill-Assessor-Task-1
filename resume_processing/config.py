"""
Configuration loader for the Resume Processing Module.

Purpose:
    Centralize environment-based settings (GLM API key, model name, endpoints)
    so no module reads ``os.environ`` directly. Uses python-dotenv for local
    development.

Inputs:
    Environment variables (typically loaded from a ``.env`` file).

Outputs:
    Immutable configuration values consumed by ``resume_parser.py``.

Example usage:
    >>> from resume_processing.config import get_glm_api_key
    >>> api_key = get_glm_api_key()
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from resume_processing.exceptions import ResumeParsingError

load_dotenv()


def get_glm_api_key() -> str:
    """
    Return the LLM provider API key from the environment.

    Prefers ``GROQ_API_KEY`` (the current provider — much faster than the
    previous GLM/Zhipu backend). Falls back to the legacy ``GLM_API_KEY``
    so an old .env file still works without edits.

    Raises:
        ResumeParsingError: If neither is set.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("GLM_API_KEY", "").strip()
    if not api_key:
        raise ResumeParsingError(
            "GROQ_API_KEY environment variable is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return api_key


def get_glm_model() -> str:
    """Return the chat-completions model identifier (defaults to a Groq model)."""
    return os.getenv("GROQ_MODEL", os.getenv("GLM_MODEL", "llama-3.3-70b-versatile")).strip()


def get_glm_api_url() -> str:
    """Return the chat-completions endpoint URL (defaults to Groq's)."""
    return os.getenv(
        "GROQ_API_URL",
        os.getenv("GLM_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
    ).strip()
