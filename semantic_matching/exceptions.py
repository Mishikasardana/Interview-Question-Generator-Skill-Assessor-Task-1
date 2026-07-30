"""
Custom exceptions for the Semantic Matching Module.

Mirrors question_generation's exception hierarchy since this module has the
same shape: multiple JSON inputs -> prompt builder -> GLM call -> validated
schema output.
"""


class SemanticMatchingError(Exception):
    """Base exception for all semantic matching failures."""


class PromptBuildError(SemanticMatchingError):
    """Raised when semantic matching inputs cannot be converted to a prompt."""


class GLMSemanticMatchingError(SemanticMatchingError):
    """Raised when the GLM API call fails or returns unusable output."""


class SemanticMatchValidationError(SemanticMatchingError):
    """Raised when the GLM response fails JSON/schema validation after retry."""
