"""
Audio transcription module.

Purpose:
    Transcribe recorded interview answer audio to text, using Google's Web
    Speech API via the ``speech_recognition`` library. This is the module
    the interview screen calls after the candidate records a spoken answer.

Inputs:
    Raw WAV audio bytes (e.g. from Streamlit's
    ``st.audio_input(...).getvalue()``).

Outputs:
    Transcribed text (``str``).

Example usage:
    >>> from speech_to_text import transcribe_audio_bytes
    >>> text = transcribe_audio_bytes(audio_bytes)

Design notes:
    - Uses ``sr.AudioFile`` (not ``sr.Microphone``) since audio arrives as
      already-recorded bytes, not a live mic stream — no ``pyaudio`` /
      system audio dependency is required for this path.
    - A single module-level ``Recognizer`` instance is reused across calls;
      it is stateless per-call (energy threshold adjustment is not needed
      for file-based input the way it is for live mic streams).

Assumptions:
    - Input audio is a valid WAV container (Streamlit's ``st.audio_input``
      guarantees this).
"""

from __future__ import annotations

import io

import speech_recognition as sr

from speech_to_text.config import get_default_language, get_google_speech_api_key
from speech_to_text.exceptions import TranscriptionError

_REQUEST_TIMEOUT_SECONDS = 60.0

_recognizer = sr.Recognizer()
# Without an explicit timeout, a stalled connection to the recognition
# service hangs indefinitely (the library default is no timeout at all),
# freezing the interview screen. Every other HTTP-backed module in this
# project sets an explicit timeout — this matches that convention.
_recognizer.operation_timeout = _REQUEST_TIMEOUT_SECONDS


def transcribe_audio_bytes(audio_bytes: bytes, *, language: str | None = None) -> str:
    """
    Transcribe recorded WAV audio bytes to text.

    Args:
        audio_bytes: Raw WAV audio bytes.
        language: BCP-47 language code (e.g. ``"en-IN"``, ``"en-US"``).
            Defaults to ``SPEECH_LANGUAGE`` from the environment
            (``config.get_default_language``) if not given.

    Returns:
        Transcribed text.

    Raises:
        TranscriptionError: If the audio is empty, not readable as WAV,
            contains no recognizable speech, or the recognition service
            request fails.
    """
    if not isinstance(audio_bytes, (bytes, bytearray)):
        raise TranscriptionError(
            f"Expected bytes for audio_bytes, got {type(audio_bytes).__name__}."
        )

    if not audio_bytes:
        raise TranscriptionError("No audio data to transcribe — recording is empty.")

    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = _recognizer.record(source)
    except (ValueError, OSError) as exc:
        raise TranscriptionError(
            f"Could not read the recording (expected WAV audio): {exc}"
        ) from exc

    try:
        return _recognizer.recognize_google(
            audio_data,
            key=get_google_speech_api_key(),
            language=language or get_default_language(),
        )
    except sr.UnknownValueError as exc:
        raise TranscriptionError(
            "Could not understand the audio. Please speak clearly and try again."
        ) from exc
    except sr.RequestError as exc:
        raise TranscriptionError(
            f"Speech recognition service request failed: {exc}"
        ) from exc
    except (ValueError, KeyError, TypeError, AssertionError) as exc:
        # Covers malformed/unexpected responses from the recognition
        # service (e.g. non-JSON body) and corrupt-but-parseable WAV
        # input (e.g. an unsupported channel count), neither of which
        # `speech_recognition` wraps in its own exception types.
        raise TranscriptionError(
            f"Speech recognition returned an unexpected response: {exc}"
        ) from exc
