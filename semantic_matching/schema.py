"""
Pydantic schema for GLM-based semantic (conceptual) match evaluation.

Purpose:
    Define the single canonical JSON shape returned by this module. Every
    field mirrors ``prompts/semantic_match_prompt.txt`` exactly.

    Unlike ``matching_engine.MatchResult`` (exact-keyword coverage), every
    score here reflects conceptual/semantic similarity per the prompt's
    rubric — this schema is an additional, separate output shape, not a
    replacement for ``MatchResult``.

Example usage:
    >>> from semantic_matching.schema import SemanticMatchResult
    >>> SemanticMatchResult(overall_score=88, category_scores={"LLMs": 90})
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

_Score = Annotated[int, Field(ge=0, le=100)]


class SemanticMatchResult(BaseModel):
    """
    Canonical parsed semantic match structure.

    All fields are always present. Missing sections from the model's
    response map to zero or empty defaults — never ``null`` or omitted keys.
    """

    model_config = ConfigDict(extra="forbid")

    overall_score: _Score = 0
    category_scores: dict[str, _Score] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
