"""
Custom exceptions for the Recruiter Intelligence Engine.

Mirrors semantic_matching's exception hierarchy since Stage A has the same
shape: JSON input -> prompt builder -> GLM call -> validated schema output.
Stage B (the hard-requirement gate) is pure deterministic Python and raises
no GLM-related exceptions at all.
"""


class RecruiterIntelligenceError(Exception):
    """Base exception for all Recruiter Intelligence Engine failures."""


class PromptBuildError(RecruiterIntelligenceError):
    """Raised when inputs cannot be converted into a prompt."""


class GLMRequirementExtractionError(RecruiterIntelligenceError):
    """Raised when the GLM API call fails or returns unusable output."""


class RequirementExtractionValidationError(RecruiterIntelligenceError):
    """Raised when the GLM response fails JSON/schema validation after retry."""


class GLMEvidenceEvaluationError(RecruiterIntelligenceError):
    """Raised when Stage C's GLM API call fails or returns unusable output."""


class EvidenceEvaluationValidationError(RecruiterIntelligenceError):
    """Raised when Stage C's GLM response fails JSON/schema validation after retry."""
