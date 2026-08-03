"""Streamlit UI end-to-end tests using streamlit.testing.v1.AppTest."""

from __future__ import annotations

import json
import importlib
from pathlib import Path
import uuid
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from database.connection import DatabaseNotConfigured
from question_generation.schema import GeneratedQuestions, InterviewQuestion

pytestmark = pytest.mark.e2e

APP_PATH = Path(__file__).resolve().parents[2] / "app.py"


def _app() -> AppTest:
    return AppTest.from_file(str(APP_PATH))


def _auth_user(role: str = "student") -> dict:
    return {
        "id": uuid.uuid4(),
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone_number": None,
        "role": role,
        "is_verified": True,
        "has_password": True,
    }


def _markdown_values(at: AppTest) -> list[str]:
    return [markdown.value for markdown in at.markdown]


def _click_button_by_label(at: AppTest, label: str) -> AppTest:
    for button in at.button:
        if button.label == label:
            return button.click().run()
    raise AssertionError(f"Button not found: {label}")


def _set_text_input_by_label(at: AppTest, label: str, value: str) -> None:
    for widget in at.text_input:
        if widget.label == label:
            widget.set_value(value)
            return
    raise AssertionError(f"text_input not found: {label}")


def test_home_page_renders_portal_buttons():
    at = _app()
    at.run()

    labels = {button.label for button in at.button}
    assert "Start as Recruiter" in labels
    assert "Start as Student" in labels


def test_start_as_student_navigates_to_auth_gate(monkeypatch: pytest.MonkeyPatch):
    # Asserts the degraded state a fresh clone shows before OAuth
    # credentials are set up. st.user is forced empty rather than relying on
    # ".streamlit/secrets.toml doesn't exist here" — that file is gitignored
    # but present on any machine where Google sign-in was actually
    # configured, which would otherwise fail this test locally only.
    monkeypatch.setattr("app.st.user", {})

    at = _app()
    at.run()
    at.button(key="start_student").click().run()

    assert at.session_state["page"] == "student"
    assert at.session_state["pending_role"] == "student"
    infos = [info.value for info in at.info]
    assert any("Google sign-in isn't configured" in text for text in infos)


