"""
Pydantic schema for generated interview questions.

The schema is intentionally small because this is an internship MVP. It gives
downstream code a predictable JSON shape without adding enterprise complexity.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InterviewQuestion(BaseModel):
    """One personalized interview question."""

    model_config = ConfigDict(extra="forbid")

    question: str
    category: str
    difficulty: Literal["easy", "medium", "hard"]
    reason: str


class GeneratedQuestions(BaseModel):
    """Canonical output from the question generation module."""

    model_config = ConfigDict(extra="forbid")

    questions: list[InterviewQuestion] = Field(default_factory=list)
