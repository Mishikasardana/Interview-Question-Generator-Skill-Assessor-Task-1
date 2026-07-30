"""
Tests for speech_to_text.transcriber.

The only network call this module makes is ``Recognizer.recognize_google``,
which is mocked in every test below — everything else (WAV parsing via
``sr.AudioFile``, error handling) runs for real against an actual
in-memory WAV file, so no test here depends on internet access.
"""

from __future__ import annotations

import io
import wave
from unittest.mock import patch

import pytest
import speech_recognition as sr

from speech_to_text.exceptions import TranscriptionError
from speech_to_text.transcriber import transcribe_audio_bytes


def _make_silent_wav_bytes(duration_seconds: float = 1.0) -> bytes:
    """Build a minimal, real, silent WAV file in memory for parsing tests."""
    buffer = io.BytesIO()
    framerate = 16000
    n_frames = int(framerate * duration_seconds)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(b"\x00\x00" * n_frames)
    return buffer.getvalue()


def test_transcribe_audio_bytes_rejects_empty_input():
    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes(b"")


def test_transcribe_audio_bytes_rejects_non_bytes_input():
    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes("not bytes")  # type: ignore[arg-type]


@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_accepts_bytearray_input(mock_recognize):
    mock_recognize.return_value = "Bytearray audio accepted."
    wav_bytes = bytearray(_make_silent_wav_bytes())

    result = transcribe_audio_bytes(wav_bytes)

    assert result == "Bytearray audio accepted."


def test_transcribe_audio_bytes_rejects_garbage_audio():
    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes(b"this is not a wav file")


@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_returns_recognized_text(mock_recognize):
    mock_recognize.return_value = "This is a test answer."
    wav_bytes = _make_silent_wav_bytes()

    result = transcribe_audio_bytes(wav_bytes)

    assert result == "This is a test answer."
    mock_recognize.assert_called_once()


@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_passes_language_override(mock_recognize):
    mock_recognize.return_value = "Test"
    wav_bytes = _make_silent_wav_bytes()

    transcribe_audio_bytes(wav_bytes, language="en-US")

    _, kwargs = mock_recognize.call_args
    assert kwargs["language"] == "en-US"


@patch("speech_to_text.transcriber.get_default_language")
@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_uses_default_language(mock_recognize, mock_language):
    mock_recognize.return_value = "Default language."
    mock_language.return_value = "en-IN"
    wav_bytes = _make_silent_wav_bytes()

    transcribe_audio_bytes(wav_bytes)

    _, kwargs = mock_recognize.call_args
    assert kwargs["language"] == "en-IN"


@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_raises_on_unrecognized_speech(mock_recognize):
    mock_recognize.side_effect = sr.UnknownValueError()
    wav_bytes = _make_silent_wav_bytes()

    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes(wav_bytes)


@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_raises_on_service_request_error(mock_recognize):
    mock_recognize.side_effect = sr.RequestError("service unavailable")
    wav_bytes = _make_silent_wav_bytes()

    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes(wav_bytes)


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("Bad JSON in response"),
        KeyError("result"),
        AssertionError("unsupported channel count"),
        TypeError("unexpected None"),
    ],
)
@patch("speech_to_text.transcriber._recognizer.recognize_google")
def test_transcribe_audio_bytes_wraps_unexpected_recognizer_errors(
    mock_recognize, exc
):
    # These are failure modes `speech_recognition` itself doesn't wrap in
    # sr.UnknownValueError/sr.RequestError (e.g. a malformed API response
    # body, or a corrupt-but-parseable WAV header) — they should still
    # surface as a TranscriptionError, not an unhandled crash.
    mock_recognize.side_effect = exc
    wav_bytes = _make_silent_wav_bytes()

    with pytest.raises(TranscriptionError):
        transcribe_audio_bytes(wav_bytes)


def test_recognizer_has_an_explicit_operation_timeout():
    from speech_to_text.transcriber import _recognizer

    # Without this, a stalled connection to the recognition service hangs
    # forever (the library default is no timeout at all).
    assert _recognizer.operation_timeout is not None
