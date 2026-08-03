"""
Main orchestrator — the single public entry point for answer evaluation.

Purpose:
    Wire together the GLM call and output validation into one callable
    function. External consumers import only ``evaluate_answer``; they never
    touch ``evaluator`` or ``output_validator`` directly.

Pipeline:
    Question + Candidate Answer + Job Role + Required Skills
        → GLM Evaluator     (evaluator)
        → Validate JSON     (output_validator)
        → Return EvaluationResult

Example usage:
    >>> from answer_evaluation.evaluate_answer import evaluate_answer
    >>> result = evaluate_answer(
    ...     question="Explain REST vs GraphQL",
    ...     candidate_answer="REST uses fixed endpoints ...",
    ...     job_role="Backend Engineer",
    ...     required_skills=["Python", "REST API"],
    ... )
    >>> result.overall_score
"""

from __future__ import annotations

from answer_evaluation.evaluator import evaluate_answer_text
from answer_evaluation.output_validator import validate_with_retry
from answer_evaluation.schema import EvaluationResult


def evaluate_answer(
    question: str,
    candidate_answer: str,
    job_role: str,
    required_skills: list[str],
) -> EvaluationResult:
    """
    Evaluate a candidate's interview answer.

    Args:
        question: Interview question.
        candidate_answer: Candidate's transcribed answer.
        job_role: Job role extracted from the JD.
        required_skills: Required skills extracted from the JD.

    Returns:
        Validated ``EvaluationResult``.

    Raises:
        AnswerEvaluationError: GLM API failure.
        AnswerValidationError: Schema validation failure after retry.
    """
    return validate_with_retry(
        lambda strict: evaluate_answer_text(
            question=question,
            candidate_answer=candidate_answer,
            job_role=job_role,
            required_skills=required_skills,
            strict=strict,
        )
    )
