"""
Deterministic scoring for the Recruiter Match Score.

Combines the Requirement Understanding step's requirements, the Hard
Requirement Check's gate result, and the Evidence Evaluation step's
per-requirement scores into ONE number (see the approved "One Recruiter
Match Score" plan, section 3). Two weight factors, one weighted average,
one hard-gate cap — nothing else.

Project quality and recency are NOT computed here. Both are folded into
the Evidence Evaluation step's own per-requirement score (plan section
3.1): a weak vs. production-quality project, or old vs. current evidence,
only mean something in the context of reading that specific evidence,
which is exactly what that step already does. This module never re-derives
or adjusts a requirement's score — it only weighs and averages scores that
are already final. This is a deliberate simplification from an earlier
version of this module, which separately computed a recency-dampening
multiplier and a project-quality rubric/adjustment; neither had benchmark
evidence justifying the extra machinery, so both were removed rather than
kept "just in case."
"""

from __future__ import annotations

import re

from recruiter_intelligence.schema import (
    ConfidenceLevel,
    HardGateResult,
    Recommendation,
    Requirement,
    RequirementBreakdown,
    RequirementEvidence,
    RequirementScore,
    RecruiterMatchResult,
    StageAResult,
    StageCResult,
)
from recruiter_intelligence.scoring_config import ScoringConfig, load_scoring_config
from recruiter_intelligence.skill_ontology import load_ontology
from resume_processing.schema import ParsedResume

# Presentation-only threshold for which requirements the narrative calls out
# as "key strengths" — not a scoring parameter (it doesn't affect
# recruiter_match_score), so it isn't in scoring_config.yaml.
_STRENGTH_SCORE_THRESHOLD = 80

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_for_verification(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text.strip().lower())


def verify_evidence_snippet(evidence: RequirementEvidence, resume: ParsedResume) -> bool:
    """
    Deterministic (no-LLM) check that a cited snippet is an actual substring
    of the resume section it claims to come from, normalized for
    whitespace/case (plan section 5.3) — closes a real hallucination gap: a
    score above the missing band always has *an* evidence entry (schema-
    enforced), but nothing previously checked it was real. A failed
    verification never blocks scoring or raises an error; it only counts
    against the evidence-completeness confidence flag (see compute_confidence)
    -- a false positive here (e.g. reformatted resume whitespace) should cost
    confidence, not correctness.
    """
    section = getattr(resume, evidence.category, None)
    if not section:
        return False
    haystack = _normalize_for_verification(" ".join(section))
    needle = _normalize_for_verification(evidence.snippet)
    return bool(needle) and needle in haystack


def compute_final_weight(
    requirement: Requirement, requirement_score: RequirementScore, config: ScoringConfig,
) -> float:
    """base_weight(required/preferred), difficulty-penalized only if the requirement is genuinely missing."""
    weight = config.required_base_weight if requirement.is_required else config.preferred_base_weight
    if requirement_score.score <= config.missing_score_threshold:
        weight *= config.difficulty_penalty_multiplier[requirement.difficulty_tier]
    return weight


def build_requirement_breakdown(
    stage_a: StageAResult, stage_c: StageCResult, resume: ParsedResume, config: ScoringConfig,
) -> list[RequirementBreakdown]:
    """
    Compose every requirement's final, explainable contribution. Assumes
    stage_c.requirement_scores already has exactly one entry per Stage A
    requirement id (evidence_evaluation.resolve_requirement_scores's job) --
    matched here by id, never by position.
    """
    scores_by_id = {score.requirement_id: score for score in stage_c.requirement_scores}
    breakdown: list[RequirementBreakdown] = []
    for requirement in stage_a.requirements:
        score = scores_by_id.get(requirement.id)
        if score is None:
            continue
        verified_count = sum(1 for e in score.evidence if verify_evidence_snippet(e, resume))
        breakdown.append(RequirementBreakdown(
            requirement_id=requirement.id,
            text=requirement.text,
            is_required=requirement.is_required,
            category=requirement.category,
            difficulty_tier=requirement.difficulty_tier,
            score=score.score,
            final_weight=compute_final_weight(requirement, score, config),
            is_missing=score.score <= config.missing_score_threshold,
            evidence=score.evidence,
            verified_evidence_count=verified_count,
            reasoning=score.reasoning,
        ))
    return breakdown


