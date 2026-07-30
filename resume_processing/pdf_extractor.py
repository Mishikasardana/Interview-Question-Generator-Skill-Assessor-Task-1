"""
PDF text extraction module.

Purpose:
    Extract raw text from text-based PDF resume files using ``pypdf``.
    This is the first transformation step after file validation.

Inputs:
    Path to a valid PDF file (``str`` or ``pathlib.Path``).

Outputs:
    Raw extracted text as a single string (may contain formatting artifacts).

Example usage:
    >>> from resume_processing.pdf_extractor import extract_text_from_pdf
    >>> text = extract_text_from_pdf("resume.pdf")
    >>> print(text[:200])

Assumptions:
    - PDFs are text-based (no OCR support in this MVP).
    - All pages are extracted and concatenated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from resume_processing.exceptions import FileValidationError, PDFExtractionError

PathLike = Union[str, Path]

# PDF files begin with this magic byte sequence (PDF spec §7.5.2).
_PDF_MAGIC_BYTES = b"%PDF"


def validate_pdf_file(pdf_path: PathLike) -> Path:
    """
    Validate that a path points to a readable, non-empty PDF file.

    Args:
        pdf_path: Filesystem path to the candidate PDF.

    Returns:
        Resolved absolute ``Path`` to the validated file.

    Raises:
        FileValidationError: If the path is missing, not a file, empty,
            or does not appear to be a PDF.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileValidationError(f"Resume file not found: {path}")

    if not path.is_file():
        raise FileValidationError(f"Path is not a file: {path}")

    if path.stat().st_size == 0:
        raise FileValidationError(f"Resume file is empty: {path}")

    # Extension check is a fast pre-filter; magic bytes catch misnamed files.
    if path.suffix.lower() != ".pdf":
        raise FileValidationError(
            f"Expected a .pdf file, got '{path.suffix}' for: {path}"
        )

    try:
        header = path.read_bytes()[:4]
    except OSError as exc:
        raise FileValidationError(f"Cannot read resume file: {path}") from exc

    if not header.startswith(_PDF_MAGIC_BYTES):
        raise FileValidationError(f"File does not appear to be a valid PDF: {path}")

    return path.resolve()


def extract_text_from_pdf(pdf_path: PathLike) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Filesystem path to the PDF resume.

    Returns:
        Concatenated text from all pages, joined with newline characters.

    Raises:
        FileValidationError: If the file does not exist or is not a valid PDF.
        PDFExtractionError: If the PDF cannot be read, is encrypted, or
            contains no extractable text.
    """
    path = validate_pdf_file(pdf_path)

    try:
        reader = PdfReader(str(path))
    except (PdfReadError, PdfStreamError, OSError) as exc:
        raise PDFExtractionError(
            f"Failed to open PDF '{path.name}': {exc}"
        ) from exc

    if reader.is_encrypted:
        raise PDFExtractionError(
            f"PDF '{path.name}' is password-protected and cannot be processed."
        )

    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text()
        except Exception as exc:
            raise PDFExtractionError(
                f"Failed to extract text from page {page_number} of "
                f"'{path.name}': {exc}"
            ) from exc

        if page_text:
            page_texts.append(page_text)

    if not page_texts:
        raise PDFExtractionError(
            f"No extractable text found in '{path.name}'. "
            "The PDF may be image-only (scanned). OCR is not supported."
        )

    return "\n".join(page_texts)
