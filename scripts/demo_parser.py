#!/usr/bin/env python3
"""
Demo script for the Resume Parser module (Option B).

Reads a plain-text resume file, cleans it, calls GLM, validates JSON,
and prints the structured result.

Usage:
    python scripts/demo_parser.py samples/resume_sample.txt

Requires:
    GLM_API_KEY set in .env or environment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from resume_processing.text_cleaner import clean_text
from resume_processing.validator import parse_and_validate_resume


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/demo_parser.py <path-to-resume.txt>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.is_file():
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    raw_text = input_path.read_text(encoding="utf-8")
    cleaned_text = clean_text(raw_text)
    parsed = parse_and_validate_resume(cleaned_text)

    print(json.dumps(parsed.model_dump(), indent=2))


if __name__ == "__main__":
    main()
