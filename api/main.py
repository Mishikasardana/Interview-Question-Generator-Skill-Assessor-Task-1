"""
FastAPI application entrypoint.

Run locally:
    uvicorn api.main:app --reload

Then open:
    http://127.0.0.1:8000/docs   (interactive Swagger UI)
    http://127.0.0.1:8000/redoc  (ReDoc)

This file only wires things together: CORS, routers, exception handlers.
No business logic lives here.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.exception_handlers import register_exception_handlers
from api.routes import evaluation, jd, matching, pipeline, questions, resume
from api.schemas import HealthResponse

load_dotenv()

app = FastAPI(
    title="Interview Intelligence Platform API",
    description=(
        "Backend for the AI Interview Intelligence Platform: resume parsing, "
        "JD parsing, skill matching, question generation, and answer "
        "evaluation, each exposed as an independent REST endpoint."
    ),
    version="1.0.0",
)

# CORS origins are read from the environment (comma-separated) instead of
# being hardcoded, so this can be locked down per-deployment without a code
# change. Defaults to "*" for local development only.
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
_is_wildcard = _allowed_origins.strip() == "*"
origins = (
    ["*"] if _is_wildcard else
    [origin.strip() for origin in _allowed_origins.split(",") if origin.strip()]
)

# Starlette's CORSMiddleware special-cases allow_origins=["*"] combined with
# allow_credentials=True: instead of literally sending "*", it reflects the
# request's actual Origin header back with credentials allowed — meaning
# *any* site can make a credentialed cross-origin request. Credentials are
# only safe to allow once a real, explicit origin allowlist is configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=not _is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(resume.router)
app.include_router(jd.router)
app.include_router(matching.router)
app.include_router(questions.router)
app.include_router(evaluation.router)
app.include_router(pipeline.router)


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    """Liveness check — does not verify GLM credentials or connectivity."""
    return HealthResponse()


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Redirect-style root — points humans to the interactive docs."""
    return {
        "service": "Interview Intelligence Platform API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
