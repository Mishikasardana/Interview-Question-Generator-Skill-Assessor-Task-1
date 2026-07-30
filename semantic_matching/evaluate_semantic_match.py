"""
Main orchestrator for semantic match evaluation.

Purpose:
    Wire together the GLM call and output validation into one callable
    function. External consumers should only import ``evaluate_semantic_match``
    from the package root; they never touch ``semantic_scorer`` or
    ``output_validator`` directly.

Design note:
    This is an ADDITIONAL, separate evaluation alongside
    ``matching_engine.run_matching`` — it does not replace or modify the
    deterministic MatchResult contract that question_generation and the UI
    already depend on. Callers should run both and display both.

Example usage:
    >>> from semantic_matching import evaluate_semantic_match
    >>> result = evaluate_semantic_match(resume_json, jd_json)
"""

from __future__ import annotations

from typing import Any

from semantic_matching.output_validator import validate_with_retry
from semantic_matching.schema import SemanticMatchResult
from semantic_matching.semantic_scorer import evaluate_semantic_match_text


def evaluate_semantic_match(
    resume_json: dict[str, Any], jd_json: dict[str, Any]
) -> SemanticMatchResult:
    """
    Produce a GLM-based semantic/conceptual match evaluation.

    Args:
        resume_json: Parsed resume JSON (resume_processing output).
        jd_json: Parsed JD JSON (jd_parsing output).

    Returns:
        Validated ``SemanticMatchResult``.

    Raises:
        PromptBuildError: If ``resume_json``/``jd_json`` is not a dict.
        GLMSemanticMatchingError: If the GLM API call fails.
        SemanticMatchValidationError: If schema validation fails after retry.
    """
    return validate_with_retry(
        lambda strict: evaluate_semantic_match_text(resume_json, jd_json, strict=strict)
    )
