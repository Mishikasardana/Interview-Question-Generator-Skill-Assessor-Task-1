"""
Recruiter Intelligence Engine — public package interface.

Builds alongside (not instead of) matching_engine and semantic_matching,
per the approved architecture plan. External consumers should only import
from here as the package grows through the roadmap's later phases:

    from recruiter_intelligence import load_ontology, SkillOntology

Everything else is an internal implementation detail.
"""

from __future__ import annotations

from recruiter_intelligence.aggregation import aggregate
from recruiter_intelligence.evidence_evaluation import evaluate_evidence
from recruiter_intelligence.exceptions import (
    EvidenceEvaluationValidationError,
    GLMEvidenceEvaluationError,
    GLMRequirementExtractionError,
    PromptBuildError,
    RecruiterIntelligenceError,
    RequirementExtractionValidationError,
)
from recruiter_intelligence.hard_requirement_gate import evaluate_hard_requirements
from recruiter_intelligence.requirement_extraction import extract_requirements
from recruiter_intelligence.schema import (
    HardGateResult,
    HardRequirementResult,
    RecruiterMatchResult,
    Requirement,
    RequirementBreakdown,
    RequirementScore,
    StageAResult,
    StageCResult,
)
from recruiter_intelligence.scoring_config import ScoringConfig, load_scoring_config
from recruiter_intelligence.skill_ontology import (
    CategoryInfo,
    EvidenceCandidate,
    SkillOntology,
    load_ontology,
    normalize_skill_name,
)

__all__ = [
    "load_ontology",
    "SkillOntology",
    "CategoryInfo",
    "EvidenceCandidate",
    "normalize_skill_name",
    "extract_requirements",
    "StageAResult",
    "Requirement",
    "evaluate_hard_requirements",
    "HardGateResult",
    "HardRequirementResult",
    "evaluate_evidence",
    "StageCResult",
    "RequirementScore",
    "aggregate",
    "RecruiterMatchResult",
    "RequirementBreakdown",
    "ScoringConfig",
    "load_scoring_config",
    "RecruiterIntelligenceError",
    "PromptBuildError",
    "GLMRequirementExtractionError",
    "RequirementExtractionValidationError",
    "GLMEvidenceEvaluationError",
    "EvidenceEvaluationValidationError",
]
