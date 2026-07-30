"""
Tests for recruiter_intelligence.aggregation — pure logic, no mocking, no
LLM calls, no network.

Uses a test-specific ScoringConfig fixture (not the production
scoring_config.yaml) so these tests assert behavior given KNOWN parameters,
decoupled from whatever the shipped config's values happen to be — this is
what lets the config get recalibrated later without editing dozens of
expected-value assertions (see the approved plan, section 6.1).
"""

from __future__ import annotations

import pytest

from recruiter_intelligence.aggregation import (
    aggregate,
    attach_contributions,
    build_requirement_breakdown,
    compile_narrative,
    compute_confidence,
    compute_final_weight,
    compute_recommendation,
    compute_weighted_average,
    tier_missing_skills,
    verify_evidence_snippet,
)
from recruiter_intelligence.hard_requirement_gate import evaluate_hard_requirements
from recruiter_intelligence.schema import (
    HardGateResult,
    HardRequirementResult,
    Requirement,
    RequirementBreakdown,
    RequirementEvidence,
    RequirementScore,
    StageAResult,
    StageCResult,
)
from recruiter_intelligence.scoring_config import ScoringConfig
from jd_parsing.schema import HardRequirement, ParsedJD
from resume_processing.schema import ParsedResume

# Generic fixture for tests that don't care about evidence verification --
# just needs to be a valid ParsedResume.
_TEST_RESUME = ParsedResume(name="Test Candidate", skills=["FastAPI"])

_TEST_CONFIG = ScoringConfig(
    version="test",
    calibrated=False,
    required_base_weight=1.0,
    preferred_base_weight=0.4,
    missing_score_threshold=20,
    difficulty_penalty_multiplier={"easy": 0.5, "medium": 1.0, "hard": 1.5, "specialized": 2.0},
    hard_gate_fail_score_cap=30,
    missing_skill_tier_rules={
        "required": {"easy": "minor", "medium": "minor", "hard": "critical", "specialized": "critical"},
        "preferred": {"easy": "nice_to_have", "medium": "nice_to_have", "hard": "minor", "specialized": "minor"},
    },
    confidence_evidence_completeness_min_share=0.7,
    recommendation_score_cutoffs={"strong_hire": 80, "consider": 60, "weak_match": 40},
)


def _requirement(**overrides) -> Requirement:
    defaults = dict(
        id="req_1", text="FastAPI", is_required=True, category="Backend Engineering",
        difficulty_tier="medium", why_it_matters="Core framework",
    )
    defaults.update(overrides)
    return Requirement(**defaults)


def _breakdown_item(**overrides) -> RequirementBreakdown:
    # RequirementBreakdown has no "score above missing-band requires
    # evidence" validator (unlike RequirementScore) -- used here to build
    # confidence-test fixtures representing a non-missing requirement with
    # NO verified evidence, a real state Phase 2's snippet-verification
    # check can produce even though the schema always guarantees at least
    # one raw citation exists whenever score > 20.
    defaults = dict(
        requirement_id="req_1", text="FastAPI", is_required=True, category="Backend Engineering",
        difficulty_tier="medium", score=90, final_weight=1.0, is_missing=False,
        evidence=[], verified_evidence_count=0, reasoning="ok",
    )
    defaults.update(overrides)
    return RequirementBreakdown(**defaults)


def _score(**overrides) -> RequirementScore:
    defaults = dict(
        requirement_id="req_1", score=85,
        evidence=[RequirementEvidence(category="skills", snippet="FastAPI")], reasoning="ok",
    )
    defaults.update(overrides)
    return RequirementScore(**defaults)


_PASSING_GATE = HardGateResult(overall_status="pass", results=[])
_REVIEW_GATE = HardGateResult(overall_status="needs_human_review", results=[
    HardRequirementResult(type="clearance", description="Top Secret", status="needs_human_review", reason="not verifiable"),
])
_FAIL_GATE = HardGateResult(overall_status="fail", results=[
    HardRequirementResult(type="degree", description="PhD required", status="fail", reason="Resume shows only a B.S."),
])


