"""Resume parsing route — upload a PDF or DOCX, get back structured resume JSON."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from resume_processing import process_resume
from resume_processing.exceptions import FileValidationError

router = APIRouter(prefix="/api/v1/resume", tags=["Resume"])

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


@router.post("/parse", response_model=None, summary="Parse a resume PDF or DOCX")
async def parse_resume(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Upload a resume (.pdf or .docx) and receive structured, normalized JSON.

    The file is written to a temporary path (the processing pipeline reads
    from disk), processed, and the temp file is always removed afterwards —
    even if parsing fails.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if not file.filename or suffix not in _SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise FileValidationError(f"Only {supported} files are supported.")

    contents = await file.read()
    if not contents:
        raise FileValidationError("Uploaded file is empty.")
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise FileValidationError(
            f"Uploaded file exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit."
        )

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        # process_resume makes a blocking httpx call — offload to a worker
        # thread so it doesn't stall the event loop for other requests.
        parsed = await run_in_threadpool(process_resume, tmp_path)
        return parsed.model_dump()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