def test_protected_interview_page_shows_auth_without_login(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.st.user", {})

    at = _app()
    at.session_state["page"] = "interview"
    at.run()

    infos = [info.value for info in at.info]
    assert any("Google sign-in isn't configured" in text for text in infos)


def test_authenticated_student_sees_dashboard():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    titles = [markdown.value for markdown in at.markdown if "Dashboard" in markdown.value]
    assert titles, "Expected authenticated student dashboard content"


def test_student_dashboard_starts_on_resume_upload_step():
    # A fresh session (nothing parsed yet) should show step 1 only — the JD
    # and question-generation controls must not be reachable before a
    # resume exists, since the flow is now a guided pipeline rather than a
    # grid of independent, order-free cards.
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    markdown = _markdown_values(at)
    assert any("Upload your resume" in value for value in markdown)
    button_keys = {button.key for button in at.button}
    assert "parse_resume_btn" in button_keys
    assert "parse_jd_student_btn" not in button_keys
    assert "student_gen_q_btn" not in button_keys


def test_completed_step_summary_escapes_html_in_resume_name():
    # The resume name shown in the "step completed" summary comes from
    # the AI-extracted parsed_resume JSON — text an attacker could try to
    # steer via a crafted resume. _render_completed_step renders it via
    # unsafe_allow_html=True, so it must come out escaped, not executed.
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["parsed_resume"] = {
        "name": '<img src=x onerror=alert(1)>',
        "skills": ["Python"],
    }
    at.run()

    markdown = _markdown_values(at)
    step_markdown = [value for value in markdown if "step-summary" in value]
    assert step_markdown, "expected the completed-step summary to render"
    assert not any("<img" in value for value in step_markdown)
    assert any("&lt;img" in value for value in step_markdown)


def test_student_dashboard_reaches_ready_to_practice_step():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["parsed_resume"] = {"name": "Jane Doe", "skills": ["Python"]}
    at.session_state["parsed_jd"] = {"role": "Backend Engineer"}
    at.session_state["questions"] = [
        {"question": "Q1?", "category": "Technical", "difficulty": "medium", "reason": "R"},
    ]
    at.run()

    markdown = _markdown_values(at)
    assert any("questions ready" in value.lower() for value in markdown)
    assert at.button(key="start_interview_btn").label == "Start Practice Interview"


def test_student_dashboard_match_card_shows_one_score_no_recommendation():
    # "One Recruiter Match Score" plan: exactly one card, one score, no
    # competing percentages. Students see the score/missing-skills
    # breakdown but not the hire/reject-style recommendation callout --
    # that's a recruiter-only hiring decision, not something a student
    # practicing on themselves needs framed that way.
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["parsed_resume"] = {"name": "Jane Doe", "skills": ["Python"]}
    at.session_state["parsed_jd"] = {"role": "Backend Engineer"}
    at.session_state["recruiter_match_result"] = {
        "recruiter_match_score": 80, "confidence": "High",
        "confidence_reason": "all non-missing requirements had direct evidence and no hard-gate ambiguity",
        "recommendation": "Strong Hire",
        "hard_gate": {"overall_status": "pass", "results": []},
        "role_archetype": "backend",
        "critical_missing_skills": ["SQL"], "minor_missing_skills": [], "nice_to_have_missing_skills": ["Docker"],
        "requirement_breakdown": [], "narrative": "Recommendation: Strong Hire",
        "ontology_version": "1.0.0", "scoring_config_version": "1.0.0",
    }
    at.run()

    metric_labels = {metric.label for metric in at.metric}
    assert metric_labels == {"Recruiter Match Score"}  # exactly one score metric on the page
    expander_labels = {expander.label for expander in at.expander}
    assert {"Critical Missing Skills", "Minor / Nice-to-have Missing Skills", "Why this score"} <= expander_labels
    # The recommendation callout badge (st.success/warning/error) is hidden
    # for students -- the narrative text in the "Why this score" expander
    # still mentions it for context, which is fine and expected.
    callout_values = [el.value for el in (*at.success, *at.warning, *at.error)]
    assert not any("Strong Hire" in value for value in callout_values)


def test_recruiter_dashboard_match_card_shows_one_score_with_recommendation():
    # Recruiters see the same single score plus the recommendation callout
    # (a real hiring decision), and — the headline behavior change of this
    # plan — no second card, no competing percentage anywhere on the page.
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["FastAPI"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Express.js"]}
    at.session_state["recruiter_match_result"] = {
        "recruiter_match_score": 85, "confidence": "High",
        "confidence_reason": "1/1 requirements had direct evidence citations.",
        "recommendation": "Strong Hire",
        "hard_gate": {"overall_status": "pass", "results": []},
        "role_archetype": "backend",
        "critical_missing_skills": [], "minor_missing_skills": [], "nice_to_have_missing_skills": [],
        "requirement_breakdown": [], "narrative": "Recommendation: Strong Hire (confidence: High)",
        "ontology_version": "1.0.0", "scoring_config_version": "1.0.0",
    }
    at.run()

    markdown = _markdown_values(at)
    assert any("Match result" in value for value in markdown)
    metric_labels = {metric.label for metric in at.metric}
    assert metric_labels == {"Recruiter Match Score"}
    assert any("Strong Hire" in value for value in markdown)


def test_recruiter_match_card_shows_friendly_error():
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["Python"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Python"]}
    at.session_state["recruiter_match_error"] = (
        "Match evaluation is unavailable right now. (GLM API key not configured.)"
    )
    at.run()

    markdown = _markdown_values(at)
    assert any("Match result" in value for value in markdown)
    info_values = [info.value for info in at.info]
    assert any("unavailable right now" in value for value in info_values)


def test_authenticated_recruiter_sees_dashboard():
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    markdown = _markdown_values(at)
    assert any("Dashboard" in value for value in markdown)
    assert at.button(key="parse_jd_recruiter_btn").label == "Continue"


def test_recruiter_dashboard_starts_on_jd_upload_step():
    # Same reasoning as the student flow: nothing should be reachable
    # before the job description exists.
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    markdown = _markdown_values(at)
    assert any("Upload the job description" in value for value in markdown)
    button_keys = {button.key for button in at.button}
    assert "parse_jd_recruiter_btn" in button_keys
    assert "recruiter_parse_resume_btn" not in button_keys
    assert "recruiter_gen_q" not in button_keys


def test_recruiter_dashboard_reaches_generate_questions_step():
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["Python"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Python"]}
    at.session_state["match_result"] = {
        "score": 75.0, "matched_required": ["Python"], "missing_required": [],
        "matched_preferred": [], "missing_preferred": [],
    }
    at.run()

    assert at.button(key="recruiter_gen_q").label == "Generate Questions"


@patch("question_generation.generate_questions.generate_questions")
def test_recruiter_generate_questions_uses_recruiter_match_result_not_matching_engine(mock_generate):
    # Phase 4 of the "One Recruiter Match Score" plan: question_generation's
    # input now comes from recruiter_match_result (via _question_generation_context),
    # not matching_engine's old matched_required/missing_required shape --
    # confirmed here by checking the actual kwargs generate_questions was
    # called with.
    mock_generate.return_value = GeneratedQuestions(questions=[
        InterviewQuestion(question="Q1?", category="Technical", difficulty="medium", reason="R"),
    ])
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["Python", "Docker"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Python"]}
    at.session_state["match_result"] = {
        "score": 50.0, "matched_required": ["Python"], "missing_required": ["Docker"],
        "matched_preferred": [], "missing_preferred": [],
    }
    at.session_state["recruiter_match_result"] = {
        "recruiter_match_score": 82, "confidence": "High", "confidence_reason": "dense evidence",
        "recommendation": "Strong Hire",
        "hard_gate": {"overall_status": "pass", "results": []},
        "role_archetype": "backend",
        "critical_missing_skills": ["Docker"], "minor_missing_skills": [], "nice_to_have_missing_skills": [],
        "requirement_breakdown": [
            {"requirement_id": "req_1", "text": "Python", "is_required": True, "category": "Backend Engineering",
             "difficulty_tier": "medium", "score": 95, "final_weight": 1.0, "contribution": 95.0,
             "is_missing": False, "evidence": [], "verified_evidence_count": 0, "reasoning": "Direct match."},
            {"requirement_id": "req_2", "text": "Docker", "is_required": True, "category": "DevOps & CI/CD",
             "difficulty_tier": "easy", "score": 5, "final_weight": 0.5, "contribution": 2.5,
             "is_missing": True, "evidence": [], "verified_evidence_count": 0, "reasoning": "No evidence found."},
        ],
        "narrative": "Recommendation: Strong Hire",
        "ontology_version": "1.0.0", "scoring_config_version": "1.0.0",
    }
    at.run()

    at.button(key="recruiter_gen_q").click().run()

    assert mock_generate.call_args is not None
    match_result_json = mock_generate.call_args.kwargs["match_result_json"]
    assert match_result_json["score"] == 82
    assert match_result_json["critical_missing_skills"] == ["Docker"]
    assert "matched_required" not in match_result_json
    assert any(
        note["skill"] == "Docker" and note["score"] == 5
        for note in match_result_json["requirement_notes"]
    )


@patch("question_generation.generate_questions.generate_questions")
def test_recruiter_generate_questions_proceeds_with_empty_context_when_recruiter_result_missing(
    mock_generate,
):
    # If the recruiter evaluation wasn't available for this session (e.g.
    # the GLM call failed), question generation should still proceed with
    # less context (an empty match_result_json) rather than block entirely.
    mock_generate.return_value = GeneratedQuestions(questions=[
        InterviewQuestion(question="Q1?", category="Technical", difficulty="medium", reason="R"),
    ])
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["Python"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Python"]}
    # recruiter_match_result deliberately left unset (None, its default).
    at.run()

    at.button(key="recruiter_gen_q").click().run()

    assert mock_generate.call_args is not None
    assert mock_generate.call_args.kwargs["match_result_json"] == {}


def test_recruiter_role_mismatch_shows_warning():
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("student")
    at.run()

    warnings = [warning.value for warning in at.warning]
    assert any("recruiter accounts" in text.lower() for text in warnings)


def test_recruiter_sidebar_does_not_show_practice_interview_nav():
    # Regression test: "Interview"/"Report" are candidate-only concepts —
    # a recruiter never takes their own practice interview, and "Report"
    # would only ever show their own (nonexistent) completed sessions.
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    button_keys = {button.key for button in at.button}
    assert "nav_interview" not in button_keys
    assert "nav_report" not in button_keys
    assert "nav_candidates" in button_keys


def test_student_sidebar_does_not_show_candidates_nav():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    button_keys = {button.key for button in at.button}
    assert "nav_candidates" not in button_keys
    assert "nav_interview" in button_keys
    assert "nav_report" in button_keys


def test_logged_in_sidebar_drops_home_and_portal_picker():
    # Phase 2: a logged-in user's role is fixed (email is globally
    # unique), so re-showing the Recruiter/Student portal picker or a
    # "Home" link that just bounces back to the dashboard is dead weight.
    # Down to Dashboard + role-specific item(s) + Settings.
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    button_keys = {button.key for button in at.button}
    assert "nav_home" not in button_keys
    assert "nav_recruiter" not in button_keys
    assert "nav_student" not in button_keys
    assert "nav_dashboard" in button_keys
    assert "nav_settings" in button_keys


def test_logged_out_sidebar_still_shows_portal_picker():
    # The portal picker is still needed before anyone is logged in.
    at = _app()
    at.run()

    button_keys = {button.key for button in at.button}
    assert "nav_home" in button_keys
    assert "nav_recruiter" in button_keys
    assert "nav_student" in button_keys
    assert "nav_dashboard" not in button_keys


def test_sidebar_dashboard_button_navigates_to_own_role():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    at.button(key="nav_dashboard").click().run()

    assert at.session_state["page"] == "recruiter"


def test_sidebar_user_card_escapes_html_in_name_and_email():
    # Name/email are free text from the signup form — a user could put
    # something like <img src=x onerror=...> in their own name. The
    # sidebar card renders them via unsafe_allow_html=True, so they must
    # come out HTML-escaped, not executed as markup.
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = {
        "id": uuid.uuid4(),
        "name": '<img src=x onerror=alert(1)>',
        "email": '"><script>alert(1)</script>',
        "phone_number": None,
        "role": "student",
    }
    at.session_state["role"] = "student"
    at.run()

    markdown = _markdown_values(at)
    card_markdown = [value for value in markdown if "sidebar-user-card" in value]
    assert card_markdown, "expected the sidebar user card to render"
    assert not any("<img" in value for value in card_markdown)
    assert not any("<script>" in value for value in card_markdown)
    assert any("&lt;img" in value for value in card_markdown)
    assert any("&lt;script&gt;" in value for value in card_markdown)


def test_settings_page_renders_for_logged_in_user():
    # Phase 2: "Profile" was renamed/reframed as "Settings" — same
    # underlying form, but the page key, heading, and nav label all
    # changed from "profile"/"Profile" to "settings"/"Settings".
    at = _app()
    at.session_state["page"] = "settings"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    markdown = _markdown_values(at)
    assert any("Settings" in value for value in markdown)
    labels = {button.label for button in at.button}
    assert "Log Out" in labels


def test_recruiter_visiting_interview_page_redirects_to_own_dashboard():
    # Defense in depth: even if a recruiter's session state somehow points
    # at the candidate-only Interview page directly, they should be
    # redirected to their own dashboard rather than shown it.
    at = _app()
    at.session_state["page"] = "interview"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    assert at.session_state["page"] == "recruiter"
    markdown = _markdown_values(at)
    assert any("Dashboard" in value for value in markdown)


def test_student_visiting_candidates_page_redirects_to_own_dashboard():
    at = _app()
    at.session_state["page"] = "candidates"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    assert at.session_state["page"] == "student"


def test_recruiter_candidates_page_shows_empty_state_with_no_screenings():
    at = _app()
    at.session_state["page"] = "candidates"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.run()

    markdown = _markdown_values(at)
    assert any("No candidates screened yet" in value for value in markdown)
    labels = {button.label for button in at.button}
    assert "Go to Dashboard" in labels


def test_recruiter_dashboard_report_button_navigates_to_candidates():
    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["auth_user"] = _auth_user("recruiter")
    at.session_state["role"] = "recruiter"
    at.session_state["parsed_jd"] = {"role": "Backend Engineer", "required_skills": ["Python"]}
    at.session_state["parsed_resume"] = {"name": "Candidate One", "skills": ["Python"]}
    at.session_state["match_result"] = {
        "score": 75.0, "matched_required": ["Python"], "missing_required": [],
        "matched_preferred": [], "missing_preferred": [],
    }
    at.session_state["questions"] = [
        {"question": "Q1?", "category": "Technical", "difficulty": "medium", "reason": "R"},
    ]
    at.run()

    _click_button_by_label(at, "View Candidate Reports")

    assert at.session_state["page"] == "candidates"


def test_home_page_redirects_logged_in_user_to_own_dashboard():
    # A logged-in user has already picked a portal — clicking "Home" (or
    # landing there after login) should skip the marketing landing page
    # entirely and go straight to their workspace.
    at = _app()
    at.session_state["page"] = "home"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    assert at.session_state["page"] == "student"
    markdown = _markdown_values(at)
    assert any("Dashboard" in value for value in markdown)


def test_interview_submit_answer_evaluates_with_generated_question(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_evaluate_answer_text(*_args, **_kwargs):
        return json.dumps(
            {
                "overall_score": 88,
                "correctness": 26,
                "keyword_coverage": 22,
                "clarity": 18,
                "communication": 14,
                "completeness": 8,
                "strengths": ["Concrete API example"],
                "improvements": ["Mention testing"],
                "feedback": "Strong response.",
                "ideal_answer": "Discuss design, trade-offs, and testing.",
            }
        )

    evaluate_answer_module = importlib.import_module("answer_evaluation.evaluate_answer")
    monkeypatch.setattr(
        evaluate_answer_module,
        "evaluate_answer_text",
        fake_evaluate_answer_text,
    )

    at = _app()
    at.session_state["page"] = "interview"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["questions"] = [
        {
            "question": "How do you build REST APIs in Python?",
            "category": "Technical",
            "difficulty": "medium",
            "reason": "Python is required.",
        }
    ]
    at.session_state["parsed_jd"] = {
        "role": "Backend Engineer",
        "required_skills": ["Python"],
    }
    at.session_state["answers"] = {0: "I build REST APIs with Python and FastAPI."}
    at.run()
    at.text_area(key="answer_text_0").set_value(
        "I build REST APIs with Python and FastAPI."
    ).run()

    _click_button_by_label(at, "Submit Answer")

    assert at.session_state["evaluations"][0]["overall_score"] == 88
    successes = [success.value for success in at.success]
    assert any("Answer submitted and evaluated" in text for text in successes)


def test_interview_page_shows_empty_state_when_no_questions_generated():
    # No dummy/placeholder questions anymore — a stale or absent question
    # set should show a real empty state pointing back to the Dashboard,
    # not fake sample content (and, incidentally, this also means a stale
    # current_question_index can no longer index past a shorter list,
    # since the page returns before ever indexing into `questions`).
    at = _app()
    at.session_state["page"] = "interview"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["questions"] = None
    at.session_state["current_question_index"] = 8
    at.run()

    assert not at.exception
    markdown = _markdown_values(at)
    assert any("No practice questions yet" in value for value in markdown)
    labels = {button.label for button in at.button}
    assert "Go to Dashboard" in labels


def test_report_page_renders_seeded_evaluation_summary():
    at = _app()
    at.session_state["page"] = "report"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.session_state["evaluations"] = {
        0: {
            "overall_score": 80,
            "correctness": 24,
            "keyword_coverage": 20,
            "clarity": 16,
            "communication": 12,
            "completeness": 8,
            "strengths": ["Clear structure"],
            "improvements": ["Add more examples"],
            "feedback": "Good answer.",
            "ideal_answer": "A stronger answer would include trade-offs.",
        },
        1: {
            "overall_score": 90,
            "correctness": 27,
            "keyword_coverage": 23,
            "clarity": 18,
            "communication": 14,
            "completeness": 8,
            "strengths": ["Specific details"],
            "improvements": [],
            "feedback": "Excellent answer.",
            "ideal_answer": "Keep the same structure.",
        },
    }
    at.run()

    markdown = _markdown_values(at)
    assert any("Practice Result" in value for value in markdown)
    assert any("Evaluation Metrics" in value for value in markdown)
    assert any("Per-Question Breakdown" in value for value in markdown)
    assert any(metric.label == "Overall Score (avg)" and metric.value == "85 / 100" for metric in at.metric)


def test_report_page_shows_empty_state_when_no_evaluations():
    # No fabricated 78/100 placeholder scorecard anymore — a session with
    # no completed practice interview should say so plainly instead of
    # showing data that looks real but isn't.
    at = _app()
    at.session_state["page"] = "report"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()

    markdown = _markdown_values(at)
    assert any("No completed practice interview yet" in value for value in markdown)
    # Skip <style> blocks — theme CSS legitimately contains "78" inside
    # colors like rgba(29,78,216,...), unrelated to the old fake scorecard.
    content_markdown = [value for value in markdown if "<style>" not in value]
    assert not any("78 / 100" in value for value in content_markdown)
    labels = {button.label for button in at.button}
    assert "Go to Dashboard" in labels


def test_google_login_shows_clean_error_when_database_unreachable(
    monkeypatch: pytest.MonkeyPatch,
):
    # Regression coverage for the Google flow's equivalent of the old
    # signup/login DB-unreachable regression: DATABASE_URL present but
    # pointing at an unreachable/misconfigured database must surface a
    # clean message, not a raw sqlalchemy.exc.OperationalError traceback.
    from sqlalchemy.exc import OperationalError

    def _raise_operational_error(*_args, **_kwargs):
        raise OperationalError("connect failed", {}, Exception('role "USERNAME" does not exist'))

    monkeypatch.setattr("app.db_repo.get_user_by_email", _raise_operational_error)
    monkeypatch.setattr(
        "app.st.user",
        {
            "is_logged_in": True,
            "email": "test@example.com",
            "name": "Test User",
            "sub": "google-sub-123",
            "provider": "student",
        },
    )

    at = _app()
    at.session_state["page"] = "student"
    at.run()

    assert not at.exception
    errors = [error.value for error in at.error]
    assert any("database" in text.lower() for text in errors)


def test_google_and_settings_submit_buttons_are_primary_styled(
    monkeypatch: pytest.MonkeyPatch,
):
    # Phase 6 polish: the Settings-save form_submit_button was never given
    # type="primary", unlike every other "main action" button in the app —
    # and since it renders in a different wrapper (div.stFormSubmitButton,
    # not div.stButton), it'd also silently fall back to Streamlit's plain
    # default styling instead of matching the rest of the app. The Google
    # sign-in button is this page's one primary CTA and should match too.
    monkeypatch.setattr("app.st.user", {"is_logged_in": False})

    at = _app()
    at.session_state["page"] = "recruiter"
    at.run()
    google_btn = next(b for b in at.button if b.label == "Continue with Google")
    assert google_btn.proto.type == "primary"

    at = _app()
    at.session_state["page"] = "settings"
    at.session_state["auth_user"] = _auth_user("student")
    at.session_state["role"] = "student"
    at.run()
    save_btn = next(b for b in at.button if b.label == "Save Changes")
    assert save_btn.proto.type == "primary"


def test_auth_page_warns_when_database_not_configured(monkeypatch: pytest.MonkeyPatch):
    def _raise_not_configured() -> None:
        raise DatabaseNotConfigured("not configured")

    monkeypatch.setattr("database.connection.get_database_url", _raise_not_configured)
    monkeypatch.setattr("app.get_database_url", _raise_not_configured, raising=False)

    at = _app()
    at.session_state["page"] = "student"
    at.run()

    warnings = [warning.value for warning in at.warning]
    assert any("DATABASE_URL" in text for text in warnings)


def _fill_signup_form(at: AppTest, *, email: str, password: str = "StrongPass1!", confirm: str | None = None) -> None:
    # Every field the signup form requires must be filled here, including
    # Phone Number and the Terms checkbox — _handle_signup_submit rejects
    # the whole form before any per-field check (password match, strength,
    # ...) if any required field is blank, so a helper that skips one makes
    # every test below assert against the wrong error.
    _set_text_input_by_label(at, "Full Name", "Test User")
    _set_text_input_by_label(at, "Email", email)
    _set_text_input_by_label(at, "Phone Number", "+1 555 123 4567")
    _set_text_input_by_label(at, "Password", password)
    _set_text_input_by_label(at, "Confirm Password", confirm if confirm is not None else password)
    at.checkbox(key="signup_terms").set_value(True)


@pytest.mark.needs_db
def test_email_signup_creates_account_and_logs_in():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    assert at.session_state["auth_mode"] == "signup"

    email = f"signup-{uuid.uuid4().hex[:8]}@example.com"
    _fill_signup_form(at, email=email)
    at.run()
    at = _click_button_by_label(at, "Create Account")

    assert not at.exception
    assert at.session_state["auth_user"] is not None
    assert at.session_state["auth_user"]["email"] == email
    assert at.session_state["auth_user"]["role"] == "student"
    assert at.session_state["auth_user"]["is_verified"] is False
    assert at.session_state["dev_email_preview"] is not None
    assert "verify_token=" in at.session_state["dev_email_preview"]["link"]


@pytest.mark.needs_db
def test_email_signup_rejects_duplicate_email():
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(at, email=email)
    at.run()
    at = _click_button_by_label(at, "Create Account")
    assert at.session_state["auth_user"] is not None

    at2 = _app()
    at2.session_state["page"] = "student"
    at2.session_state["pending_role"] = "student"
    at2.run()
    at2 = _click_button_by_label(at2, "Create Account")
    _fill_signup_form(at2, email=email)
    at2.run()
    at2 = _click_button_by_label(at2, "Create Account")

    assert at2.session_state["auth_user"] is None
    errors = [e.value for e in at2.error]
    assert any("already exists" in text for text in errors)


def test_email_signup_rejects_mismatched_passwords():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(
        at, email=f"mismatch-{uuid.uuid4().hex[:8]}@example.com",
        password="StrongPass1!", confirm="Different1!",
    )
    at.run()
    at = _click_button_by_label(at, "Create Account")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("do not match" in text for text in errors)


def test_email_signup_rejects_weak_password():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(at, email=f"weak-{uuid.uuid4().hex[:8]}@example.com", password="weak")
    at.run()
    at = _click_button_by_label(at, "Create Account")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("Password must have" in text for text in errors)


def _create_email_account(*, role: str = "student", password: str = "StrongPass1!") -> str:
    """Creates a real email/password account via the signup flow and
    returns its email — a small helper shared by the login/verify/reset
    tests below, all of which need a genuine account already on file."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    at = _app()
    at.session_state["page"] = role
    at.session_state["pending_role"] = role
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(at, email=email, password=password)
    at.run()
    _click_button_by_label(at, "Create Account")
    return email


@pytest.mark.needs_db
def test_email_login_succeeds_with_correct_credentials():
    email = _create_email_account(role="student")

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    _set_text_input_by_label(at, "Email", email)
    _set_text_input_by_label(at, "Password", "StrongPass1!")
    at.run()
    at = _click_button_by_label(at, "Login")

    assert not at.exception
    assert at.session_state["auth_user"] is not None
    assert at.session_state["auth_user"]["email"] == email


@pytest.mark.needs_db
def test_email_login_rejects_wrong_password():
    email = _create_email_account(role="student")

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    _set_text_input_by_label(at, "Email", email)
    _set_text_input_by_label(at, "Password", "WrongPassword!")
    at.run()
    at = _click_button_by_label(at, "Login")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("Invalid email or password" in text for text in errors)


@pytest.mark.needs_db
def test_email_login_rejects_unknown_email():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    _set_text_input_by_label(at, "Email", f"missing-{uuid.uuid4().hex[:8]}@example.com")
    _set_text_input_by_label(at, "Password", "WhateverPass1!")
    at.run()
    at = _click_button_by_label(at, "Login")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("Invalid email or password" in text for text in errors)


@pytest.mark.needs_db
def test_email_login_shows_role_mismatch_warning():
    email = _create_email_account(role="student")

    at = _app()
    at.session_state["page"] = "recruiter"
    at.session_state["pending_role"] = "recruiter"
    at.run()
    _set_text_input_by_label(at, "Email", email)
    _set_text_input_by_label(at, "Password", "StrongPass1!")
    at.run()
    at = _click_button_by_label(at, "Login")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("registered as a student" in text for text in errors)


@pytest.mark.needs_db
def test_email_login_locks_out_after_repeated_failures():
    import rate_limiter

    email = _create_email_account(role="student")
    rate_limiter._login_attempts.pop(email, None)

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    for _ in range(rate_limiter.LOGIN_MAX_ATTEMPTS):
        _set_text_input_by_label(at, "Email", email)
        _set_text_input_by_label(at, "Password", "WrongPassword!")
        at.run()
        at = _click_button_by_label(at, "Login")

    _set_text_input_by_label(at, "Email", email)
    _set_text_input_by_label(at, "Password", "StrongPass1!")  # even the correct password now
    at.run()
    at = _click_button_by_label(at, "Login")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("Too many failed attempts" in text for text in errors)

    rate_limiter._login_attempts.pop(email, None)


@pytest.mark.needs_db
def test_signup_against_existing_google_only_account_is_rejected():
    # Security guardrail: the public signup form must never be usable to
    # attach a password to somebody else's existing Google-linked account.
    from database import repositories as db_repo

    email = f"google-{uuid.uuid4().hex[:8]}@example.com"
    db_repo.get_or_create_oauth_user(
        email=email, name="Google User", role="student", google_id=f"sub-{uuid.uuid4().hex[:8]}",
    )

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(at, email=email)
    at.run()
    at = _click_button_by_label(at, "Create Account")

    assert at.session_state["auth_user"] is None
    errors = [e.value for e in at.error]
    assert any("already exists" in text for text in errors)


@pytest.mark.needs_db
def test_forgot_password_flow_creates_usable_reset_link():
    email = _create_email_account(role="student")

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Forgot Password?")
    assert at.session_state["auth_mode"] == "forgot_password"

    _set_text_input_by_label(at, "Email", email)
    at.run()
    at = _click_button_by_label(at, "Send Reset Link")

    successes = [s.value for s in at.success]
    assert any("password reset link has been created" in text for text in successes)
    codes = [c.value for c in at.code]
    assert codes and "reset_token=" in codes[0]


@pytest.mark.needs_db
def test_forgot_password_never_issues_a_token_for_google_only_account():
    from database import repositories as db_repo

    email = f"google-{uuid.uuid4().hex[:8]}@example.com"
    db_repo.get_or_create_oauth_user(
        email=email, name="Google User", role="student", google_id=f"sub-{uuid.uuid4().hex[:8]}",
    )

    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Forgot Password?")
    _set_text_input_by_label(at, "Email", email)
    at.run()
    at = _click_button_by_label(at, "Send Reset Link")

    # Same generic message either way, but no usable token/link is shown.
    successes = [s.value for s in at.success]
    assert any("password reset link has been created" in text for text in successes)
    assert not list(at.code)


@pytest.mark.needs_db
def test_reset_password_link_lets_user_set_a_new_password_and_log_in():
    from database import repositories as db_repo

    email = _create_email_account(role="student")
    raw_token = db_repo.create_password_reset_token(email=email)
    assert raw_token is not None

    at = _app()
    at.query_params["reset_token"] = raw_token
    at.run()

    assert not at.exception
    assert at.session_state["auth_mode"] == "reset_password"

    _set_text_input_by_label(at, "New Password", "BrandNewPass1!")
    _set_text_input_by_label(at, "Confirm New Password", "BrandNewPass1!")
    at.run()
    at = _click_button_by_label(at, "Set New Password")

    assert at.session_state["auth_mode"] == "login"
    successes = [s.value for s in at.success]
    assert any("password has been reset" in text for text in successes)

    # Log in with the new password to confirm it actually took effect.
    at2 = _app()
    at2.session_state["page"] = "student"
    at2.session_state["pending_role"] = "student"
    at2.run()
    _set_text_input_by_label(at2, "Email", email)
    _set_text_input_by_label(at2, "Password", "BrandNewPass1!")
    at2.run()
    at2 = _click_button_by_label(at2, "Login")
    assert at2.session_state["auth_user"] is not None


@pytest.mark.needs_db
def test_reset_password_rejects_invalid_or_expired_token():
    at = _app()
    at.query_params["reset_token"] = "not-a-real-token"
    at.run()

    assert not at.exception
    errors = [e.value for e in at.error]
    assert any("invalid or has expired" in text for text in errors)


@pytest.mark.needs_db
def test_verify_email_link_marks_account_verified():
    # The dev-stub verification link is created at signup time (not on a
    # later login), so capture it right there rather than via the shared
    # _create_email_account helper.
    email = f"verify-{uuid.uuid4().hex[:8]}@example.com"
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["pending_role"] = "student"
    at.run()
    at = _click_button_by_label(at, "Create Account")
    _fill_signup_form(at, email=email)
    at.run()
    at = _click_button_by_label(at, "Create Account")
    assert at.session_state["auth_user"]["is_verified"] is False

    link = at.session_state["dev_email_preview"]["link"]
    verify_token = link.split("verify_token=")[1]

    at2 = _app()
    at2.query_params["verify_token"] = verify_token
    at2.run()

    assert not at2.exception
    successes = [s.value for s in at2.success]
    assert any("verified" in text for text in successes)


def test_verify_banner_shows_for_unverified_email_user():
    at = _app()
    at.session_state["page"] = "student"
    user = _auth_user("student")
    user["is_verified"] = False
    at.session_state["auth_user"] = user
    at.session_state["role"] = "student"
    at.run()

    warnings = [w.value for w in at.warning]
    assert any("verify your email" in text for text in warnings)


def test_verify_banner_absent_for_verified_user():
    at = _app()
    at.session_state["page"] = "student"
    at.session_state["auth_user"] = _auth_user("student")  # is_verified=True by default
    at.session_state["role"] = "student"
    at.run()

    warnings = [w.value for w in at.warning]
    assert not any("verify your email" in text for text in warnings)


def test_settings_set_password_only_offered_to_passwordless_google_account():
    at = _app()
    at.session_state["page"] = "settings"
    user = _auth_user("student")
    user["has_password"] = False
    at.session_state["auth_user"] = user
    at.session_state["role"] = "student"
    at.run()

    assert any("Set Password" == b.label for b in at.button)


def test_settings_set_password_hidden_when_already_has_password():
    at = _app()
    at.session_state["page"] = "settings"
    at.session_state["auth_user"] = _auth_user("student")  # has_password=True by default
    at.session_state["role"] = "student"
    at.run()

    assert not any("Set Password" == b.label for b in at.button)


@pytest.mark.needs_db
def test_settings_set_password_succeeds_for_google_only_account():
    from database import repositories as db_repo

    email = f"google-{uuid.uuid4().hex[:8]}@example.com"
    google_user = db_repo.get_or_create_oauth_user(
        email=email, name="Google User", role="student", google_id=f"sub-{uuid.uuid4().hex[:8]}",
    )

    at = _app()
    at.session_state["page"] = "settings"
    user = _auth_user("student")
    user["id"] = google_user.id
    user["email"] = email
    user["has_password"] = False
    at.session_state["auth_user"] = user
    at.session_state["role"] = "student"
    at.run()

    _set_text_input_by_label(at, "New Password", "NewSecurePass1!")
    _set_text_input_by_label(at, "Confirm Password", "NewSecurePass1!")
    at.run()
    at = _click_button_by_label(at, "Set Password")

    assert at.session_state["auth_user"]["has_password"] is True
    successes = [s.value for s in at.success]
    assert any("Password set" in text for text in successes)

    # And the account can now log in via email/password too.
    at2 = _app()
    at2.session_state["page"] = "student"
    at2.session_state["pending_role"] = "student"
    at2.run()
    _set_text_input_by_label(at2, "Email", email)
    _set_text_input_by_label(at2, "Password", "NewSecurePass1!")
    at2.run()
    at2 = _click_button_by_label(at2, "Login")
    assert at2.session_state["auth_user"] is not None


def test_about_page_renders_from_sidebar():
    at = _app()
    at.run()
    at.button(key="nav_about").click().run()

    assert at.session_state["page"] == "about"
    titles = [markdown.value for markdown in at.markdown if "About" in markdown.value]
    assert titles


def test_page_titles_are_real_headings_not_styled_divs():
    # Phase 5 (accessibility): every page's main title used to be a plain
    # <div class="section-title"> — invisible to screen-reader heading
    # navigation, which is one of the most common ways screen-reader users
    # scan a page. Each inner page (no marketing hero of its own) should
    # render its title as a real <h1>, and the logged-out Home page (which
    # already has its own <h1> in the hero) should NOT get a second one.
    cases = [
        ("student", _auth_user("student"), "student", "Dashboard"),
        ("recruiter", _auth_user("recruiter"), "recruiter", "Dashboard"),
        ("settings", _auth_user("student"), "student", "Settings"),
        ("candidates", _auth_user("recruiter"), "recruiter", "Candidates"),
    ]
    for page, user, role, expected_text in cases:
        at = _app()
        at.session_state["page"] = page
        at.session_state["auth_user"] = user
        at.session_state["role"] = role
        at.run()

        h1_values = [m.value for m in at.markdown if "<h1" in m.value]
        assert any(expected_text in value for value in h1_values), (
            f"page={page!r}: expected an <h1> containing {expected_text!r}, "
            f"got {h1_values!r}"
        )


def test_home_page_has_exactly_one_h1():
    # The hero already provides the page's one true <h1> — "Choose Your
    # Portal" must not introduce a second one (should be a subsection
    # heading instead, since it's not asserting a new h1 as it was fixed
    # away from the generic section-title div).
    at = _app()
    at.run()

    h1_count = sum(m.value.count("<h1") for m in at.markdown)
    assert h1_count == 1
