"""
Configuration loader for the Speech-to-Text Module.

Purpose:
    Centralize environment-based settings so no module reads ``os.environ``
    directly, matching the ``config.py`` convention used by every other
    module in this project.

Note on API keys:
    Unlike the GLM-backed modules, a Google Speech-to-Text API key is
    optional here. If ``GOOGLE_SPEECH_API_KEY`` is unset, the module falls
    back to ``speech_recognition``'s bundled free-tier demo key (the same
    no-signup-required Google Web Speech API access used in earlier
    prototypes of this project) — rate-limited, fine for development and
    small-scale/demo use, not intended for production-scale traffic.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_google_speech_api_key() -> str | None:
    """Return an optional Google Speech-to-Text API key, or None to use the free tier."""
    api_key = os.getenv("GOOGLE_SPEECH_API_KEY", "").strip()
    return api_key or None


@lru_cache
def get_default_language() -> str:
    """Return the default BCP-47 language code for transcription."""
    return os.getenv("SPEECH_LANGUAGE", "en-IN").strip() or "en-IN"