# --- verify_evidence_snippet (evidence-snippet verification guardrail) ---


def test_verify_evidence_snippet_true_for_exact_match():
    resume = ParsedResume(name="Jane", skills=["FastAPI", "PostgreSQL"])
    evidence = RequirementEvidence(category="skills", snippet="FastAPI")
    assert verify_evidence_snippet(evidence, resume) is True


def test_verify_evidence_snippet_normalizes_whitespace_and_case():
    resume = ParsedResume(name="Jane", projects=["Built a  Production   REST API with FastAPI."])
    evidence = RequirementEvidence(category="projects", snippet="production rest api with fastapi")
    assert verify_evidence_snippet(evidence, resume) is True


def test_verify_evidence_snippet_false_for_fabricated_citation():
    resume = ParsedResume(name="Jane", skills=["FastAPI"])
    evidence = RequirementEvidence(category="skills", snippet="Kubernetes")
    assert verify_evidence_snippet(evidence, resume) is False


def test_verify_evidence_snippet_false_for_empty_section():
    resume = ParsedResume(name="Jane", certifications=[])
    evidence = RequirementEvidence(category="certifications", snippet="AWS Certified")
    assert verify_evidence_snippet(evidence, resume) is False


# --- compute_final_weight (base weight + missing-difficulty-penalty only) ---


def test_compute_final_weight_required_outweighs_preferred():
    present_score = _score(score=90)
    required_weight = compute_final_weight(_requirement(is_required=True), present_score, _TEST_CONFIG)
    preferred_weight = compute_final_weight(_requirement(is_required=False), present_score, _TEST_CONFIG)
    assert required_weight > preferred_weight
    assert required_weight == _TEST_CONFIG.required_base_weight
    assert preferred_weight == _TEST_CONFIG.preferred_base_weight


def test_compute_final_weight_applies_difficulty_penalty_only_when_missing():
    missing_score = _score(score=10, evidence=[])
    present_score = _score(score=90)

    specialized_req = _requirement(difficulty_tier="specialized")
    missing_weight = compute_final_weight(specialized_req, missing_score, _TEST_CONFIG)
    present_weight = compute_final_weight(specialized_req, present_score, _TEST_CONFIG)

    # Missing + specialized multiplies the base weight; present never does.
    assert missing_weight == _TEST_CONFIG.required_base_weight * 2.0
    assert present_weight == _TEST_CONFIG.required_base_weight


def test_compute_final_weight_harder_missing_skill_weighs_more_than_easier_one():
    missing_score = _score(score=0, evidence=[])
    hard_weight = compute_final_weight(_requirement(difficulty_tier="specialized"), missing_score, _TEST_CONFIG)
    easy_weight = compute_final_weight(_requirement(difficulty_tier="easy"), missing_score, _TEST_CONFIG)
    assert hard_weight > easy_weight


# --- compute_weighted_average ---


def test_compute_weighted_average_weighs_required_over_preferred():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="FastAPI", is_required=True),
        _requirement(id="req_2", text="Kubernetes", is_required=False, category="DevOps & CI/CD"),
    ])
    stage_c = StageCResult(requirement_scores=[
        _score(requirement_id="req_1", score=100),
        _score(requirement_id="req_2", score=0, evidence=[]),
    ])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    avg = compute_weighted_average(breakdown)
    # Required FastAPI at 100 dominates over preferred Kubernetes at 0 --
    # not an unweighted 50 average.
    assert avg > 70


def test_compute_weighted_average_zero_weight_returns_zero():
    assert compute_weighted_average([]) == 0.0


# --- attach_contributions (explainability: traceable per-requirement shares) ---


def test_attach_contributions_sum_exactly_to_weighted_average():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="FastAPI", is_required=True),
        _requirement(id="req_2", text="PostgreSQL", is_required=True, category="Databases", difficulty_tier="easy"),
        _requirement(id="req_3", text="Kubernetes", is_required=False, category="DevOps & CI/CD", difficulty_tier="hard"),
    ])
    stage_c = StageCResult(requirement_scores=[
        _score(requirement_id="req_1", score=90),
        _score(requirement_id="req_2", score=70),
        _score(requirement_id="req_3", score=10, evidence=[]),
    ])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    breakdown = attach_contributions(breakdown)
    avg = compute_weighted_average(breakdown)

    assert sum(item.contribution for item in breakdown) == pytest.approx(avg)


