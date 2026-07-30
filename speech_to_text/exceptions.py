"""
Custom exceptions for the Speech-to-Text Module.

Purpose:
    Provide a meaningful, domain-specific error instead of surfacing raw
    ``speech_recognition`` exceptions, mirroring the exception style used
    across the rest of the project.
"""


class TranscriptionError(Exception):
    """Raised when recorded audio cannot be transcribed to text."""

    pass
