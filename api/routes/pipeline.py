"""
Combined pipeline route.

Convenience endpoint that chains resume parsing → JD parsing → matching in a
single request, mirroring the flow described in the project README. Splitting
these into three separate calls (see resume.py, jd.py, matching.py) is still
supported and is what a real frontend would likely do so it can show
progress between stages — this endpoint just saves round trips for simple
integrations, scripts, or testing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool

from api.routes.matching import _run_recruiter_pipeline
from jd_parsing import parse_jd
from resume_processing import process_resume
from resume_processing.exceptions import FileValidationError

router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/analyze", summary="Parse resume + JD and run matching in one call")
async def analyze_route(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
) -> dict[str, Any]:
    """
    Run resume parsing, JD parsing, and matching as one pipeline call.

    Returns:
        ``{"resume": {...}, "jd": {...}, "match": {...}}``
    """
    suffix = Path(resume_file.filename or "").suffix.lower()
    if not resume_file.filename or suffix not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise FileValidationError(f"Only {supported} files are supported for resume_file.")

    contents = await resume_file.read()
    if not contents:
        raise FileValidationError("Uploaded resume file is empty.")
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise FileValidationError(
            f"Uploaded file exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit."
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # process_resume, parse_jd, and the Recruiter Match pipeline (two
        # GLM calls) all make blocking httpx calls — offload each to a
        # worker thread so they don't stall the event loop for other
        # requests.
        parsed_resume = await run_in_threadpool(process_resume, tmp_path)
        parsed_jd = await run_in_threadpool(parse_jd, jd_text)
        match_result_json = await run_in_threadpool(
            _run_recruiter_pipeline, parsed_resume.model_dump(), parsed_jd.model_dump(),
        )

        return {
            "resume": parsed_resume.model_dump(),
            "jd": parsed_jd.model_dump(),
            "match": match_result_json,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
