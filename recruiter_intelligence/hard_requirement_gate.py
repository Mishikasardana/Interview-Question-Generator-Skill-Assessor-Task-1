"""
Stage B of the Recruiter Intelligence Engine: the deterministic
hard-requirement gate.

Pure Python, no LLM call, no network access — every verdict here must be
reproducible and explainable from the resume/JD data alone. See the
approved plan's hard-requirement strategy: clearance/visa/location are
generally NOT reliably verifiable from a resume, so this deliberately
routes those to NEEDS_HUMAN_REVIEW rather than guessing PASS or FAIL —
guessing immigration or clearance status from a resume would be both
inaccurate and a fairness risk, not just a nicety.

A small, local degree-level heuristic mirrors matching_engine._education_score
in spirit (word-boundary keyword matching against a 4-tier degree ladder)
rather than importing it — recruiter_intelligence must not reach into
matching_engine's private internals, matching the same principle already
applied to skill_ontology.py's normalization function.
"""

from __future__ import annotations

import re

from jd_parsing.schema import HardRequirement, ParsedJD
from recruiter_intelligence.schema import HardGateResult, HardRequirementResult
from resume_processing.schema import ParsedResume

_DEGREE_LEVELS: dict[str, int] = {
    "phd": 4, "doctorate": 4,
    "master": 3, "msc": 3, "ms": 3, "ma": 3, "mtech": 3, "mba": 3,
    "bachelor": 2, "btech": 2, "bsc": 2, "bs": 2, "ba": 2, "bca": 2,
    "diploma": 1, "associate": 1,
}

_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _word_in_text(text: str, word: str) -> bool:
    return bool(re.search(r"\b" + re.escape(word) + r"\b", text))


def _degree_level(text: str) -> int:
    # Strip periods first so common dotted abbreviations ("M.S.", "B.S.",
    # "Ph.D.") normalize to the same tokens as their undotted forms
    # ("ms", "bs", "phd") before word-boundary matching.
    text = text.lower().replace(".", "")
    return max((level for keyword, level in _DEGREE_LEVELS.items() if _word_in_text(text, keyword)), default=0)


def _extract_minimum_years(minimum_value: str, description: str) -> float | None:
    """Best-effort extraction of a numeric year threshold from JD text."""
    match = _NUMBER_RE.search(minimum_value) or _NUMBER_RE.search(description)
    return float(match.group(1)) if match else None


def _evaluate_min_experience_years(
    hard_req: HardRequirement, total_years: float | None,
) -> HardRequirementResult:
    required_years = _extract_minimum_years(hard_req.minimum_value, hard_req.description)
    if required_years is None:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description,
            status="needs_human_review",
            reason="Could not determine a specific numeric year threshold from the JD text.",
        )
    if total_years is None:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description,
            status="needs_human_review",
            reason="Resume did not state enough dated experience to estimate total years.",
        )
    if total_years >= required_years:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description, status="pass",
            reason=f"Estimated {total_years} years of experience meets the {required_years}-year requirement.",
        )
    return HardRequirementResult(
        type=hard_req.type, description=hard_req.description, status="fail",
        reason=f"Estimated {total_years} years of experience is below the {required_years}-year requirement.",
    )


def _evaluate_degree(hard_req: HardRequirement, education: list[str]) -> HardRequirementResult:
    required_level = _degree_level(f"{hard_req.minimum_value} {hard_req.description}")
    if required_level == 0:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description,
            status="needs_human_review",
            reason="Could not determine a specific degree level from the JD text.",
        )
    candidate_level = _degree_level(" ".join(education))
    if candidate_level >= required_level:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description, status="pass",
            reason="Resume's education entries meet or exceed the required degree level.",
        )
    return HardRequirementResult(
        type=hard_req.type, description=hard_req.description, status="fail",
        reason="Resume's education entries do not show the required degree level.",
    )


def _evaluate_certification(hard_req: HardRequirement, certifications: list[str]) -> HardRequirementResult:
    needle = (hard_req.minimum_value or hard_req.description).strip().lower()
    if not needle:
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description,
            status="needs_human_review",
            reason="Could not determine which specific certification is required.",
        )
    haystack = " ".join(certifications).lower()
    if needle in haystack or any(needle in cert.lower() or cert.lower() in needle for cert in certifications):
        return HardRequirementResult(
            type=hard_req.type, description=hard_req.description, status="pass",
            reason="A matching certification was found on the resume.",
        )
    return HardRequirementResult(
        type=hard_req.type, description=hard_req.description, status="fail",
        reason="No matching certification was found on the resume.",
    )


_NOT_VERIFIABLE_REASON = (
    "Not reliably verifiable from a resume alone — routed to a human "
    "recruiter rather than guessed, to avoid an inaccurate or unfair "
    "automated determination."
)


def evaluate_hard_requirements(jd: ParsedJD, resume: ParsedResume) -> HardGateResult:
    """
    Evaluate every hard requirement on the JD against the resume.

    Returns a HardGateResult whose overall_status is:
      - "fail" if ANY mandatory hard requirement fails
      - "needs_human_review" if none fail but at least one couldn't be
        determined automatically
      - "pass" otherwise (including when there are no hard requirements at all)
    """
    results: list[HardRequirementResult] = []

    for hard_req in jd.hard_requirements:
        if hard_req.type == "min_experience_years":
            result = _evaluate_min_experience_years(
                hard_req, resume.estimated_total_experience_years,
            )
        elif hard_req.type == "degree":
            result = _evaluate_degree(hard_req, resume.education)
        elif hard_req.type == "certification":
            result = _evaluate_certification(hard_req, resume.certifications)
        else:
            # clearance, visa, location, other -- never guessed.
            result = HardRequirementResult(
                type=hard_req.type, description=hard_req.description,
                status="needs_human_review", reason=_NOT_VERIFIABLE_REASON,
            )

        if not hard_req.is_mandatory and result.status == "fail":
            # The JD itself softened this one (e.g. "preferred" not
            # "required") -- a miss here is informational, not disqualifying.
            result = HardRequirementResult(
                type=result.type, description=result.description, status="pass",
                reason=f"{result.reason} (not mandatory per the JD's own wording, so this does not gate the candidate.)",
            )

        results.append(result)

    if any(r.status == "fail" for r in results):
        overall = "fail"
    elif any(r.status == "needs_human_review" for r in results):
        overall = "needs_human_review"
    else:
        overall = "pass"

    return HardGateResult(overall_status=overall, results=results)
