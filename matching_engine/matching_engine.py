"""
matching_engine/matching_engine.py
Interview Intelligence Platform — Skill Matching Engine

Responsibilities:
  - Normalize skill names (lowercase, alias resolution, version stripping)
  - Match candidate skills against required and preferred JD skills
  - Scan project/experience text for implicitly demonstrated skills
  - Compute a weighted match score (40% required, 20% projects, 20% experience, 10% education, 10% preferred)
  - Produce a structured skill gap list for the Question Generator

Design notes:
    This module is pure and has no external API calls, so unlike
    ``resume_processing``, ``question_generation``, ``jd_parsing``, and
    ``answer_evaluation`` it needs no ``config.py`` or GLM credentials. It
    does, however, validate its inputs defensively (see
    ``MatchingEngineError`` below) since ``resume_json``/``jd_json`` may
    originate directly from an untrusted API request body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from matching_engine.exceptions import MatchingEngineError


# ---------------------------------------------------------------------------
# Alias table — maps abbreviations / alternate spellings to a canonical form.
# Add entries here as new domains are encountered.
# ---------------------------------------------------------------------------
SKILL_ALIASES: dict[str, str] = {
    # Languages
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "c#": "csharp",
    "c++": "cpp",
    # Frontend
    "react.js": "react",
    "reactjs": "react",
    "next.js": "nextjs",
    "vue.js": "vue",
    "vuejs": "vue",
    "express.js": "express",
    "expressjs": "express",
    "node.js": "node",
    "nodejs": "node",
    # AI / ML
    "ml": "machine learning",
    "dl": "deep learning",
    "cv": "computer vision",
    "nlp": "natural language processing",
    "llm": "large language models",
    "llms": "large language models",
    "genai": "generative ai",
    "gen ai": "generative ai",
    "rag": "retrieval augmented generation",
    "hf": "huggingface",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "tf": "tensorflow",
    "keras": "tensorflow",          # commonly co-occurring
    # Databases
    "pg": "postgresql",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "mongo db": "mongodb",
    # Cloud
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "azure": "microsoft azure",
    # APIs / architecture
    "rest": "rest api",
    "restapi": "rest api",
    "rest apis": "rest api",
    "graphql api": "graphql",
    # DevOps
    "k8s": "kubernetes",
    "ci/cd": "cicd",
    "ci cd": "cicd",
    # Misc
    "oop": "object oriented programming",
    "dsa": "data structures and algorithms",
    "os": "operating systems",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SkillGapEntry:
    """One missing skill, annotated for the Question Generator."""
    skill: str          # original casing from the JD
    skill_type: str     # "required" | "preferred"
    priority: str       # "high" | "medium"

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "type": self.skill_type,
            "priority": self.priority,
        }


@dataclass
class MatchResult:
    """
    Full output of the Matching Engine.
    All downstream modules (Question Generator, UI) consume this object.
    """
    score: float                            # 0–100 weighted match score
    required_coverage: float               # % of required skills matched
    preferred_coverage: float              # % of preferred skills matched

    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]

    inferred_skills: list[str] = field(default_factory=list)
    # ↑ skills not in candidate's explicit list but found in project/experience text

    skill_gap: list[SkillGapEntry] = field(default_factory=list)
    # ↑ ordered list: required gaps first (high priority), then preferred (medium)

    def to_dict(self) -> dict:
        """Serialisable form — store directly in match_result_json column."""
        return {
            "score": round(self.score, 2),
            "required_coverage": round(self.required_coverage, 2),
            "preferred_coverage": round(self.preferred_coverage, 2),
            "matched_required": self.matched_required,
            "missing_required": self.missing_required,
            "matched_preferred": self.matched_preferred,
            "missing_preferred": self.missing_preferred,
            "inferred_skills": self.inferred_skills,
            "skill_gap": [g.to_dict() for g in self.skill_gap],
        }

    def summary(self) -> str:
        """Human-readable one-liner for logging / debug."""
        return (
            f"Score: {self.score:.1f}/100 | "
            f"Required: {len(self.matched_required)}/{len(self.matched_required) + len(self.missing_required)} | "
            f"Preferred: {len(self.matched_preferred)}/{len(self.matched_preferred) + len(self.missing_preferred)} | "
            f"Inferred: {len(self.inferred_skills)} | "
            f"Gaps: {len(self.skill_gap)}"
        )


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalize(skill: str) -> str:
    """
    Canonical form of a skill token:
      1. Strip surrounding whitespace
      2. Lowercase
      3. Collapse internal whitespace runs to a single space
      4. Strip trailing version numbers  ("Python 3.11" → "python")
      5. Resolve known aliases
    """
    s = skill.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # Remove trailing standalone version tokens: "python 3", "node 18.x", "es2022", etc.
    # Matches: optional v + digits + optional (dot + word chars) segments
    s = re.sub(r"\s+v?\d+(\.\w+)*$", "", s)
    return SKILL_ALIASES.get(s, s)


def _normalize_set(skills: list[str]) -> dict[str, str]:
    """
    Returns {normalized_form: original_form}.
    Deduplicates by normalized form; first occurrence wins.
    Skips empty / whitespace-only entries.
    """
    result: dict[str, str] = {}
    for s in skills:
        if not s or not s.strip():
            continue
        norm = _normalize(s)
        if norm and norm not in result:
            result[norm] = s
    return result


def _extract_skill_list(payload: dict, field_name: str) -> list[str]:
    """Return a validated list of skill strings from an untrusted payload."""
    skills = payload.get(field_name, [])
    if not isinstance(skills, list):
        raise MatchingEngineError(
            f"Expected list for {field_name}, got {type(skills).__name__}."
        )
    if not all(isinstance(skill, str) for skill in skills):
        raise MatchingEngineError(f"Expected all {field_name} entries to be strings.")
    return skills


def _append_text_value(chunks: list[str], value: object) -> None:
    """Append strings from a scalar or list value, ignoring non-text values."""
    if isinstance(value, list):
        chunks.extend(item for item in value if isinstance(item, str))
    elif isinstance(value, str):
        chunks.append(value)


# ---------------------------------------------------------------------------
# Free-text scanner (Step 4 — projects & experience)
# ---------------------------------------------------------------------------

def _project_text(resume_json: dict) -> str:
    chunks: list[str] = []
    for project in resume_json.get("projects", []):
        if isinstance(project, dict):
            for key in ("name", "description", "technologies", "tech_stack", "tools"):
                _append_text_value(chunks, project.get(key, ""))
        elif isinstance(project, str):
            chunks.append(project)
    return " ".join(chunks).lower()


def _experience_text(resume_json: dict) -> str:
    chunks: list[str] = []
    for exp in resume_json.get("experience", []):
        if isinstance(exp, dict):
            for key in ("role", "title", "description", "technologies", "tools"):
                _append_text_value(chunks, exp.get(key, ""))
            for bullet in exp.get("responsibilities", []):
                if isinstance(bullet, str):
                    chunks.append(bullet)
        elif isinstance(exp, str):
            chunks.append(exp)
    return " ".join(chunks).lower()


def _education_score(resume_json: dict, jd_json: dict) -> float:
    """
    Returns 0.0–1.0. Compares candidate degree level against JD requirement.
    If JD has no education requirement, full score is awarded.
    """
    degree_levels = {
        "phd": 4, "doctorate": 4,
        "master": 3, "msc": 3, "mtech": 3, "me": 3, "mba": 3,
        "bachelor": 2, "btech": 2, "be": 2, "bsc": 2, "bca": 2,
        "diploma": 1, "associate": 1,
    }
    jd_text = (str(jd_json.get("education_requirement", "")) + " " +
               str(jd_json.get("experience_level", ""))).lower()
    required_level = max(
        (lvl for kw, lvl in degree_levels.items() if _skill_in_text(jd_text, kw)),
        default=0,
    )
    if required_level == 0:
        return 1.0   # no education requirement in JD → full score

    edu_text = " ".join(
        str(e.get("degree", "") if isinstance(e, dict) else e)
        for e in resume_json.get("education", [])
    ).lower()
    candidate_level = max(
        (lvl for kw, lvl in degree_levels.items() if _skill_in_text(edu_text, kw)),
        default=0,
    )
    if candidate_level >= required_level:
        return 1.0
    if candidate_level == required_level - 1:
        return 0.5
    return 0.0


def _build_free_text(resume_json: dict) -> str:
    """
    Concatenate all descriptive text from projects and experience sections.
    Handles both dict-style (structured) and plain-string resume entries.
    """
    chunks: list[str] = []

    for project in resume_json.get("projects", []):
        if isinstance(project, dict):
            for key in ("name", "description", "technologies", "tech_stack", "tools"):
                _append_text_value(chunks, project.get(key, ""))
        elif isinstance(project, str):
            chunks.append(project)

    for exp in resume_json.get("experience", []):
        if isinstance(exp, dict):
            for key in ("role", "title", "description", "technologies", "tools"):
                _append_text_value(chunks, exp.get(key, ""))
            for bullet in exp.get("responsibilities", []):
                if isinstance(bullet, str):
                    chunks.append(bullet)
        elif isinstance(exp, str):
            chunks.append(exp)

    return " ".join(chunks).lower()


def _skill_in_text(text: str, norm_skill: str) -> bool:
    """
    Word-boundary search so "java" doesn't match inside "javascript",
    and "c" doesn't match every word containing 'c'.
    """
    pattern = r"\b" + re.escape(norm_skill) + r"\b"
    return bool(re.search(pattern, text))


# ---------------------------------------------------------------------------
# Core matching logic
# ---------------------------------------------------------------------------

def run_matching(resume_json: dict, jd_json: dict) -> MatchResult:
    """
    Compare a parsed resume against a parsed job description.

    Args:
        resume_json : Output of resume_parser — must contain 'skills' (list[str]).
                      May also contain 'projects' and 'experience' for deep scan.
        jd_json     : Output of jd_parser — must contain 'required_skills' and
                      'preferred_skills' (both list[str]).

    Returns:
        MatchResult with score, gap list, and all matched/missing breakdowns.

    Raises:
        MatchingEngineError: If ``resume_json`` or ``jd_json`` is not a dict.
    """
    if not isinstance(resume_json, dict):
        raise MatchingEngineError(
            f"Expected dict for resume_json, got {type(resume_json).__name__}."
        )
    if not isinstance(jd_json, dict):
        raise MatchingEngineError(
            f"Expected dict for jd_json, got {type(jd_json).__name__}."
        )

    # ── Step 1: Normalise all three skill lists ───────────────────────────
    candidate_raw = _extract_skill_list(resume_json, "skills")
    required_raw = _extract_skill_list(jd_json, "required_skills")
    preferred_raw = _extract_skill_list(jd_json, "preferred_skills")

    candidate_norm: dict[str, str] = _normalize_set(candidate_raw)   # {norm: orig}
    required_norm:  dict[str, str] = _normalize_set(required_raw)
    preferred_norm: dict[str, str] = _normalize_set(preferred_raw)

    # ── Step 4: Scan project/experience text for implicit skill evidence ──
    free_text = _build_free_text(resume_json)
    inferred: list[str] = []

    all_jd_skills = {**required_norm, **preferred_norm}
    for norm_skill, orig_skill in all_jd_skills.items():
        if norm_skill not in candidate_norm and _skill_in_text(free_text, norm_skill):
            candidate_norm[norm_skill] = orig_skill  # treat as matched
            inferred.append(orig_skill)

    # ── Step 2: Match against required skills ─────────────────────────────
    matched_required:  list[str] = []
    missing_required:  list[str] = []

    for norm, orig in required_norm.items():
        if norm in candidate_norm:
            matched_required.append(orig)
        else:
            missing_required.append(orig)

    # ── Step 3: Match against preferred skills ────────────────────────────
    matched_preferred: list[str] = []
    missing_preferred: list[str] = []

    for norm, orig in preferred_norm.items():
        if norm in candidate_norm:
            matched_preferred.append(orig)
        else:
            missing_preferred.append(orig)

    # ── Step 5: Coverage ratios and final score ───────────────────────────
    n_required  = len(required_norm)
    n_preferred = len(preferred_norm)

    required_coverage  = (len(matched_required)  / n_required)  if n_required  else 1.0
    preferred_coverage = (len(matched_preferred) / n_preferred) if n_preferred else 1.0

    proj_text = _project_text(resume_json)
    exp_text  = _experience_text(resume_json)

    project_coverage    = (sum(1 for n in required_norm if _skill_in_text(proj_text, n)) / n_required) if n_required else 1.0
    experience_coverage = (sum(1 for n in required_norm if _skill_in_text(exp_text,  n)) / n_required) if n_required else 1.0
    edu_score           = _education_score(resume_json, jd_json)

    # Scoring formula: 40% required · 20% projects · 20% experience · 10% education · 10% preferred
    score = (
        0.40 * required_coverage  +
        0.20 * project_coverage   +
        0.20 * experience_coverage +
        0.10 * edu_score          +
        0.10 * preferred_coverage
    ) * 100

    # ── Skill gap — structured output for Question Generator ─────────────
    # Required gaps are listed first (high priority) then preferred (medium).
    skill_gap: list[SkillGapEntry] = [
        SkillGapEntry(skill=orig, skill_type="required", priority="high")
        for orig in missing_required
    ] + [
        SkillGapEntry(skill=orig, skill_type="preferred", priority="medium")
        for orig in missing_preferred
    ]

    return MatchResult(
        score=score,
        required_coverage=required_coverage * 100,
        preferred_coverage=preferred_coverage * 100,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_preferred=matched_preferred,
        missing_preferred=missing_preferred,
        inferred_skills=inferred,
        skill_gap=skill_gap,
    )
