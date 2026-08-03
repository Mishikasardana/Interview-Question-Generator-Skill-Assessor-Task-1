"""
Deterministic scoring configuration loader.

Externalizes every weight, penalty, and cutoff the Recruiter Match Score
calculation uses (see the approved "One Recruiter Match Score" plan,
section 6) so none of it is hardcoded in aggregation.py. Loaded once and
cached, mirroring skill_ontology.py's load_ontology() pattern exactly —
one more small, versioned YAML file with the same governance, not new
machinery.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

_CONFIG_PATH = Path(__file__).parent / "config" / "scoring_config.yaml"

MissingSkillTier = Literal["critical", "minor", "nice_to_have"]


@dataclass(frozen=True)
class ScoringConfig:
    """Loaded, typed view of scoring_config.yaml. Construct via load_scoring_config()."""

    version: str
    calibrated: bool
    required_base_weight: float
    preferred_base_weight: float
    missing_score_threshold: int
    difficulty_penalty_multiplier: dict[str, float]
    hard_gate_fail_score_cap: int
    missing_skill_tier_rules: dict[str, dict[str, MissingSkillTier]]
    confidence_evidence_completeness_min_share: float
    recommendation_score_cutoffs: dict[str, int]

    def missing_skill_tier(self, *, is_required: bool, difficulty_tier: str) -> MissingSkillTier:
        key = "required" if is_required else "preferred"
        return self.missing_skill_tier_rules[key][difficulty_tier]


@lru_cache(maxsize=1)
def load_scoring_config() -> ScoringConfig:
    """Load and cache the shipped scoring_config.yaml for this process's lifetime."""
    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    return ScoringConfig(
        version=raw.get("version", "unknown"),
        calibrated=raw.get("calibrated", False),
        required_base_weight=raw["required_base_weight"],
        preferred_base_weight=raw["preferred_base_weight"],
        missing_score_threshold=raw["missing_score_threshold"],
        difficulty_penalty_multiplier=raw["difficulty_penalty_multiplier"],
        hard_gate_fail_score_cap=raw["hard_gate_fail_score_cap"],
        missing_skill_tier_rules=raw["missing_skill_tier_rules"],
        confidence_evidence_completeness_min_share=(
            raw["confidence_flag_thresholds"]["evidence_completeness_min_share"]
        ),
        recommendation_score_cutoffs=raw["recommendation_score_cutoffs"],
    )