def attach_contributions(breakdown: list[RequirementBreakdown]) -> list[RequirementBreakdown]:
    """
    Attach each requirement's exact share of the weighted-average score
    (contribution = score * final_weight / total_weight) -- these shares
    sum exactly to compute_weighted_average's result, which is what makes
    every point in the final score traceable to a specific requirement
    (the approved plan's non-negotiable explainability principle, section
    4). A no-op if total weight is zero (nothing to attribute).
    """
    total_weight = sum(item.final_weight for item in breakdown)
    if total_weight <= 0:
        return breakdown
    return [
        item.model_copy(update={"contribution": (item.score * item.final_weight) / total_weight})
        for item in breakdown
    ]


def compute_weighted_average(breakdown: list[RequirementBreakdown]) -> float:
    """Weighted average of each requirement's already-final score. The hard-gate cap is applied by the caller, not here."""
    total_weight = sum(item.final_weight for item in breakdown)
    if total_weight <= 0:
        return 0.0
    weighted_sum = sum(item.score * item.final_weight for item in breakdown)
    return max(0.0, min(100.0, weighted_sum / total_weight))


def compute_confidence(
    breakdown: list[RequirementBreakdown], hard_gate: HardGateResult, config: ScoringConfig,
) -> tuple[ConfidenceLevel, str]:
    """
    Confidence answers "how sure is the system that this score is right,"
    not just "did we find citations" (plan section 3.3) -- a small, named
    set of red flags. Starts at High; each flag raised drops one level.
    """
    flags: list[str] = []

    if not breakdown:
        flags.append("no requirements were evaluated")
    else:
        non_missing = [item for item in breakdown if not item.is_missing]
        if non_missing:
            with_verified_evidence = sum(1 for item in non_missing if item.verified_evidence_count > 0)
            evidence_share = with_verified_evidence / len(non_missing)
            if evidence_share < config.confidence_evidence_completeness_min_share:
                flags.append(
                    f"only {with_verified_evidence}/{len(non_missing)} non-missing requirements "
                    "have verified evidence"
                )

    if hard_gate.overall_status == "needs_human_review":
        flags.append("at least one hard requirement needs human review")

    if len(flags) == 0:
        level: ConfidenceLevel = "High"
    elif len(flags) == 1:
        level = "Medium"
    else:
        level = "Low"

    reason = (
        "; ".join(flags) if flags
        else "all non-missing requirements had direct evidence and no hard-gate ambiguity"
    )
    return level, reason


def tier_missing_skills(
    breakdown: list[RequirementBreakdown], config: ScoringConfig,
) -> tuple[list[str], list[str], list[str]]:
    """
    Tier every missing requirement via the config's direct
    (is_required, difficulty_tier) -> tier rule table (plan section 3.2) --
    no numeric weight-threshold comparison needed, since final_weight for a
    missing requirement only ever takes one of a handful of discrete values.
    """
    critical: list[str] = []
    minor: list[str] = []
    nice_to_have: list[str] = []
    buckets = {"critical": critical, "minor": minor, "nice_to_have": nice_to_have}

    for item in breakdown:
        if not item.is_missing:
            continue
        tier = config.missing_skill_tier(is_required=item.is_required, difficulty_tier=item.difficulty_tier)
        buckets[tier].append(item.text)

    return critical, minor, nice_to_have