def test_attach_contributions_higher_weight_and_score_contributes_more():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="FastAPI", is_required=True),
        _requirement(id="req_2", text="Rust", is_required=False, category="Other"),
    ])
    stage_c = StageCResult(requirement_scores=[
        _score(requirement_id="req_1", score=90),
        _score(requirement_id="req_2", score=90),
    ])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    breakdown = attach_contributions(breakdown)

    required_item = next(item for item in breakdown if item.requirement_id == "req_1")
    preferred_item = next(item for item in breakdown if item.requirement_id == "req_2")
    # Same score, but required carries more weight -- its contribution to
    # the final number must be larger.
    assert required_item.contribution > preferred_item.contribution


def test_attach_contributions_zero_weight_is_a_noop():
    assert attach_contributions([]) == []


# --- compute_confidence (redefined: red-flag count, not evidence density alone) ---


def test_compute_confidence_high_with_no_red_flags():
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement()])
    stage_c = StageCResult(requirement_scores=[_score()])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    level, reason = compute_confidence(breakdown, _PASSING_GATE, _TEST_CONFIG)
    assert level == "High"
    assert "no hard-gate ambiguity" in reason


def test_compute_confidence_medium_with_one_red_flag_sparse_evidence():
    breakdown = [
        _breakdown_item(
            requirement_id="req_1",
            evidence=[RequirementEvidence(category="skills", snippet="x")], verified_evidence_count=1,
        ),
        _breakdown_item(requirement_id="req_2", evidence=[]),
        _breakdown_item(requirement_id="req_3", evidence=[]),
        _breakdown_item(requirement_id="req_4", evidence=[]),
    ]
    level, reason = compute_confidence(breakdown, _PASSING_GATE, _TEST_CONFIG)
    assert level == "Medium"
    assert "1/4" in reason


def test_compute_confidence_low_with_two_red_flags_sparse_evidence_and_review():
    breakdown = [
        _breakdown_item(requirement_id="req_1", evidence=[]),
        _breakdown_item(requirement_id="req_2", evidence=[]),
    ]
    level, _reason = compute_confidence(breakdown, _REVIEW_GATE, _TEST_CONFIG)
    assert level == "Low"


def test_compute_confidence_missing_requirements_dont_count_against_evidence_completeness():
    # A genuinely missing requirement (score <= missing_threshold) has no
    # evidence by definition -- that must not itself count as a red flag,
    # only non-missing requirements lacking evidence should.
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1", text="Kubernetes")])
    stage_c = StageCResult(requirement_scores=[_score(requirement_id="req_1", score=5, evidence=[])])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    level, _reason = compute_confidence(breakdown, _PASSING_GATE, _TEST_CONFIG)
    assert level == "High"


def test_compute_confidence_no_requirements_is_a_red_flag():
    level, reason = compute_confidence([], _PASSING_GATE, _TEST_CONFIG)
    assert level == "Medium"
    assert "no requirements were evaluated" in reason


# --- tier_missing_skills (direct config rule table, no numeric threshold) ---


def test_tier_missing_skills_required_hard_is_critical():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="Distributed Systems", is_required=True, difficulty_tier="hard"),
    ])
    stage_c = StageCResult(requirement_scores=[_score(requirement_id="req_1", score=0, evidence=[])])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    critical, minor, nice_to_have = tier_missing_skills(breakdown, _TEST_CONFIG)
    assert critical == ["Distributed Systems"]
    assert minor == nice_to_have == []


def test_tier_missing_skills_preferred_easy_is_nice_to_have():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="Rust", is_required=False, difficulty_tier="easy"),
    ])
    stage_c = StageCResult(requirement_scores=[_score(requirement_id="req_1", score=0, evidence=[])])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    _critical, _minor, nice_to_have = tier_missing_skills(breakdown, _TEST_CONFIG)
    assert nice_to_have == ["Rust"]


