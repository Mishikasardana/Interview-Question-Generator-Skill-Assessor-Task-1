"""Question generation route — generate personalized interview questions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from api.schemas import QuestionGenerateRequest
from question_generation import generate_questions

router = APIRouter(prefix="/api/v1/questions", tags=["Question Generation"])


@router.post("/generate", summary="Generate personalized interview questions")
async def generate_questions_route(payload: QuestionGenerateRequest) -> dict[str, Any]:
    """Generate interview questions from resume + JD + match result JSON."""
    # generate_questions makes a blocking httpx call — offload to a worker
    # thread so it doesn't stall the event loop for other requests.
    result = await run_in_threadpool(
        generate_questions,
        resume_json=payload.resume_json,
        jd_json=payload.jd_json,
        match_result_json=payload.match_result_json,
        difficulty=payload.difficulty,
        question_count=payload.question_count,
    )
    return result.model_dump()
