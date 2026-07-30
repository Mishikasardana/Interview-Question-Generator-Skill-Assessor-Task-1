"""Unit tests for prompt_builder.py."""

import pytest

from question_generation.exceptions import PromptBuildError
from question_generation.prompt_builder import build_question_prompt


def test_build_question_prompt_includes_inputs() -> None:
    prompt = build_question_prompt(
        resume_json={"skills": ["Python"]},
        jd_json={"required_skills": ["Python", "SQL"]},
        match_result_json={"matched_skills": ["Python"]},
        difficulty="Medium",
        question_count=3,
    )

    assert '"parsed_resume"' in prompt
    assert '"parsed_jd"' in prompt
    assert '"match_result"' in prompt
    assert '"difficulty": "medium"' in prompt
    assert '"question_count": 3' in prompt


def test_build_question_prompt_rejects_non_dict_inputs() -> None:
    with pytest.raises(PromptBuildError, match="resume_json"):
        build_question_prompt(
            resume_json=["Python"],  # type: ignore[arg-type]
            jd_json={},
            match_result_json={},
            difficulty="easy",
            question_count=1,
        )


def test_build_question_prompt_rejects_invalid_difficulty() -> None:
    with pytest.raises(PromptBuildError, match="Difficulty"):
        build_question_prompt({}, {}, {}, "expert", 1)


def test_build_question_prompt_rejects_invalid_question_count() -> None:
    with pytest.raises(PromptBuildError, match="between 1 and 20"):
        build_question_prompt({}, {}, {}, "easy", 0)


def test_build_question_prompt_rejects_boolean_question_count() -> None:
    with pytest.raises(PromptBuildError, match="Expected question_count"):
        build_question_prompt({}, {}, {}, "easy", True)
