"""Answer evaluation route — score a candidate's interview answer."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from answer_evaluation import evaluate_answer
from api.schemas import EvaluateAnswerRequest

router = APIRouter(prefix="/api/v1/interview", tags=["Interview Evaluation"])


@router.post("/evaluate", summary="Evaluate a candidate's interview answer")
async def evaluate_answer_route(payload: EvaluateAnswerRequest) -> dict[str, Any]:
    """Score a candidate's spoken/written answer against the interview question."""
    # evaluate_answer makes a blocking httpx call — offload to a worker
    # thread so it doesn't stall the event loop for other requests.
    result = await run_in_threadpool(
        evaluate_answer,
        question=payload.question,
        candidate_answer=payload.candidate_answer,
        job_role=payload.job_role,
        required_skills=payload.required_skills,
    )
    return result.model_dump()
