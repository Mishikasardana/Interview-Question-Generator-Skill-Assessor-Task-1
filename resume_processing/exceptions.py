"""
Custom exceptions for the Resume Processing Module.

Purpose:
    Provide meaningful, domain-specific errors instead of generic Python
    exceptions. Each pipeline stage raises its own exception type so callers
    can handle failures precisely and debug quickly.

Inputs:
    N/A — exception classes only.

Outputs:
    Exception hierarchy rooted at ``ResumeProcessingError``.

Example usage:
    >>> from resume_processing.exceptions import PDFExtractionError
    >>> raise PDFExtractionError("Could not read PDF: file is encrypted")
"""


class ResumeProcessingError(Exception):
    """Base exception for all resume processing failures."""

    pass


class FileValidationError(ResumeProcessingError):
    """Raised when the input file is missing, empty, or not a valid PDF/DOCX."""

    pass


class PDFExtractionError(ResumeProcessingError):
    """Raised when text cannot be extracted from a PDF."""

    pass


class DocxExtractionError(ResumeProcessingError):
    """Raised when text cannot be extracted from a DOCX file."""

    pass


class TextCleaningError(ResumeProcessingError):
    """Raised when text cleaning fails unexpectedly."""

    pass


class ResumeParsingError(ResumeProcessingError):
    """Raised when the GLM API call fails or returns unusable output."""

    pass


class ValidationError(ResumeProcessingError):
    """Raised when LLM output fails JSON/schema validation after retries."""

    pass


class NormalizationError(ResumeProcessingError):
    """Raised when data normalization fails unexpectedly."""

    pass
