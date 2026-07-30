"""
Main orchestrator — the single public entry point for resume processing.

Purpose:
    Wire together all pipeline stages into one callable function. External
    consumers import only ``process_resume`` (or ``process_resume_with_raw_text``
    when the raw extracted text is also needed, e.g. for database storage);
    they never touch internal modules.

Pipeline:
    Resume PDF or DOCX
        → Validate File
        → Extract Text       (pdf_extractor / docx_extractor, by extension)
        → Clean Text         (text_cleaner)
        → Resume Parser      (resume_parser / GLM)
        → Validate JSON      (validator)
        → Normalize Data     (normalizer)
        → Return ParsedResume

Inputs:
    ``resume_file``: Path to a .pdf or .docx resume (``str`` or ``pathlib.Path``).

Outputs:
    ``ParsedResume``: Validated, normalized structured resume data.

Example usage:
    >>> from resume_processing.process_resume import process_resume
    >>> result = process_resume("candidates/jane_doe.pdf")
    >>> print(result.skills)
    >>> result = process_resume("candidates/jane_doe.docx")  # also supported

Design notes:
    - Thin orchestrator: no business logic, only stage sequencing.
    - Each stage raises domain-specific exceptions from ``exceptions.py``.
    - File validation happens here (before extraction) to fail fast.
    - Originally PDF-only. DOCX support was added via ``docx_extractor.py``
      using the same extension-based dispatch pattern as the rest of the
      pipeline, rather than a separate code path, so every downstream stage
      (cleaning, parsing, validation, normalization) is unaffected by which
      file format the raw text came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from resume_processing.docx_extractor import extract_text_from_docx
from resume_processing.exceptions import FileValidationError
from resume_processing.normalizer import normalize_resume
from resume_processing.pdf_extractor import extract_text_from_pdf
from resume_processing.schema import ParsedResume
from resume_processing.text_cleaner import clean_text
from resume_processing.validator import parse_and_validate_resume

PathLike = Union[str, Path]

_SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def _extract_raw_text(resume_file: PathLike) -> str:
    """
    Extract raw text from a resume file, dispatching by extension.

    Raises:
        FileValidationError: Unsupported file extension.
        PDFExtractionError / DocxExtractionError: Extraction failure.
    """
    suffix = Path(resume_file).suffix.lower()

    if suffix == ".pdf":
        return extract_text_from_pdf(resume_file)
    if suffix == ".docx":
        return extract_text_from_docx(resume_file)

    supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
    raise FileValidationError(
        f"Unsupported resume file type '{suffix}'. Supported types: {supported}."
    )


def process_resume_with_raw_text(resume_file: PathLike) -> tuple[str, ParsedResume]:
    """
    Process a resume (PDF or DOCX) and also return the raw extracted text.

    Useful when a caller needs to persist the original extracted text (e.g.
    the database layer's ``resumes.raw_text`` column) alongside the parsed
    structure, without extracting the file or calling the GLM API twice.

    Args:
        resume_file: Filesystem path to the resume (.pdf or .docx).

    Returns:
        Tuple of ``(raw_text, parsed_resume)``.

    Raises:
        FileValidationError: Invalid, missing, or unsupported input file.
        PDFExtractionError / DocxExtractionError: Text extraction failure.
        TextCleaningError: Text cleaning failure.
        ResumeParsingError: GLM API failure.
        ValidationError: Schema validation failure after retry.
        NormalizationError: Normalization failure.
    """
    raw_text = _extract_raw_text(resume_file)
    cleaned_text = clean_text(raw_text)
    parsed_resume = parse_and_validate_resume(cleaned_text)
    normalized = normalize_resume(parsed_resume)
    return raw_text, normalized


def process_resume(resume_file: PathLike) -> ParsedResume:
    """
    Process a resume (PDF or DOCX) through the full extraction and parsing
    pipeline.

    Args:
        resume_file: Filesystem path to the resume (.pdf or .docx).

    Returns:
        Validated and normalized ``ParsedResume``.

    Raises:
        FileValidationError: Invalid, missing, or unsupported input file.
        PDFExtractionError / DocxExtractionError: Text extraction failure.
        TextCleaningError: Text cleaning failure.
        ResumeParsingError: GLM API failure.
        ValidationError: Schema validation failure after retry.
        NormalizationError: Normalization failure.
    """
    _, parsed_resume = process_resume_with_raw_text(resume_file)
    return parsed_resume
