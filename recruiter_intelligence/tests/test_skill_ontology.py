"""Tests for recruiter_intelligence.skill_ontology — no network calls."""

from __future__ import annotations

from recruiter_intelligence.skill_ontology import (
    SkillOntology,
    load_ontology,
    normalize_skill_name,
)

# A small, self-contained ontology for testing SkillOntology's logic in
# isolation, independent of the real (larger, evolving) shipped data file.
_SYNTHETIC_RAW = {
    "version": "test",
    "synonyms": {"py": "python", "js": "javascript"},
    "categories": {
        "backend_frameworks": {
            "label": "Backend Frameworks",
            "base_difficulty": "medium",
            "decay_rate": "moderate",
            "members": ["fastapi", "express"],
        },
        "containerization": {
            "label": "Containerization",
            "base_difficulty": "easy",
            "decay_rate": "slow",
            "members": ["docker"],
        },
        "container_orchestration": {
            "label": "Container Orchestration",
            "base_difficulty": "hard",
            "decay_rate": "moderate",
            "members": ["kubernetes"],
        },
    },
    "transferable_edges": [
        {"from": "containerization", "to": "container_orchestration", "strength": "strong"},
    ],
}


def _ontology() -> SkillOntology:
    return SkillOntology(_SYNTHETIC_RAW)


def test_normalize_skill_name_lowercases_and_collapses_whitespace():
    assert normalize_skill_name("  Python   3  ") == "python"


def test_normalize_skill_name_strips_trailing_version():
    assert normalize_skill_name("Node.js 18") == "node.js"


def test_resolve_synonym():
    ontology = _ontology()
    assert ontology.resolve("PY") == "python"
    assert ontology.resolve("Python") == "python"


def test_relationship_exact_match():
    ontology = _ontology()
    assert ontology.relationship("Python", "py") == "exact"


def test_relationship_same_category():
    ontology = _ontology()
    assert ontology.relationship("FastAPI", "Express") == "same_category"


def test_relationship_transferable_strong():
    ontology = _ontology()
    assert ontology.relationship("Kubernetes", "Docker") == "transferable_strong"


def test_relationship_none_for_unrelated_skills():
    ontology = _ontology()
    assert ontology.relationship("FastAPI", "Kubernetes") == "none"


def test_relationship_none_for_skill_not_in_ontology():
    ontology = _ontology()
    assert ontology.relationship("FastAPI", "Some Totally Novel Framework") == "none"


def test_base_difficulty_and_decay_rate_for_known_skill():
    ontology = _ontology()
    assert ontology.base_difficulty("fastapi") == "medium"
    assert ontology.decay_rate("kubernetes") == "moderate"


def test_base_difficulty_returns_none_for_unknown_skill():
    ontology = _ontology()
    assert ontology.base_difficulty("some obscure niche tool") is None


def test_find_evidence_candidates_ranks_exact_before_transferable():
    ontology = _ontology()
    candidates = ontology.find_evidence_candidates(
        "Docker", ["Kubernetes", "Docker", "Unrelated Thing"],
    )
    assert [c.resume_skill for c in candidates] == ["Docker", "Kubernetes"]
    assert candidates[0].relationship == "exact"
    assert candidates[1].relationship == "transferable_strong"


def test_find_evidence_candidates_skips_non_string_and_empty_entries():
    ontology = _ontology()
    candidates = ontology.find_evidence_candidates(
        "Docker", ["Docker", 123, None, "", "   "],  # type: ignore[list-item]
    )
    assert len(candidates) == 1
    assert candidates[0].resume_skill == "Docker"


def test_find_evidence_candidates_empty_when_nothing_relates():
    ontology = _ontology()
    assert ontology.find_evidence_candidates("FastAPI", ["Kubernetes"]) == []


def test_coverage_fraction():
    ontology = _ontology()
    assert ontology.coverage(["FastAPI", "Docker", "Something Unlisted"]) == 2 / 3


def test_coverage_empty_list_returns_zero():
    ontology = _ontology()
    assert ontology.coverage([]) == 0.0


# --- Smoke tests against the real, shipped skill_ontology.yaml ---


def test_load_ontology_loads_the_real_shipped_file():
    ontology = load_ontology()
    assert ontology.version


def test_load_ontology_is_cached():
    assert load_ontology() is load_ontology()


def test_real_ontology_fastapi_and_express_are_same_category():
    # The exact example from the original bug report this whole redesign
    # is built to fix: FastAPI (JD) vs. Express.js (resume) should land in
    # the same-category (equivalent-technology) band, not "none."
    ontology = load_ontology()
    assert ontology.relationship("FastAPI", "Express.js") == "same_category"


def test_real_ontology_docker_and_kubernetes_are_transferable():
    ontology = load_ontology()
    relationship = ontology.relationship("Docker", "Kubernetes")
    assert relationship in ("transferable_strong", "transferable_weak")


def test_real_ontology_resolves_seeded_synonym():
    # Seeded verbatim from matching_engine.SKILL_ALIASES.
    ontology = load_ontology()
    assert ontology.resolve("py") == "python"
    assert ontology.resolve("k8s") == "kubernetes"
