"""
Speech-to-Text Module — public package interface.

External consumers should only import from here:

    from speech_to_text import transcribe_audio_bytes, TranscriptionError
"""

from __future__ import annotations

from speech_to_text.exceptions import TranscriptionError
from speech_to_text.transcriber import transcribe_audio_bytes

__all__ = ["transcribe_audio_bytes", "TranscriptionError"]