def compute_recommendation(
    score: float, confidence: ConfidenceLevel, hard_gate: HardGateResult, config: ScoringConfig,
) -> Recommendation:
    cutoffs = config.recommendation_score_cutoffs
    if hard_gate.overall_status == "fail" or score < cutoffs["weak_match"]:
        return "Not Recommended"
    if score >= cutoffs["strong_hire"]:
        return "Strong Hire" if confidence != "Low" else "Consider"
    if score >= cutoffs["consider"]:
        return "Consider"
    return "Weak Match"


def compile_narrative(
    *,
    recommendation: Recommendation,
    confidence: ConfidenceLevel,
    confidence_reason: str,
    recruiter_match_score: float,
    hard_gate: HardGateResult,
    critical_missing_skills: list[str],
    breakdown: list[RequirementBreakdown],
) -> str:
    """Deterministic narrative -- no LLM call."""
    lines = [f"Recommendation: {recommendation} (confidence: {confidence} — {confidence_reason})"]

    if hard_gate.overall_status == "fail":
        failed = [r for r in hard_gate.results if r.status == "fail"]
        lines.append(
            "Disqualifying hard requirement(s): "
            + "; ".join(f"{r.description or r.type} — {r.reason}" for r in failed)
        )
    elif hard_gate.overall_status == "needs_human_review":
        review = [r for r in hard_gate.results if r.status == "needs_human_review"]
        lines.append("Needs human review: " + "; ".join(r.description or r.type for r in review))

    if critical_missing_skills:
        lines.append("Critical gaps: " + ", ".join(critical_missing_skills) + ".")

    strengths = sorted(
        (item for item in breakdown if item.score >= _STRENGTH_SCORE_THRESHOLD),
        key=lambda item: item.score, reverse=True,
    )[:3]
    if strengths:
        lines.append(
            "Key strengths: "
            + "; ".join(f"{item.text} ({item.score}%) — {item.reasoning}".strip(" —") for item in strengths)
        )

    lines.append(f"Recruiter Match Score: {recruiter_match_score:.0f}/100.")
    return "\n".join(lines)


def aggregate(
    stage_a: StageAResult, stage_c: StageCResult, hard_gate: HardGateResult, resume: ParsedResume,
) -> RecruiterMatchResult:
    """
    Public entry point: combine the job-understanding, hard-gate, and
    evidence steps into one RecruiterMatchResult. ``resume`` is needed only
    to verify evidence snippets (section 5.3) -- scoring itself never reads
    the resume directly; every score was already finalized upstream.
    """
    config = load_scoring_config()
    # Read only for reproducibility metadata (plan's non-negotiable principle)
    # -- not a scoring input. Already cached by load_ontology()'s own
    # lru_cache, so this costs nothing extra.
    ontology_version = load_ontology().version

    breakdown = build_requirement_breakdown(stage_a, stage_c, resume, config)
    breakdown = attach_contributions(breakdown)
    weighted_average = compute_weighted_average(breakdown)

    if hard_gate.overall_status == "fail":
        final_score = min(config.hard_gate_fail_score_cap, weighted_average)
    else:
        final_score = weighted_average

    confidence, confidence_reason = compute_confidence(breakdown, hard_gate, config)
    recommendation = compute_recommendation(final_score, confidence, hard_gate, config)
    critical, minor, nice_to_have = tier_missing_skills(breakdown, config)
    narrative = compile_narrative(
        recommendation=recommendation, confidence=confidence, confidence_reason=confidence_reason,
        recruiter_match_score=final_score, hard_gate=hard_gate,
        critical_missing_skills=critical, breakdown=breakdown,
    )

    return RecruiterMatchResult(
        recruiter_match_score=round(final_score),
        confidence=confidence,
        confidence_reason=confidence_reason,
        recommendation=recommendation,
        hard_gate=hard_gate,
        role_archetype=stage_a.role_archetype,
        critical_missing_skills=critical,
        minor_missing_skills=minor,
        nice_to_have_missing_skills=nice_to_have,
        requirement_breakdown=breakdown,
        narrative=narrative,
        ontology_version=ontology_version,
        scoring_config_version=config.version,
    )
