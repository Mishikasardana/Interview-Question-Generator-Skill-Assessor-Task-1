"""Unit tests for pdf_extractor.py."""

from unittest.mock import MagicMock, patch

import pytest

from resume_processing.exceptions import FileValidationError, PDFExtractionError
from resume_processing.pdf_extractor import extract_text_from_pdf, validate_pdf_file


def test_validate_pdf_file_accepts_pdf_with_magic_bytes(tmp_path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")

    result = validate_pdf_file(pdf_path)

    assert result == pdf_path.resolve()


def test_validate_pdf_file_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileValidationError, match="not found"):
        validate_pdf_file(tmp_path / "missing.pdf")


def test_validate_pdf_file_rejects_non_pdf_extension(tmp_path) -> None:
    text_path = tmp_path / "resume.txt"
    text_path.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(FileValidationError, match=".pdf"):
        validate_pdf_file(text_path)


def test_validate_pdf_file_rejects_invalid_magic_bytes(tmp_path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_text("not a real pdf", encoding="utf-8")

    with pytest.raises(FileValidationError, match="valid PDF"):
        validate_pdf_file(pdf_path)


@patch("resume_processing.pdf_extractor.PdfReader")
def test_extract_text_from_pdf_combines_page_text(
    mock_reader_class: MagicMock, tmp_path
) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")
    page_one = MagicMock()
    page_one.extract_text.return_value = "Jane Doe"
    page_two = MagicMock()
    page_two.extract_text.return_value = "Python Developer"
    mock_reader = MagicMock(is_encrypted=False, pages=[page_one, page_two])
    mock_reader_class.return_value = mock_reader

    result = extract_text_from_pdf(pdf_path)

    assert result == "Jane Doe\nPython Developer"


@patch("resume_processing.pdf_extractor.PdfReader")
def test_extract_text_from_pdf_rejects_encrypted_pdf(
    mock_reader_class: MagicMock, tmp_path
) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ncontent")
    mock_reader_class.return_value = MagicMock(is_encrypted=True)

    with pytest.raises(PDFExtractionError, match="password-protected"):
        extract_text_from_pdf(pdf_path)