def test_tier_missing_skills_required_easy_is_minor():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="Docstrings", is_required=True, difficulty_tier="easy"),
    ])
    stage_c = StageCResult(requirement_scores=[_score(requirement_id="req_1", score=0, evidence=[])])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    _critical, minor, _nice = tier_missing_skills(breakdown, _TEST_CONFIG)
    assert minor == ["Docstrings"]


def test_tier_missing_skills_ignores_non_missing_requirements():
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1")])
    stage_c = StageCResult(requirement_scores=[_score(requirement_id="req_1", score=90)])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    critical, minor, nice_to_have = tier_missing_skills(breakdown, _TEST_CONFIG)
    assert critical == minor == nice_to_have == []


# --- compute_recommendation ---


def test_compute_recommendation_strong_hire():
    assert compute_recommendation(85, "High", _PASSING_GATE, _TEST_CONFIG) == "Strong Hire"


def test_compute_recommendation_high_score_low_confidence_downgrades_to_consider():
    assert compute_recommendation(90, "Low", _PASSING_GATE, _TEST_CONFIG) == "Consider"


def test_compute_recommendation_hard_gate_failure_overrides_high_score():
    assert compute_recommendation(95, "High", _FAIL_GATE, _TEST_CONFIG) == "Not Recommended"


def test_compute_recommendation_bands():
    assert compute_recommendation(65, "Medium", _PASSING_GATE, _TEST_CONFIG) == "Consider"
    assert compute_recommendation(45, "Medium", _PASSING_GATE, _TEST_CONFIG) == "Weak Match"
    assert compute_recommendation(20, "Low", _PASSING_GATE, _TEST_CONFIG) == "Not Recommended"


# --- compile_narrative ---


def test_compile_narrative_mentions_hard_gate_failure():
    narrative = compile_narrative(
        recommendation="Not Recommended", confidence="High",
        confidence_reason="all non-missing requirements had direct evidence and no hard-gate ambiguity",
        recruiter_match_score=90.0, hard_gate=_FAIL_GATE,
        critical_missing_skills=[], breakdown=[],
    )
    assert "Disqualifying" in narrative
    assert "PhD required" in narrative


def test_compile_narrative_lists_critical_gaps_and_strengths_and_one_score():
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="FastAPI", is_required=True),
    ])
    stage_c = StageCResult(requirement_scores=[
        _score(requirement_id="req_1", score=90, reasoning="Strong direct match"),
    ])
    breakdown = build_requirement_breakdown(stage_a, stage_c, _TEST_RESUME, _TEST_CONFIG)
    narrative = compile_narrative(
        recommendation="Strong Hire", confidence="High", confidence_reason="dense evidence",
        recruiter_match_score=90.0, hard_gate=_PASSING_GATE,
        critical_missing_skills=["Distributed Systems"], breakdown=breakdown,
    )
    assert "Critical gaps: Distributed Systems" in narrative
    assert "FastAPI" in narrative
    assert "Strong direct match" in narrative
    assert "Recruiter Match Score: 90/100." in narrative
    # No separate "technical fit" / "project quality" numbers anywhere.
    assert "fit" not in narrative.lower()
    assert "project quality" not in narrative.lower()


# --- Full orchestration (aggregate) ---


_AGGREGATE_TEST_RESUME = ParsedResume(
    name="Test Candidate", skills=["Express.js", "FastAPI", "PostgreSQL"],
)


