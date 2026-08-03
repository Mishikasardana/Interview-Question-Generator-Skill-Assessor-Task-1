"""
Centralized exception handling.

Every processing module raises its own exception hierarchy (see each
module's ``exceptions.py``). Rather than repeat try/except blocks in every
route, we register one FastAPI exception handler per base exception class
here. This keeps routes thin and guarantees a consistent error JSON shape:

    {"error_type": "...", "detail": "..."}

Mapping:
    - RequestValidationError (FastAPI/Pydantic's own request-shape errors —
      missing/empty fields, wrong types) → 422, same {"error_type","detail"}
      shape as everything else, instead of FastAPI's default {"detail":[...]}
    - *ValidationError / *ParsingError / PromptBuildError / FileValidationError
      / MatchingEngineError  → 422 Unprocessable Entity (bad input, either
      from the caller or from the LLM output that couldn't be salvaged)
    - *ResumeParsingError / GLMQuestionGenerationError / AnswerEvaluationError
      that specifically indicate an upstream GLM API failure are still raised
      as subclasses of each module's base error, so they are covered by the
      same 422 mapping below (the caller-facing distinction that matters is
      "your request could not be completed", not which internal stage failed).
    - Anything unexpected → 500 Internal Server Error
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from answer_evaluation.exceptions import AnswerEvaluationProcessingError
from jd_parsing.exceptions import JDProcessingError
from matching_engine.exceptions import MatchingEngineError
from question_generation.exceptions import QuestionGenerationError
from recruiter_intelligence.exceptions import RecruiterIntelligenceError
from resume_processing.exceptions import ResumeProcessingError
from semantic_matching.exceptions import SemanticMatchingError

logger = logging.getLogger("iip.api")

# Exceptions that indicate a problem the caller can potentially fix or retry
# (bad input, unparseable JD text, LLM returned unusable output, etc).
_CLIENT_FACING_ERRORS = (
    ResumeProcessingError,
    JDProcessingError,
    MatchingEngineError,
    QuestionGenerationError,
    AnswerEvaluationProcessingError,
    SemanticMatchingError,
    RecruiterIntelligenceError,
)


async def _handle_client_facing_error(request: Request, exc: Exception) -> JSONResponse:
    logger.warning("%s: %s", type(exc).__name__, exc)
    return JSONResponse(
        status_code=422,
        content={"error_type": type(exc).__name__, "detail": str(exc)},
    )


async def _handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    FastAPI/Pydantic raise this themselves for request-shape problems
    (missing/empty fields, wrong types) — before any route or domain
    exception ever runs. Without this handler it bypasses the uniform
    {"error_type","detail"} shape entirely and falls through to FastAPI's
    default {"detail": [...]} body, breaking the documented error contract
    for the single most common class of client mistake.
    """
    logger.warning("RequestValidationError on %s: %s", request.url.path, exc.errors())
    detail = "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ) or "Invalid request."
    return JSONResponse(
        status_code=422,
        content={"error_type": "RequestValidationError", "detail": detail},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error_type": "InternalServerError", "detail": "An unexpected error occurred."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every exception handler to the given FastAPI app."""
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)
    for exc_class in _CLIENT_FACING_ERRORS:
        app.add_exception_handler(exc_class, _handle_client_facing_error)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
