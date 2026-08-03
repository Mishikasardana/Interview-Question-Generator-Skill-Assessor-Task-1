"""
Pydantic schema for parsed resume data.

Purpose:
    Define the single canonical JSON shape returned by the module. Pydantic
    enforces types, required keys, and defaults so every consumer receives
    consistent data regardless of resume content.

Inputs:
    Raw dict/JSON from the LLM parser (validated by ``validator.py``).

Outputs:
    ``ParsedResume`` model instance with typed fields.

Example usage:
    >>> from resume_processing.schema import ParsedResume
    >>> resume = ParsedResume(name="Jane Doe", skills=["Python"])
    >>> resume.model_dump()
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ParsedResume(BaseModel):
    """
    Canonical parsed resume structure.

    All fields are always present. Missing sections from the source resume
    map to empty strings or empty lists — never ``null`` or omitted keys —
    with one deliberate exception: ``estimated_total_experience_years``.

    That field is ``float | None`` rather than defaulting to ``0.0``,
    because for a hard-requirement gate (e.g. "5+ years required") a
    genuine zero (a fresh graduate with no professional experience) and an
    "I couldn't tell from this resume" are different outcomes with
    different consequences — the former should fail a min-years gate, the
    latter should route to human review, never a silent guess. See the
    Recruiter Intelligence Engine plan's hard-requirements strategy.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    estimated_total_experience_years: float | None = None
