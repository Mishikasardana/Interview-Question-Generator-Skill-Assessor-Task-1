#!/usr/bin/env python3
"""
Demo script for the Matching Engine module.

Runs the skill matching algorithm against a bundled sample resume + JD pair
and prints the full result — no GLM API key required (this module is pure
logic, no LLM calls).

Usage:
    python scripts/demo_matching.py
"""

from __future__ import annotations

import json

from matching_engine import run_matching

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


def main() -> None:
    result = run_matching(SAMPLE_RESUME, SAMPLE_JD)

    print("=" * 55)
    print("MATCHING ENGINE — DEMO OUTPUT")
    print("=" * 55)
    print(result.summary())
    print()
    print(f"Matched required  : {result.matched_required}")
    print(f"Missing required  : {result.missing_required}")
    print(f"Matched preferred : {result.matched_preferred}")
    print(f"Missing preferred : {result.missing_preferred}")
    print(f"Inferred (text)   : {result.inferred_skills}")
    print()
    print("Skill Gap (for Question Generator):")
    for gap in result.skill_gap:
        print(f"  [{gap.priority.upper():6s}] {gap.skill_type:9s} — {gap.skill}")
    print()
    print("Serialised dict (for API/DB):")
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
