"""Unit tests for text_cleaner.py."""

import pytest

from resume_processing.exceptions import TextCleaningError
from resume_processing.text_cleaner import clean_text


def test_replaces_tabs_with_spaces() -> None:
    assert clean_text("hello\tworld") == "hello world"


def test_collapses_repeated_spaces_within_line() -> None:
    assert clean_text("hello    world") == "hello world"


def test_collapses_multiple_blank_lines() -> None:
    assert clean_text("line one\n\n\n\nline two") == "line one\n\nline two"


def test_preserves_single_blank_line() -> None:
    assert clean_text("line one\n\nline two") == "line one\n\nline two"


def test_trims_outer_whitespace() -> None:
    assert clean_text("\n\n  hello   world  \n") == "hello world"


def test_does_not_change_words() -> None:
    raw = "Python   Developer\n\n\nPostgreSQL"
    cleaned = clean_text(raw)
    assert "Python Developer" in cleaned
    assert "PostgreSQL" in cleaned


def test_empty_string_returns_empty() -> None:
    assert clean_text("") == ""


def test_rejects_non_string_input() -> None:
    with pytest.raises(TextCleaningError):
        clean_text(None)  # type: ignore[arg-type]
