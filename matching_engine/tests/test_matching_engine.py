"""Tests for matching_engine.matching_engine — pure logic, no network calls."""

from __future__ import annotations

import pytest

from matching_engine import MatchingEngineError, run_matching

SAMPLE_RESUME = {
    "name": "Arjun Mehta",
    "skills": ["Python", "PyTorch", "FastAPI", "PostgreSQL", "Docker", "React"],
    "projects": [
        {
            "name": "Anomaly Detection System",
            "description": (
                "Built a computer vision pipeline using scikit-learn and "
                "OpenCV for industrial inspection."
            ),
        }
    ],
    "experience": [
        {
            "role": "ML Intern",
            "description": (
                "Trained transformer models using HuggingFace on "
                "multilingual datasets."
            ),
        }
    ],
}

SAMPLE_JD = {
    "role": "ML Engineer",
    "required_skills": [
        "Python", "PyTorch", "HuggingFace", "REST API", "Docker", "SQL",
    ],
    "preferred_skills": [
        "Kubernetes", "scikit-learn", "Computer Vision", "AWS", "Redis",
    ],
}


def test_run_matching_returns_match_result():
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    assert 0 <= result.score <= 100


def test_run_matching_matches_exact_required_skills():
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    assert "Python" in result.matched_required
    assert "PyTorch" in result.matched_required


def test_run_matching_flags_missing_required_skills():
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    # Candidate has neither "SQL" nor "REST API" as an explicit skill.
    assert "SQL" in result.missing_required or "REST API" in result.missing_required


def test_run_matching_infers_skills_from_free_text():
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    # "HuggingFace" appears only in the experience description, not the
    # skills list, so it should show up as an inferred skill.
    assert "HuggingFace" in result.inferred_skills


def test_run_matching_produces_skill_gap_entries():
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    assert isinstance(result.skill_gap, list)
    assert all(hasattr(gap, "skill") for gap in result.skill_gap)


def test_run_matching_empty_resume_still_returns_result():
    result = run_matching({}, SAMPLE_JD)
    assert result.score >= 0
    assert result.matched_required == []


def test_run_matching_rejects_non_dict_resume():
    with pytest.raises(MatchingEngineError):
        run_matching(["not", "a", "dict"], SAMPLE_JD)


def test_run_matching_rejects_non_dict_jd():
    with pytest.raises(MatchingEngineError):
        run_matching(SAMPLE_RESUME, "not a dict either")


def test_run_matching_rejects_non_list_skill_fields():
    with pytest.raises(MatchingEngineError, match="Expected list for skills"):
        run_matching({"skills": "Python"}, SAMPLE_JD)

    with pytest.raises(MatchingEngineError, match="Expected list for required_skills"):
        run_matching(SAMPLE_RESUME, {"required_skills": "Python"})


def test_run_matching_rejects_non_string_skill_entries():
    with pytest.raises(MatchingEngineError, match="entries to be strings"):
        run_matching({"skills": ["Python", 123]}, SAMPLE_JD)


def test_run_matching_ignores_non_text_project_and_experience_values():
    resume = {
        "skills": [],
        "projects": [{"name": "API", "technologies": ["Python", 42, None]}],
        "experience": [{"role": "Engineer", "tools": ["Docker", object()]}],
    }
    jd = {
        "required_skills": ["Python", "Docker"],
        "preferred_skills": [],
    }

    result = run_matching(resume, jd)

    assert result.matched_required == ["Python", "Docker"]
    assert result.inferred_skills == ["Python", "Docker"]


def test_match_result_to_dict_round_trips_json_serialisable():
    import json

    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)
    serialised = json.dumps(result.to_dict())
    assert isinstance(serialised, str)


def test_education_score_ignores_words_containing_degree_substrings():
    # "resume" and "described" both contain the substring "me "/"be " that a
    # naive `in` check would misread as the "M.E."/"B.E." degree keywords.
    # required_skills/preferred_skills are left empty so required/preferred/
    # project/experience coverage all default to full marks, isolating the
    # education component: with no *real* degree requirement in the JD, the
    # overall score should stay at 100 rather than being docked for a
    # phantom degree gap.
    resume = {"skills": [], "education": []}
    jd = {
        "required_skills": [],
        "preferred_skills": [],
        "education_requirement": "",
        "experience_level": "Please submit your resume as described below.",
    }

    result = run_matching(resume, jd)

    assert result.score == pytest.approx(100.0)


def test_education_score_still_detects_real_degree_requirement():
    resume = {"skills": [], "education": ["Bachelor of Technology in CS"]}
    jd = {
        "required_skills": [],
        "preferred_skills": [],
        "education_requirement": "Master's degree required",
        "experience_level": "",
    }

    result = run_matching(resume, jd)

    # Candidate only has a Bachelor's (level 2) against a Master's (level 3)
    # requirement — one level short, so education contributes half credit
    # (0.5 * 10% = 5) rather than full (10) or zero.
    assert result.score == pytest.approx(95.0)
