"""Tests for recruiter_intelligence.hard_requirement_gate — pure logic, no mocking."""

from __future__ import annotations

from jd_parsing.schema import HardRequirement, ParsedJD
from recruiter_intelligence.hard_requirement_gate import evaluate_hard_requirements
from resume_processing.schema import ParsedResume


def _jd(**hard_requirements_kwargs) -> ParsedJD:
    return ParsedJD(
        role="Backend Engineer",
        hard_requirements=[HardRequirement(**hard_requirements_kwargs)],
    )


def test_no_hard_requirements_passes_by_default():
    jd = ParsedJD(role="Backend Engineer")
    resume = ParsedResume(name="Jane")

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "pass"
    assert result.results == []


def test_min_experience_years_passes_when_estimate_meets_threshold():
    jd = _jd(type="min_experience_years", description="3+ years", minimum_value="3 years")
    resume = ParsedResume(name="Jane", estimated_total_experience_years=4.0)

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "pass"
    assert result.results[0].status == "pass"


def test_min_experience_years_fails_when_estimate_is_below_threshold():
    jd = _jd(type="min_experience_years", description="5+ years", minimum_value="5 years")
    resume = ParsedResume(name="Jane", estimated_total_experience_years=2.0)

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "fail"
    assert result.results[0].status == "fail"


def test_min_experience_years_needs_review_when_resume_has_no_estimate():
    jd = _jd(type="min_experience_years", description="5+ years", minimum_value="5 years")
    resume = ParsedResume(name="Jane", estimated_total_experience_years=None)

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "needs_human_review"


def test_degree_passes_when_candidate_meets_required_level():
    jd = _jd(type="degree", description="Bachelor's degree required", minimum_value="Bachelor's")
    resume = ParsedResume(name="Jane", education=["M.S. Computer Science, State University"])

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "pass"


def test_degree_fails_when_candidate_below_required_level():
    jd = _jd(type="degree", description="Master's degree required", minimum_value="Master's")
    resume = ParsedResume(name="Jane", education=["B.S. Computer Science, State University"])

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "fail"


def test_degree_word_boundary_ignores_substring_false_positives():
    # "resume"/"described" must not be misread as containing "me"/"be" --
    # mirrors matching_engine's own word-boundary regression test.
    jd = _jd(type="degree", description="Bachelor's degree required", minimum_value="Bachelor's")
    resume = ParsedResume(
        name="Jane",
        education=["As described in my resume, I have a Bachelor's degree."],
    )

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "pass"


def test_certification_passes_when_present():
    jd = _jd(type="certification", description="AWS certification", minimum_value="AWS Certified Solutions Architect")
    resume = ParsedResume(name="Jane", certifications=["AWS Certified Solutions Architect - Associate"])

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "pass"


def test_certification_fails_when_absent():
    jd = _jd(type="certification", description="PMP certification", minimum_value="PMP")
    resume = ParsedResume(name="Jane", certifications=["AWS Certified Solutions Architect"])

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "fail"


def test_clearance_always_needs_human_review_never_guessed():
    jd = _jd(type="clearance", description="Active Top Secret clearance", minimum_value="Top Secret")
    resume = ParsedResume(name="Jane")

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "needs_human_review"
    assert result.results[0].status == "needs_human_review"


def test_visa_always_needs_human_review_never_guessed():
    jd = _jd(type="visa", description="Must be authorized to work in the US")
    resume = ParsedResume(name="Jane")

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "needs_human_review"


def test_location_always_needs_human_review_never_guessed():
    jd = _jd(type="location", description="Must be based in New York")
    resume = ParsedResume(name="Jane")

    result = evaluate_hard_requirements(jd, resume)

    assert result.overall_status == "needs_human_review"


def test_non_mandatory_requirement_does_not_gate_on_failure():
    jd = _jd(
        type="degree", description="Master's preferred", minimum_value="Master's",
        is_mandatory=False,
    )
    resume = ParsedResume(name="Jane", education=["B.S. Computer Science"])

    result = evaluate_hard_requirements(jd, resume)

    # A soft ("preferred") requirement never gates the candidate out, even
    # though the candidate doesn't technically meet it.
    assert result.overall_status == "pass"
    assert result.results[0].status == "pass"


def test_any_mandatory_failure_dominates_overall_status():
    jd = ParsedJD(
        role="Backend Engineer",
        hard_requirements=[
            HardRequirement(type="clearance", description="Top Secret clearance"),
            HardRequirement(type="degree", description="PhD required", minimum_value="PhD"),
        ],
    )
    resume = ParsedResume(name="Jane", education=["B.S. Computer Science"])

    result = evaluate_hard_requirements(jd, resume)

    # One NEEDS_HUMAN_REVIEW (clearance) and one FAIL (degree) -- FAIL wins.
    assert result.overall_status == "fail"
