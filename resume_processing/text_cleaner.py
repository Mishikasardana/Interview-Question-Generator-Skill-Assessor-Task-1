"""
Text cleaning module.

Purpose:
    Remove formatting artifacts from extracted PDF text without altering
    semantic content. Prepares clean input for the LLM parser.

Inputs:
    Raw text string from ``pdf_extractor.py``.

Outputs:
    Cleaned text string with normalized whitespace.

Cleaning rules (MVP):
    - Collapse multiple blank lines to a single blank line.
    - Replace tabs with spaces.
    - Collapse repeated spaces within a line.
    - Trim leading/trailing whitespace from the final text.

Example usage:
    >>> from resume_processing.text_cleaner import clean_text
    >>> cleaned = clean_text("Hello    world\\n\\n\\nNext line")
    >>> print(cleaned)

Note:
    This module intentionally does NOT modify actual resume content
    (names, skills, dates, etc.).
"""

from __future__ import annotations

import re

from resume_processing.exceptions import TextCleaningError

_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
_REPEATED_SPACES = re.compile(r" {2,}")


def clean_text(raw_text: str) -> str:
    """
    Clean formatting artifacts from extracted resume text.

    Args:
        raw_text: Raw text extracted from a PDF.

    Returns:
        Text with normalized whitespace.

    Raises:
        TextCleaningError: If input is not a string.
    """
    if not isinstance(raw_text, str):
        raise TextCleaningError(
            f"Expected str for text cleaning, got {type(raw_text).__name__}."
        )

    if not raw_text:
        return ""

    text = raw_text.replace("\t", " ")

    lines = [_REPEATED_SPACES.sub(" ", line) for line in text.split("\n")]
    text = "\n".join(lines)

    # Three or more newlines means two or more blank lines — keep only one.
    text = _MULTIPLE_BLANK_LINES.sub("\n\n", text)

    return text.strip()
