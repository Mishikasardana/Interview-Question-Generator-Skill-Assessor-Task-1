"""
Semantic Matching Module — public package interface.

External consumers should only import from here:

    from semantic_matching import evaluate_semantic_match, SemanticMatchResult

Everything else (``semantic_scorer``, ``prompt_builder``,
``output_validator``, ``config``) is an internal implementation detail, not
part of the contract.

This module is an additional, GLM-powered *semantic* evaluation that runs
alongside — not instead of — the deterministic ``matching_engine.run_matching``.
It never modifies matching_engine's pure, offline contract.
"""

from __future__ import annotations

from semantic_matching.evaluate_semantic_match import evaluate_semantic_match
from semantic_matching.exceptions import (
    GLMSemanticMatchingError,
    PromptBuildError,
    SemanticMatchingError,
    SemanticMatchValidationError,
)
from semantic_matching.schema import SemanticMatchResult

__all__ = [
    "evaluate_semantic_match",
    "SemanticMatchResult",
    "SemanticMatchingError",
    "PromptBuildError",
    "GLMSemanticMatchingError",
    "SemanticMatchValidationError",
]
