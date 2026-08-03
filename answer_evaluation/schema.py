"""
Pydantic schema for interview answer evaluation results.

Purpose:
    Define the single canonical JSON shape returned by the module. The field
    set matches ``prompts/evaluation_prompt.txt`` exactly:
    ``overall_score`` = ``correctness`` + ``keyword_coverage`` + ``clarity`` +
    ``communication`` + ``completeness``.

    Note: an earlier draft of this module's validator included a stray
    ``required_skill_relevance`` field that the evaluation prompt never asks
    the model to produce and that is not part of the scoring formula. It has
    been removed here so the schema always matches what the prompt actually
    requests — keeping a field the LLM never populates would silently
    default it to 0 on every response, which is misleading.

Inputs:
    Raw dict/JSON from the LLM evaluator (validated by ``output_validator.py``).

Outputs:
    ``EvaluationResult`` model instance with typed fields.

Example usage:
    >>> from answer_evaluation.schema import EvaluationResult
    >>> result = EvaluationResult(overall_score=78, correctness=25, ...)
    >>> result.model_dump()
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationResult(BaseModel):
    """
    Canonical answer evaluation structure.

    All fields are always present. Missing sections from the model's
    response map to zero or empty defaults — never ``null`` or omitted keys.
    """

    model_config = ConfigDict(extra="forbid")

    overall_score: float = Field(default=0, ge=0, le=100)
    correctness: float = Field(default=0, ge=0, le=30)
    keyword_coverage: float = Field(default=0, ge=0, le=25)
    clarity: float = Field(default=0, ge=0, le=20)
    communication: float = Field(default=0, ge=0, le=15)
    completeness: float = Field(default=0, ge=0, le=10)
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    feedback: str = ""
    ideal_answer: str = ""

    @model_validator(mode="after")
    def _recompute_overall_score(self) -> "EvaluationResult":
        """
        The prompt defines overall_score as the sum of the five subscores,
        but nothing guarantees the model actually did that arithmetic on
        its end — recompute it here so the headline number can never
        contradict the subscore breakdown shown in the UI. Always within
        [0, 100] since the subscores' own bounds sum to exactly 100.
        """
        self.overall_score = (
            self.correctness
            + self.keyword_coverage
            + self.clarity
            + self.communication
            + self.completeness
        )
        return self
