"""
Data normalization module.

Purpose:
    Normalize common aliases in parsed resume data (e.g., ``python`` →
    ``Python``, ``js`` → ``JavaScript``). Keeps output consistent for
    downstream matching and search.

Inputs:
    Validated ``ParsedResume`` from ``validator.py``.

Outputs:
    Normalized ``ParsedResume`` (same schema, cleaned values).

Example usage:
    >>> from resume_processing.normalizer import normalize_resume
    >>> normalized = normalize_resume(parsed_resume)

Design notes:
    - Only alias-based normalization (dict lookup), no NLP.
    - Applied primarily to ``skills``; other fields normalized minimally.
    - Pure function — easy to test and extend with new aliases.
"""

from __future__ import annotations

from collections.abc import Iterable

from resume_processing.exceptions import NormalizationError
from resume_processing.schema import ParsedResume

_SKILL_ALIASES = {
    "py": "Python",
    "python": "Python",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgre sql": "PostgreSQL",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
}


def _normalize_text(value: str) -> str:
    """Trim surrounding whitespace and collapse internal repeated spaces."""
    return " ".join(value.strip().split())


def _normalize_skill(skill: str) -> str:
    """Normalize one skill using alias lookup, preserving unknown skills."""
    cleaned = _normalize_text(skill)
    if not cleaned:
        return ""

    lookup_key = cleaned.casefold()
    return _SKILL_ALIASES.get(lookup_key, cleaned)


def _deduplicate(values: Iterable[str]) -> list[str]:
    """Return values in original order after removing blank and duplicate items."""
    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = _normalize_text(value)
        if not cleaned:
            continue

        lookup_key = cleaned.casefold()
        if lookup_key in seen:
            continue

        seen.add(lookup_key)
        normalized_values.append(cleaned)

    return normalized_values


def normalize_resume(resume: ParsedResume) -> ParsedResume:
    """
    Normalize common value aliases in a parsed resume.

    Args:
        resume: Validated parsed resume data.

    Returns:
        A new ``ParsedResume`` with normalized field values.

    Raises:
        NormalizationError: If normalization fails unexpectedly.
    """
    if not isinstance(resume, ParsedResume):
        raise NormalizationError(
            f"Expected ParsedResume for normalization, got {type(resume).__name__}."
        )

    try:
        normalized_skills = _deduplicate(
            skill
            for skill in (_normalize_skill(item) for item in resume.skills)
            if skill
        )

        return resume.model_copy(
            update={
                "name": _normalize_text(resume.name),
                "email": _normalize_text(resume.email),
                "phone": _normalize_text(resume.phone),
                "linkedin": _normalize_text(resume.linkedin),
                "github": _normalize_text(resume.github),
                "skills": normalized_skills,
                "education": _deduplicate(resume.education),
                "experience": _deduplicate(resume.experience),
                "projects": _deduplicate(resume.projects),
                "certifications": _deduplicate(resume.certifications),
            }
        )
    except Exception as exc:
        if isinstance(exc, NormalizationError):
            raise
        raise NormalizationError(f"Failed to normalize resume: {exc}") from exc
