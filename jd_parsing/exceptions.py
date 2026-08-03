"""
Custom exceptions for the JD Parsing Module.

Purpose:
    Provide meaningful, domain-specific errors instead of generic Python
    exceptions, mirroring the exception style used in ``resume_processing``
    and ``question_generation`` so the API layer can handle every module's
    failures the same way.

Inputs:
    N/A — exception classes only.

Outputs:
    Exception hierarchy rooted at ``JDProcessingError``.

Example usage:
    >>> from jd_parsing.exceptions import JDParsingError
    >>> raise JDParsingError("GLM API call failed")
"""


class JDProcessingError(Exception):
    """Base exception for all JD processing failures."""

    pass


class JDParsingError(JDProcessingError):
    """Raised when the GLM API call fails or returns unusable output."""

    pass


class JDValidationError(JDProcessingError):
    """Raised when LLM output fails JSON/schema validation after retries."""

    pass
