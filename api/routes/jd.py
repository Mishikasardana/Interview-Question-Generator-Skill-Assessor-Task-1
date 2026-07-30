"""JD parsing route — send raw JD text, get back structured JD JSON."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from api.schemas import JDParseRequest
from jd_parsing import parse_jd

router = APIRouter(prefix="/api/v1/jd", tags=["Job Description"])


@router.post("/parse", summary="Parse raw job description text")
async def parse_jd_route(payload: JDParseRequest) -> dict[str, Any]:
    """Parse raw job description text into structured, validated JSON."""
    # parse_jd makes a blocking httpx call — run it on a worker thread so
    # it doesn't stall the event loop (and every other in-flight request)
    # for the duration of the GLM round trip.
    parsed = await run_in_threadpool(parse_jd, payload.jd_text)
    return parsed.model_dump()
