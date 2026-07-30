"""
GLM-based interview answer evaluator module.

Purpose:
    Send a candidate's interview answer (plus question/role/skills context)
    to the GLM API and receive a structured evaluation. This module is
    isolated — it knows about the LLM and prompt, nothing else. It performs
    exactly one API call per invocation; retry logic lives in
    ``output_validator.py``, matching the pattern used everywhere else in
    this project.

Inputs:
    Interview question, candidate answer, job role, and required skills.

Outputs:
    Raw JSON string from the model (not yet validated).

Example usage:
    >>> from answer_evaluation.evaluator import evaluate_answer_text
    >>> raw_json = evaluate_answer_text(
    ...     question="Explain REST vs GraphQL",
    ...     candidate_answer="REST uses ...",
    ...     job_role="Backend Engineer",
    ...     required_skills=["Python", "REST API"],
    ... )

Design notes:
    - Prompt lives in ``prompts/evaluation_prompt.txt``, loaded via
      ``Path(__file__).parent`` so it resolves correctly regardless of the
      process's current working directory.
    - Uses ``httpx`` for HTTP calls, same as the rest of the project.
    - Returns raw string; validation happens in ``output_validator.py``.

Assumptions:
    - GLM API credentials are configured via ``config.py``.
    - Model is instructed to return JSON only (no markdown, no explanations).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from answer_evaluation.config import get_glm_api_key, get_glm_api_url, get_glm_model
from answer_evaluation.exceptions import AnswerEvaluationError

_PROMPT_PATH = Path(__file__).parent / "prompts" / "evaluation_prompt.txt"
_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_TEMPERATURE = 0.1


def _load_system_prompt() -> str:
    """Load the evaluation system prompt from disk."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AnswerEvaluationError(
            f"Failed to load evaluation prompt from '{_PROMPT_PATH}': {exc}"
        ) from exc


def _build_user_prompt(
    question: str,
    candidate_answer: str,
    job_role: str,
    required_skills: list[str],
) -> str:
    """Assemble the structured user-turn content sent to the model."""
    skills_text = ", ".join(required_skills) if required_skills else ""
    return (
        f"Job Role:\n{job_role}\n\n"
        f"Required Skills:\n{skills_text}\n\n"
        f"Interview Question:\n{question}\n\n"
        f"Candidate Answer:\n{candidate_answer}\n"
    )


def evaluate_answer_text(
    question: str,
    candidate_answer: str,
    job_role: str,
    required_skills: list[str],
    *,
    strict: bool = False,
) -> str:
    """
    Evaluate a candidate's interview answer using the GLM API.

    Args:
        question: Interview question.
        candidate_answer: Candidate's transcribed answer.
        job_role: Job role extracted from the JD.
        required_skills: Required skills extracted from the JD.
        strict: When ``True``, appends an extra instruction reinforcing that
            every schema field must be present and only raw JSON returned.
            Used on retry attempts.

    Returns:
        Raw JSON string from the LLM (may still need schema validation).

    Raises:
        AnswerEvaluationError: If required text inputs are empty, the API
            call fails, or the model returns no usable content.
    """
    if not isinstance(question, str) or not question.strip():
        raise AnswerEvaluationError("Cannot evaluate with an empty question.")

    if not isinstance(candidate_answer, str) or not candidate_answer.strip():
        raise AnswerEvaluationError("Cannot evaluate an empty candidate answer.")

    system_prompt = _load_system_prompt()
    if strict:
        system_prompt += (
            "\n\nIMPORTANT: Return ONLY valid JSON. Do not include markdown, "
            "explanations, comments, or code fences. Ensure every field from "
            "the schema is present."
        )

    user_prompt = _build_user_prompt(
        question=question,
        candidate_answer=candidate_answer,
        job_role=job_role,
        required_skills=required_skills,
    )

    payload = {
        "model": get_glm_model(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": _DEFAULT_TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {get_glm_api_key()}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            get_glm_api_url(),
            headers=headers,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise AnswerEvaluationError(
            f"GLM API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise AnswerEvaluationError(f"GLM API request failed: {exc}") from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AnswerEvaluationError(
            f"Unexpected GLM API response format: {response.text}"
        ) from exc

    if not content or not str(content).strip():
        raise AnswerEvaluationError("GLM API returned empty content.")

    return str(content)
