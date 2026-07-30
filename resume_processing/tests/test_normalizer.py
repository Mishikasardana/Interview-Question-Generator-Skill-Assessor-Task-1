"""Unit tests for normalizer.py."""

import pytest

from resume_processing.exceptions import NormalizationError
from resume_processing.normalizer import normalize_resume
from resume_processing.schema import ParsedResume


def test_normalize_resume_normalizes_skill_aliases() -> None:
    resume = ParsedResume(skills=["python", "JS", "nodejs", "postgres"])

    result = normalize_resume(resume)

    assert result.skills == ["Python", "JavaScript", "Node.js", "PostgreSQL"]


def test_normalize_resume_removes_duplicate_and_blank_values() -> None:
    resume = ParsedResume(
        name="  Jane   Doe  ",
        skills=[" Python ", "python", "", "  SQL  "],
        projects=[" Interview   Tracker ", "interview tracker", ""],
    )

    result = normalize_resume(resume)

    assert result.name == "Jane Doe"
    assert result.skills == ["Python", "SQL"]
    assert result.projects == ["Interview Tracker"]


def test_normalize_resume_preserves_unknown_skills() -> None:
    resume = ParsedResume(skills=["FastAPI", "Pandas"])

    result = normalize_resume(resume)

    assert result.skills == ["FastAPI", "Pandas"]


def test_normalize_resume_rejects_wrong_input_type() -> None:
    with pytest.raises(NormalizationError):
        normalize_resume({"skills": ["Python"]})  # type: ignore[arg-type]
