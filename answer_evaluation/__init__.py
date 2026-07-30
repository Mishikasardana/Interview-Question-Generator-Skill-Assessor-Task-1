"""
Answer Evaluation Module — public package interface.

External consumers should only import from here:

    from answer_evaluation import evaluate_answer, EvaluationResult

Everything else (``evaluator``, ``output_validator``, ``config``,
``exceptions``) is an internal implementation detail.
"""

from __future__ import annotations

from answer_evaluation.evaluate_answer import evaluate_answer
from answer_evaluation.exceptions import (
    AnswerEvaluationError,
    AnswerEvaluationProcessingError,
    AnswerValidationError,
)
from answer_evaluation.schema import EvaluationResult

__all__ = [
    "evaluate_answer",
    "EvaluationResult",
    "AnswerEvaluationProcessingError",
    "AnswerEvaluationError",
    "AnswerValidationError",
]
