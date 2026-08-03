"""
Skill Knowledge Graph / Ontology — deterministic skill-relationship lookups.

Consulted between Stage B and Stage C of the Recruiter Intelligence Engine
pipeline (see the approved plan, section "3a.1 Skill Knowledge Graph / Skill
Ontology") so the LLM in Stage C receives a pre-computed evidence shortlist
instead of re-deriving conceptual relationships between technologies from
scratch on every call — this is the single biggest lever for consistency
identified in that plan.

Data lives in data/skill_ontology.yaml — a versioned, human-reviewed file.
This module only reads it; nothing here writes back to it at inference time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

_ONTOLOGY_PATH = Path(__file__).parent / "data" / "skill_ontology.yaml"

DifficultyTier = Literal["easy", "medium", "hard", "specialized"]
DecayRate = Literal["fast", "moderate", "slow"]
RelationshipType = Literal[
    "exact", "same_category", "transferable_strong", "transferable_weak", "none",
]

_RELATIONSHIP_RANK: dict[RelationshipType, int] = {
    "exact": 0, "same_category": 1, "transferable_strong": 2,
    "transferable_weak": 3, "none": 4,
}

_VERSION_SUFFIX_RE = re.compile(r"\s+v?\d+(\.\w+)*$")


def normalize_skill_name(raw: str) -> str:
    """
    Normalize a skill string the same way matching_engine._normalize does
    (lowercase, collapse whitespace, strip a trailing version number) so a
    given skill string normalizes identically whichever module sees it
    first. Deliberately reimplemented, not imported, from matching_engine —
    this module must not reach into that package's internals; the two stay
    independent per the additive architecture the whole redesign is built on.
    """
    normalized = raw.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = _VERSION_SUFFIX_RE.sub("", normalized)
    return normalized


@dataclass(frozen=True)
class CategoryInfo:
    key: str
    label: str
    base_difficulty: DifficultyTier
    decay_rate: DecayRate
    members: frozenset[str]


@dataclass(frozen=True)
class EvidenceCandidate:
    """One resume skill offered as candidate evidence for a JD requirement."""

    resume_skill: str
    relationship: RelationshipType
    category_label: str | None


class SkillOntology:
    """Loaded, indexed view of skill_ontology.yaml. Construct via load_ontology()."""

    def __init__(self, raw: dict):
        self.version: str = raw.get("version", "unknown")

        self._synonyms: dict[str, str] = {
            normalize_skill_name(str(k)): normalize_skill_name(str(v))
            for k, v in (raw.get("synonyms") or {}).items()
        }

        self._categories: dict[str, CategoryInfo] = {}
        self._member_to_category: dict[str, str] = {}
        for key, cat in (raw.get("categories") or {}).items():
            members = frozenset(
                normalize_skill_name(str(m)) for m in cat.get("members", [])
            )
            self._categories[key] = CategoryInfo(
                key=key,
                label=cat.get("label", key),
                base_difficulty=cat.get("base_difficulty", "medium"),
                decay_rate=cat.get("decay_rate", "moderate"),
                members=members,
            )
            for member in members:
                self._member_to_category[member] = key

        self._transferable: dict[str, list[tuple[str, str]]] = {}
        for edge in raw.get("transferable_edges") or []:
            a, b, strength = edge["from"], edge["to"], edge["strength"]
            self._transferable.setdefault(a, []).append((b, strength))
            self._transferable.setdefault(b, []).append((a, strength))

    def resolve(self, skill: str) -> str:
        """Normalize a skill string and resolve it to its canonical synonym."""
        normalized = normalize_skill_name(skill)
        return self._synonyms.get(normalized, normalized)

    def category_for(self, skill: str) -> CategoryInfo | None:
        """The ontology category a skill belongs to, or None if unlisted."""
        resolved = self.resolve(skill)
        category_key = self._member_to_category.get(resolved)
        return self._categories.get(category_key) if category_key else None

    def base_difficulty(self, skill: str) -> DifficultyTier | None:
        category = self.category_for(skill)
        return category.base_difficulty if category else None

    def decay_rate(self, skill: str) -> DecayRate | None:
        category = self.category_for(skill)
        return category.decay_rate if category else None

    def relationship(self, skill_a: str, skill_b: str) -> RelationshipType:
        """Deterministic relationship type between two skill strings."""
        a = self.resolve(skill_a)
        b = self.resolve(skill_b)
        if a == b:
            return "exact"

        category_a = self._member_to_category.get(a)
        category_b = self._member_to_category.get(b)
        if category_a and category_a == category_b:
            return "same_category"

        if category_a and category_b:
            for other_category, strength in self._transferable.get(category_a, []):
                if other_category == category_b:
                    return "transferable_strong" if strength == "strong" else "transferable_weak"

        return "none"

    def find_evidence_candidates(
        self, requirement_skill: str, candidate_skills: list[str],
    ) -> list[EvidenceCandidate]:
        """
        For a JD requirement, scan a candidate's resume skills and return
        every one with SOME ontology relationship to it, strongest first.

        An empty result means the ontology has nothing to offer for this
        requirement — Stage C falls back to today's freeform reasoning,
        graceful degradation rather than a hard dependency.
        """
        candidates: list[EvidenceCandidate] = []
        for candidate_skill in candidate_skills:
            if not isinstance(candidate_skill, str) or not candidate_skill.strip():
                continue
            relationship = self.relationship(requirement_skill, candidate_skill)
            if relationship == "none":
                continue
            category = self.category_for(candidate_skill)
            candidates.append(EvidenceCandidate(
                resume_skill=candidate_skill,
                relationship=relationship,
                category_label=category.label if category else None,
            ))
        candidates.sort(key=lambda c: _RELATIONSHIP_RANK[c.relationship])
        return candidates

    def coverage(self, requirement_skills: list[str]) -> float:
        """
        Fraction of requirement_skills that resolve to a known ontology
        category — the "ontology coverage rate" validation metric from the
        approved plan. Returns 0.0 for an empty input.
        """
        if not requirement_skills:
            return 0.0
        hits = sum(1 for skill in requirement_skills if self.category_for(skill) is not None)
        return hits / len(requirement_skills)


@lru_cache(maxsize=1)
def load_ontology() -> SkillOntology:
    """Load and cache the shipped skill_ontology.yaml for this process's lifetime."""
    raw = yaml.safe_load(_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    return SkillOntology(raw)
