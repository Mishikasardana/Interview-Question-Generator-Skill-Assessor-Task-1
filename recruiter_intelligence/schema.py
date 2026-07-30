"""
Pydantic schemas for the Recruiter Intelligence Engine's Stage A (JD
requirement extraction) and Stage B (deterministic hard-requirement gate).

See the approved plan (.claude/plans/ — "Recruiter Intelligence Engine") for
the full architecture. Stage A is an LLM call; Stage B is pure Python.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jd_parsing.schema import HardRequirementType

RoleArchetype = Literal[
    "backend", "frontend", "fullstack", "data_science", "ml_engineer",
    "prompt_engineer_genai", "devops_infra", "mobile", "qa", "other",
]

# A fixed, small set — not freeform text — so Stage D's role-archetype
# weighting profiles (a category -> multiplier table) can reliably key off
# these values. This directly targets a measured, real problem: the earlier
# semantic_matching benchmark found 13 different category-name variants
# across 10 runs of the same JD when category naming was left freeform.
CategoryLabel = Literal[
    "Backend Engineering", "Frontend Engineering", "Databases",
    "Cloud & Infrastructure", "DevOps & CI/CD", "LLM & AI/ML",
    "Data Science & Analytics", "Mobile Engineering", "Testing & QA",
    "Security & Compliance", "Soft Skills & Leadership", "Other",
]

DifficultyTier = Literal["easy", "medium", "hard", "specialized"]

HardGateStatus = Literal["pass", "fail", "needs_human_review"]


class RequirementJudgment(BaseModel):
    """
    One requirement's raw LLM-produced judgment.

    ``skill`` is matched back against the original JD's required_skills/
    preferred_skills lists by the orchestrator via text match, not
    positional index — a dropped or reordered item is detected and
    defaulted rather than silently misaligning everything after it.

    No ``weight_hint`` field — the only per-requirement importance signal
    used downstream is required-vs-preferred (already reliably classified
    by jd_parsing). A prior revision scaled weight by an additional
    LLM-assigned 0-1 "importance" number; it was removed because it had no
    benchmark evidence justifying it over the plain required/preferred
    split, and a continuous LLM-assigned number is harder to keep
    consistent across repeated runs than a fixed categorical choice (see
    the approved "One Recruiter Match Score" plan, section 3.1).
    """

    model_config = ConfigDict(extra="forbid")

    skill: str
    category: CategoryLabel = "Other"
    difficulty_tier: DifficultyTier = "medium"
    why_it_matters: str = ""


class StageALLMResponse(BaseModel):
    """Raw schema the GLM call must return — validated before orchestration."""

    model_config = ConfigDict(extra="forbid")

    role_archetype: RoleArchetype = "other"
    requirement_judgments: list[RequirementJudgment] = Field(default_factory=list)


class Requirement(BaseModel):
    """
    One fully-resolved JD requirement.

    ``is_required`` comes from which of ParsedJD's own lists the skill was
    already classified into by jd_parsing (Phase 1) — Stage A never
    re-guesses this. ``id`` is assigned by the orchestrator (stable,
    sequential), never by the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    is_required: bool
    category: CategoryLabel
    difficulty_tier: DifficultyTier
    why_it_matters: str
    ontology_base_difficulty: DifficultyTier | None = None


class StageAResult(BaseModel):
    """Public result of Stage A — consumed by the ontology lookup, Stage C, Stage D."""

    model_config = ConfigDict(extra="forbid")

    role_archetype: RoleArchetype
    requirements: list[Requirement] = Field(default_factory=list)


class HardRequirementResult(BaseModel):
    """Stage B's per-hard-requirement verdict."""

    model_config = ConfigDict(extra="forbid")

    type: HardRequirementType
    description: str
    status: HardGateStatus
    reason: str


class HardGateResult(BaseModel):
    """Stage B's overall verdict — feeds Stage D's score cap / confidence cap."""

    model_config = ConfigDict(extra="forbid")

    overall_status: HardGateStatus
    results: list[HardRequirementResult] = Field(default_factory=list)


# ── Stage C: per-requirement evidence evaluation ────────────────────────────

EvidenceCategory = Literal["skills", "projects", "experience", "education", "certifications"]
RecencyBucket = Literal["current", "recent", "aged", "old", "undated"]

_Score = Annotated[int, Field(ge=0, le=100)]


