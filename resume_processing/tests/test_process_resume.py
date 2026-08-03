"""Unit tests for process_resume.py."""

from unittest.mock import MagicMock, patch

from resume_processing.process_resume import (
    process_resume,
    process_resume_with_raw_text,
)
from resume_processing.schema import ParsedResume


@patch("resume_processing.process_resume.normalize_resume")
@patch("resume_processing.process_resume.parse_and_validate_resume")
@patch("resume_processing.process_resume.clean_text")
@patch("resume_processing.process_resume.extract_text_from_pdf")
def test_process_resume_runs_pipeline_in_order(
    mock_extract: MagicMock,
    mock_clean: MagicMock,
    mock_parse_validate: MagicMock,
    mock_normalize: MagicMock,
) -> None:
    parsed = ParsedResume(name="Jane Doe", skills=["python"])
    normalized = ParsedResume(name="Jane Doe", skills=["Python"])
    mock_extract.return_value = "Raw   text"
    mock_clean.return_value = "Raw text"
    mock_parse_validate.return_value = parsed
    mock_normalize.return_value = normalized

    result = process_resume("resume.pdf")

    assert result == normalized
    mock_extract.assert_called_once_with("resume.pdf")
    mock_clean.assert_called_once_with("Raw   text")
    mock_parse_validate.assert_called_once_with("Raw text")
    mock_normalize.assert_called_once_with(parsed)


@patch("resume_processing.process_resume.normalize_resume")
@patch("resume_processing.process_resume.parse_and_validate_resume")
@patch("resume_processing.process_resume.clean_text")
@patch("resume_processing.process_resume.extract_text_from_docx")
def test_process_resume_dispatches_docx_files_to_docx_extractor(
    mock_extract: MagicMock,
    mock_clean: MagicMock,
    mock_parse_validate: MagicMock,
    mock_normalize: MagicMock,
) -> None:
    parsed = ParsedResume(name="Jane Doe", skills=["python"])
    mock_extract.return_value = "Raw docx text"
    mock_clean.return_value = "Raw docx text"
    mock_parse_validate.return_value = parsed
    mock_normalize.return_value = parsed

    result = process_resume("resume.docx")

    assert result == parsed
    mock_extract.assert_called_once_with("resume.docx")


def test_process_resume_rejects_unsupported_extension():
    from resume_processing.exceptions import FileValidationError

    import pytest

    with pytest.raises(FileValidationError):
        process_resume("resume.txt")


@patch("resume_processing.process_resume.normalize_resume")
@patch("resume_processing.process_resume.parse_and_validate_resume")
@patch("resume_processing.process_resume.clean_text")
@patch("resume_processing.process_resume.extract_text_from_pdf")
def test_process_resume_with_raw_text_returns_both(
    mock_extract: MagicMock,
    mock_clean: MagicMock,
    mock_parse_validate: MagicMock,
    mock_normalize: MagicMock,
) -> None:
    parsed = ParsedResume(name="Jane Doe", skills=["python"])
    normalized = ParsedResume(name="Jane Doe", skills=["Python"])
    mock_extract.return_value = "Raw   text"
    mock_clean.return_value = "Raw text"
    mock_parse_validate.return_value = parsed
    mock_normalize.return_value = normalized

    raw_text, result = process_resume_with_raw_text("resume.pdf")

    assert raw_text == "Raw   text"
    assert result == normalized
    # Only one extraction call — process_resume() must not re-extract or
    # re-call the (expensive) GLM parser a second time to get raw text.
    mock_extract.assert_called_once_with("resume.pdf")
    mock_parse_validate.assert_called_once_with("Raw text")

