"""
Configuration loader for the Semantic Matching Module.

Purpose:
    Centralize environment-based settings (GLM API key, model name, endpoint)
    so no module reads ``os.environ`` directly. Reuses the exact same
    environment variables as every other GLM-backed module in this project
    (``GLM_API_KEY``, ``GLM_MODEL``, ``GLM_API_URL``) so the whole project is
    configured from a single ``.env`` file with no duplicated or conflicting
    settings.

Inputs:
    Environment variables (typically loaded from a ``.env`` file).

Outputs:
    Configuration values consumed by ``semantic_scorer.py``.

Example usage:
    >>> from semantic_matching.config import get_glm_api_key
    >>> api_key = get_glm_api_key()
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from semantic_matching.exceptions import GLMSemanticMatchingError

load_dotenv()


def get_glm_api_key() -> str:
    """
    Return the LLM provider API key from the environment.

    Prefers ``GROQ_API_KEY`` (the current provider — used by this module and
    by ``recruiter_intelligence``, which reuses this config). Falls back to
    the legacy ``GLM_API_KEY`` so an old .env file still works without edits.

    Raises:
        GLMSemanticMatchingError: If neither is set.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("GLM_API_KEY", "").strip()
    if not api_key:
        raise GLMSemanticMatchingError(
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
