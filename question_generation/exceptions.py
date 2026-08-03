"""
Custom exceptions for the Question Generation Module.

Each stage raises a domain-specific exception so failures are easier to
understand during development and technical reviews.
"""


class QuestionGenerationError(Exception):
    """Base exception for all question generation failures."""

    pass


class PromptBuildError(QuestionGenerationError):
    """Raised when question generation inputs cannot be converted to a prompt."""

    pass


class GLMQuestionGenerationError(QuestionGenerationError):
    """Raised when the GLM API call fails or returns unusable output."""

    pass


class QuestionValidationError(QuestionGenerationError):
    """Raised when generated question JSON fails validation after retry."""

    pass