class RequirementEvidence(BaseModel):
    """One citation backing a requirement score — always a verbatim resume snippet."""

    model_config = ConfigDict(extra="forbid")

    category: EvidenceCategory
    snippet: str
    approximate_recency: RecencyBucket = "undated"


class RequirementScore(BaseModel):
    """
    Stage C's per-requirement judgment. ``requirement_id`` must match a
    Stage A ``Requirement.id`` — matched by the orchestrator, not trusted
    positionally.

    A score above the 0-20% "missing" band with no evidence is structurally
    invalid — this enforces "no unsupported assumptions" at the schema
    level, not just as a prompt instruction the model can ignore.
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    score: _Score
    evidence: list[RequirementEvidence] = Field(default_factory=list)
    reasoning: str = ""

    @model_validator(mode="after")
    def _require_evidence_above_missing_band(self) -> "RequirementScore":
        if self.score > 20 and not self.evidence:
            raise ValueError(
                f"score {self.score} is above the 0-20% 'missing' band and "
                "requires at least one evidence citation"
            )
        return self


class StageCResult(BaseModel):
    """
    Raw schema the GLM call must return for the Evidence Evaluation step --
    validated before scoring.

    No separate project-quality signal list. A prior revision asked the
    model to also emit structured, evidence-gated project-quality facts per
    project/experience entry, which the backend converted into a second
    "project quality score" and an additive adjustment. Both were removed:
    project and recency quality now shape the *requirement_scores* below
    directly (the Evidence Evaluation prompt asks for this explicitly) --
    a weak vs. production-quality project, or old vs. current evidence,
    only mean something in the context of the specific evidence being read,
    which is exactly what this step already does (see the approved "One
    Recruiter Match Score" plan, section 3.1).
    """

    model_config = ConfigDict(extra="forbid")

    requirement_scores: list[RequirementScore] = Field(default_factory=list)


# ── Stage D/E: deterministic aggregation, confidence, tiering, narrative ────

ConfidenceLevel = Literal["High", "Medium", "Low"]
Recommendation = Literal["Strong Hire", "Consider", "Weak Match", "Not Recommended"]
MissingSkillTier = Literal["critical", "minor", "nice_to_have"]


class RequirementBreakdown(BaseModel):
    """
    One requirement's fully-resolved contribution to the final score —
    everything needed to explain *why* the score is what it is (the
    non-negotiable explainability/reproducibility principle in the
    approved plan), without recomputing anything from raw Stage A/C output.

    There is deliberately only one score field here, not a "raw" vs.
    "effective" pair — project quality and recency are folded into the
    Evidence Evaluation step's own judgment (plan section 3.1), so the
    score Stage C assigns is already final; nothing downstream adjusts it.

    ``contribution`` is this requirement's exact share of the weighted-
    average score, BEFORE any hard-gate cap (score * final_weight /
    total_weight) — every requirement's contribution sums exactly to that
    weighted average, which is what makes every point in the final score
    traceable to a specific requirement (plan section 4).
    """

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    text: str
    is_required: bool
    category: CategoryLabel
    difficulty_tier: DifficultyTier
    score: _Score
    final_weight: float
    contribution: float = 0.0
    is_missing: bool
    evidence: list[RequirementEvidence] = Field(default_factory=list)
    verified_evidence_count: int = 0
    reasoning: str = ""


class RecruiterMatchResult(BaseModel):
    """
    The single, unified, primary recruiter-facing output. Exactly one score
    — ``recruiter_match_score`` — computed by deterministic Python from
    Stage C's evidence; the LLM never sees or sets it directly. No separate
    "technical fit" or "project quality" score exists alongside it (see the
    approved plan's non-negotiable principle: one score, fully traceable).
    """

    model_config = ConfigDict(extra="forbid")

    recruiter_match_score: _Score
    confidence: ConfidenceLevel
    confidence_reason: str
    recommendation: Recommendation
    hard_gate: HardGateResult
    role_archetype: RoleArchetype
    critical_missing_skills: list[str] = Field(default_factory=list)
    minor_missing_skills: list[str] = Field(default_factory=list)
    nice_to_have_missing_skills: list[str] = Field(default_factory=list)
    requirement_breakdown: list[RequirementBreakdown] = Field(default_factory=list)
    narrative: str = ""
    ontology_version: str = "unknown"
    scoring_config_version: str = "unknown"
