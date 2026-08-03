"""
Custom exceptions for the Answer Evaluation Module.

Purpose:
    Provide meaningful, domain-specific errors instead of generic Python
    exceptions, mirroring the exception style used across the rest of the
    project so the API layer can handle every module's failures the same way.

Inputs:
    N/A — exception classes only.

Outputs:
    Exception hierarchy rooted at ``AnswerEvaluationProcessingError``.

Example usage:
    >>> from answer_evaluation.exceptions import AnswerEvaluationError
    >>> raise AnswerEvaluationError("GLM API call failed")
"""


class AnswerEvaluationProcessingError(Exception):
    """Base exception for all answer evaluation failures."""

    pass


class AnswerEvaluationError(AnswerEvaluationProcessingError):
    """Raised when the GLM API call fails or returns unusable output."""

    pass


class AnswerValidationError(AnswerEvaluationProcessingError):
    """Raised when LLM output fails JSON/schema validation after retries."""

    pass