def test_aggregate_end_to_end_reproduces_fastapi_express_bug_report():
    """The literal originally-reported bug: FastAPI evidenced only by Express.js should NOT score near zero."""
    stage_a = StageAResult(role_archetype="backend", requirements=[
        _requirement(id="req_1", text="FastAPI", is_required=True, category="Backend Engineering"),
        _requirement(id="req_2", text="PostgreSQL", is_required=True, category="Databases", difficulty_tier="easy"),
    ])
    stage_c = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=85,
            evidence=[RequirementEvidence(category="skills", snippet="Express.js", approximate_recency="current")],
            reasoning="Express.js is an equivalent backend framework.",
        ),
        RequirementScore(
            requirement_id="req_2", score=100,
            evidence=[RequirementEvidence(category="skills", snippet="PostgreSQL", approximate_recency="current")],
            reasoning="Direct match.",
        ),
    ])
    result = aggregate(stage_a, stage_c, _PASSING_GATE, _AGGREGATE_TEST_RESUME)

    assert result.recruiter_match_score >= 80
    assert result.recommendation in ("Strong Hire", "Consider")
    assert result.critical_missing_skills == []


def test_aggregate_hard_gate_failure_caps_score():
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1")])
    stage_c = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=100,
            evidence=[RequirementEvidence(category="skills", snippet="FastAPI")], reasoning="perfect",
        ),
    ])
    result = aggregate(stage_a, stage_c, _FAIL_GATE, _AGGREGATE_TEST_RESUME)

    assert result.recruiter_match_score <= 30  # ships with the production config's cap; a real cap, not asserting its exact value
    assert result.recommendation == "Not Recommended"


def test_aggregate_real_hard_gate_needs_review_caps_confidence_not_score():
    jd = ParsedJD(role="Engineer", required_skills=["FastAPI"], hard_requirements=[
        HardRequirement(type="visa", description="Must be authorized to work in the US"),
    ])
    resume = ParsedResume(name="Jane", skills=["FastAPI"])
    hard_gate = evaluate_hard_requirements(jd, resume)

    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1")])
    stage_c = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=100,
            evidence=[RequirementEvidence(category="skills", snippet="FastAPI")], reasoning="perfect",
        ),
    ])
    result = aggregate(stage_a, stage_c, hard_gate, resume)

    assert hard_gate.overall_status == "needs_human_review"
    assert result.recruiter_match_score > 30  # not capped -- only FAIL caps the score
    assert result.confidence != "High"  # capped by needs_human_review


def test_aggregate_records_ontology_and_config_version():
    from recruiter_intelligence.scoring_config import load_scoring_config
    from recruiter_intelligence.skill_ontology import load_ontology

    stage_a = StageAResult(role_archetype="backend", requirements=[])
    stage_c = StageCResult(requirement_scores=[])
    result = aggregate(stage_a, stage_c, _PASSING_GATE, _AGGREGATE_TEST_RESUME)
    assert result.ontology_version == load_ontology().version
    assert result.scoring_config_version == load_scoring_config().version


def test_aggregate_result_has_no_separate_technical_fit_or_project_quality_fields():
    # The schema itself enforces this (extra="forbid" plus the fields
    # simply don't exist), but assert it explicitly here since it's the
    # headline behavior change this revision makes.
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1")])
    stage_c = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=90,
            evidence=[RequirementEvidence(category="skills", snippet="FastAPI")], reasoning="ok",
        ),
    ])
    result = aggregate(stage_a, stage_c, _PASSING_GATE, _AGGREGATE_TEST_RESUME)
    dumped = result.model_dump()
    assert "technical_fit_score" not in dumped
    assert "project_quality_score" not in dumped
    assert "project_quality_adjustment" not in dumped


def test_aggregate_records_verified_evidence_count_on_breakdown():
    stage_a = StageAResult(role_archetype="backend", requirements=[_requirement(id="req_1", text="FastAPI")])
    stage_c = StageCResult(requirement_scores=[
        RequirementScore(
            requirement_id="req_1", score=90,
            evidence=[
                RequirementEvidence(category="skills", snippet="FastAPI"),  # verifiable -- in resume.skills
                RequirementEvidence(category="skills", snippet="a fabricated citation not in the resume"),
            ],
            reasoning="ok",
        ),
    ])
    result = aggregate(stage_a, stage_c, _PASSING_GATE, _AGGREGATE_TEST_RESUME)
    assert result.requirement_breakdown[0].verified_evidence_count == 1
