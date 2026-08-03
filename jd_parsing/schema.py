"""
Pydantic schema for parsed job description data.

Purpose:
    Define the single canonical JSON shape returned by the module. Pydantic
    enforces types, required keys, and defaults so every consumer (the
    Matching Engine, Question Generation, and the API layer) receives
    consistent data regardless of JD content.

Inputs:
    Raw dict/JSON from the LLM parser (validated by ``output_validator.py``).

Outputs:
    ``ParsedJD`` model instance with typed fields.

Example usage:
    >>> from jd_parsing.schema import ParsedJD
    >>> jd = ParsedJD(role="ML Engineer", required_skills=["Python"])
    >>> jd.model_dump()
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HardRequirementType = Literal[
    "min_experience_years", "degree", "certification", "clearance", "visa", "location", "other",
]


class HardRequirement(BaseModel):
    """
    A pass/fail gate the JD states explicitly — distinct from a skill to be
    weighed. See the Recruiter Intelligence Engine plan's hard-requirements
    strategy: types like clearance/visa/location are generally NOT reliably
    verifiable from a resume and must route to human review downstream,
    never a guessed pass or fail.
    """

    model_config = ConfigDict(extra="forbid")

    type: HardRequirementType
    description: str = ""
    minimum_value: str = ""
    is_mandatory: bool = True


class ParsedJD(BaseModel):
    """
    Canonical parsed job description structure.

    All fields are always present. Missing sections from the source JD map
    to empty strings or empty lists — never ``null`` or omitted keys — so
    downstream modules (matching engine, question generation) never need to
    guard against missing keys.

    Note: ``education_requirement`` was added beyond the field set in the
    original prompt draft because ``matching_engine._education_score`` reads
    ``jd_json["education_requirement"]`` to score degree-level fit. Without
    it, that field was silently always empty and education scoring degraded
    to "no requirement" for every JD — a connected-pipeline bug, not a
    hypothetical one.

    ``hard_requirements`` is additive (default empty list) — every existing
    consumer of ``ParsedJD`` is unaffected until it's read explicitly.
    """

    model_config = ConfigDict(extra="forbid")

    role: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_level: str = ""
    education_requirement: str = ""
    hard_requirements: list[HardRequirement] = Field(default_factory=list)
