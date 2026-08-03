"""Unit tests for semantic_matching.prompt_builder."""

from __future__ import annotations

import pytest

from semantic_matching.exceptions import PromptBuildError
from semantic_matching.prompt_builder import build_semantic_match_prompt


def test_build_semantic_match_prompt_includes_resume_and_jd_sections():
    prompt = build_semantic_match_prompt(
        resume_json={
            "name": "Jane Doe",
            "skills": ["Python", "React"],
            "projects": ["Built Claude AI-powered chatbot using LLM APIs"],
            "experience": ["Backend intern, built REST APIs with Node.js"],
        },
        jd_json={
            "role": "GenAI Full Stack / Prompt Engineer Intern",
            "required_skills": ["Prompt Engineering", "RAG"],
            "preferred_skills": ["Next.js"],
            "responsibilities": ["Integrate LLM APIs into product features"],
        },
    )

    assert "=== CANDIDATE RESUME ===" in prompt
    assert "=== JOB DESCRIPTION ===" in prompt
    assert "Jane Doe" in prompt
    assert "Claude AI-powered chatbot" in prompt
    assert "GenAI Full Stack / Prompt Engineer Intern" in prompt
    assert "Prompt Engineering" in prompt
    assert "RAG" in prompt


def test_build_semantic_match_prompt_handles_missing_optional_fields():
    prompt = build_semantic_match_prompt(resume_json={}, jd_json={})

    assert "(not provided)" in prompt
    assert "(none listed)" in prompt


def test_build_semantic_match_prompt_handles_dict_shaped_entries():
    prompt = build_semantic_match_prompt(
        resume_json={"experience": [{"role": "Intern", "description": "Built APIs"}]},
        jd_json={},
    )

    assert "Intern" in prompt
    assert "Built APIs" in prompt


def test_build_semantic_match_prompt_rejects_non_dict_resume():
    with pytest.raises(PromptBuildError, match="resume_json"):
        build_semantic_match_prompt(["Python"], {})  # type: ignore[arg-type]


def test_build_semantic_match_prompt_rejects_non_dict_jd():
    with pytest.raises(PromptBuildError, match="jd_json"):
        build_semantic_match_prompt({}, ["Python"])  # type: ignore[arg-type]
