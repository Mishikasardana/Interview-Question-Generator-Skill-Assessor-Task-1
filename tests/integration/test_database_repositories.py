"""PostgreSQL integration tests for database.repositories.

Skipped unless TEST_DATABASE_URL is set in the environment.
"""

from __future__ import annotations

import os
import uuid

import pytest

from database.connection import get_engine, init_db
from database.exceptions import UserAlreadyExistsError
from database.repositories import (
    authenticate_user,
    complete_interview_session,
    create_interview_session,
    create_user,
    get_report_detail,
    list_recent_candidate_screenings,
    list_recent_reports,
    save_answer,
    save_evaluation,
    save_job_description,
    save_match_result,
    save_question_set,
    save_report,
    save_resume,
    update_match_result_recruiter,
    update_match_result_semantic,
    update_user_profile,
)

pytestmark = pytest.mark.integration

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()


@pytest.fixture(scope="module")
def db_ready():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set")

    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    get_engine.cache_clear()

    init_db()
    yield
    get_engine.cache_clear()


def test_create_and_authenticate_user_round_trip(db_ready):
    email = f"test-{uuid.uuid4()}@example.com"

    user = create_user(
        name="Integration Tester",
        email=email,
        password="integration-password",
        role="student",
    )
    assert user.email == email

    authenticated = authenticate_user(email=email, password="integration-password")
    assert authenticated is not None
    assert authenticated.id == user.id

    wrong_password = authenticate_user(email=email, password="wrong-password")
    assert wrong_password is None


def test_update_user_profile_round_trip(db_ready):
    user = create_user(
        name="Profile Tester",
        email=f"profile-{uuid.uuid4()}@example.com",
        password="password",
        phone_number="555-0100",
        role="student",
    )

    updated = update_user_profile(
        user_id=user.id,
        name="Updated Tester",
        phone_number="",
    )

    assert updated is not None
    assert updated.name == "Updated Tester"
    assert updated.phone_number is None


def test_create_user_rejects_duplicate_email(db_ready):
    email = f"dup-{uuid.uuid4()}@example.com"
    create_user(
        name="First User",
        email=email,
        password="password-one",
        role="student",
    )

    with pytest.raises(UserAlreadyExistsError):
        create_user(
            name="Second User",
            email=email,
            password="password-two",
            role="student",
        )


def test_save_resume_persists_json(db_ready):
    user = create_user(
        name="Resume Owner",
        email=f"resume-{uuid.uuid4()}@example.com",
        password="password",
        role="student",
    )
    parsed = {"name": "Jane Doe", "skills": ["Python"]}

    resume = save_resume(
        user_id=user.id,
        original_file_name="resume.pdf",
        file_type="pdf",
        raw_text="Jane Doe\nPython",
        parsed_resume_json=parsed,
    )

    assert resume.user_id == user.id
    assert resume.parsed_resume_json == parsed


def test_interview_report_persistence_and_readback(db_ready):
    user = create_user(
        name="Report Owner",
        email=f"report-{uuid.uuid4()}@example.com",
        password="password",
        role="student",
    )
    resume = save_resume(
        user_id=user.id,
        original_file_name="resume.pdf",
        file_type="pdf",
        raw_text="Jane Doe\nPython",
        parsed_resume_json={"name": "Jane Doe", "skills": ["Python"]},
    )
    jd = save_job_description(
        user_id=user.id,
        original_file_name=None,
        file_type="txt",
        raw_text="Backend engineer with Python.",
        parsed_jd_json={"role": "Backend Engineer", "required_skills": ["Python"]},
    )
    match_result = save_match_result(
        resume_id=resume.id,
        job_description_id=jd.id,
        score=92.5,
        result_json={"score": 92.5, "matched_required": ["Python"]},
    )
    question_set, questions = save_question_set(
        user_id=user.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        match_result_id=match_result.id,
        difficulty="medium",
        questions=[
            {
                "question": "How have you used Python in backend services?",
                "category": "Technical",
                "difficulty": "medium",
                "reason": "Python is required.",
            }
        ],
    )
    interview_session = create_interview_session(
        user_id=user.id,
        question_set_id=question_set.id,
        resume_id=resume.id,
        job_description_id=jd.id,
        role_context="Backend Engineer",
    )
    answer = save_answer(
        interview_session_id=interview_session.id,
        question_id=questions[0].id,
        question_text=questions[0].question_text,
        answer_text="I build APIs with Python.",
        transcript_text=None,
    )
    save_evaluation(
        answer_id=answer.id,
        evaluation_json={
            "overall_score": 84,
            "correctness": 25,
            "keyword_coverage": 20,
            "clarity": 18,
            "communication": 13,
            "completeness": 8,
            "strengths": ["Specific backend example"],
            "improvements": ["Mention testing"],
            "feedback": "Strong answer.",
            "ideal_answer": "Discuss API design, testing, and deployment.",
        },
    )
    complete_interview_session(interview_session.id)
    save_report(
        interview_session_id=interview_session.id,
        overall_score=84,
        summary_json={"average_score": 84, "question_count": 1},
        recommendation="Proceed",
    )

    recent_reports = list_recent_reports(user_id=user.id, limit=1)
    detail = get_report_detail(interview_session_id=interview_session.id)

    assert recent_reports == [
        {
            "interview_session_id": str(interview_session.id),
            "role_context": "Backend Engineer",
            "overall_score": 84,
            "recommendation": "Proceed",
            "created_at": recent_reports[0]["created_at"],
        }
    ]
    assert detail is not None
    assert detail["overall_score"] == 84
    assert detail["recommendation"] == "Proceed"
    assert detail["answers"][0]["question_text"] == questions[0].question_text
    assert detail["answers"][0]["overall_score"] == 84
    assert detail["answers"][0]["strengths"] == ["Specific backend example"]


def test_update_match_result_semantic_merges_into_existing_row(db_ready):
    user = create_user(
        name="Semantic Match Owner",
        email=f"semantic-{uuid.uuid4()}@example.com",
        password="password",
        role="student",
    )
    resume = save_resume(
        user_id=user.id,
        original_file_name="resume.pdf",
        file_type="pdf",
        raw_text="Jane Doe\nPython, Claude AI",
        parsed_resume_json={"name": "Jane Doe", "skills": ["Python", "Claude AI"]},
    )
    jd = save_job_description(
        user_id=user.id,
        original_file_name=None,
        file_type="txt",
        raw_text="GenAI Full Stack Intern.",
        parsed_jd_json={"role": "GenAI Full Stack Intern", "required_skills": ["Prompt Engineering"]},
    )
    match_result = save_match_result(
        resume_id=resume.id,
        job_description_id=jd.id,
        score=42.9,
        result_json={"score": 42.9, "matched_required": []},
    )

    updated = update_match_result_semantic(
        match_result_id=match_result.id,
        semantic_evaluation={
            "overall_score": 85,
            "category_scores": {"Prompt Engineering": 70},
            "reasoning": ["Credited Claude AI experience for Prompt Engineering."],
        },
    )

    assert updated is not None
    assert updated.result_json["score"] == 42.9
    assert updated.result_json["matched_required"] == []
    assert updated.result_json["semantic_evaluation"]["overall_score"] == 85
    assert updated.result_json["semantic_evaluation"]["category_scores"]["Prompt Engineering"] == 70


def test_update_match_result_semantic_returns_none_for_missing_row(db_ready):
    result = update_match_result_semantic(
        match_result_id=uuid.uuid4(),
        semantic_evaluation={"overall_score": 50},
    )

    assert result is None


def test_update_match_result_recruiter_merges_into_existing_row(db_ready):
    user = create_user(
        name="Recruiter Match Owner",
        email=f"recruiter-match-{uuid.uuid4()}@example.com",
        password="password",
        role="recruiter",
    )
    resume = save_resume(
        user_id=user.id,
        original_file_name="resume.pdf",
        file_type="pdf",
        raw_text="John Smith\nExpress.js, Node.js, PostgreSQL",
        parsed_resume_json={"name": "John Smith", "skills": ["Express.js", "Node.js", "PostgreSQL"]},
    )
    jd = save_job_description(
        user_id=user.id,
        original_file_name=None,
        file_type="txt",
        raw_text="Senior Backend Engineer.",
        parsed_jd_json={"role": "Senior Backend Engineer", "required_skills": ["FastAPI"]},
    )
    match_result = save_match_result(
        resume_id=resume.id,
        job_description_id=jd.id,
        score=6.0,
        result_json={"score": 6.0, "matched_required": []},
    )

    updated = update_match_result_recruiter(
        match_result_id=match_result.id,
        recruiter_evaluation={
            "recruiter_match_score": 85,
            "recommendation": "Strong Hire",
            "critical_missing_skills": [],
        },
    )

    assert updated is not None
    assert updated.result_json["score"] == 6.0
    assert updated.result_json["matched_required"] == []
    assert updated.result_json["recruiter_evaluation"]["recruiter_match_score"] == 85
    assert updated.result_json["recruiter_evaluation"]["recommendation"] == "Strong Hire"


def test_update_match_result_recruiter_returns_none_for_missing_row(db_ready):
    result = update_match_result_recruiter(
        match_result_id=uuid.uuid4(),
        recruiter_evaluation={"recruiter_match_score": 50},
    )

    assert result is None


def test_list_recent_candidate_screenings_round_trip(db_ready):
    recruiter = create_user(
        name="Recruiter Owner",
        email=f"recruiter-{uuid.uuid4()}@example.com",
        password="password",
        role="recruiter",
    )
    candidate_resume = save_resume(
        user_id=recruiter.id,
        original_file_name="candidate.pdf",
        file_type="pdf",
        raw_text="Candidate One\nPython, SQL",
        parsed_resume_json={"name": "Candidate One", "skills": ["Python", "SQL"]},
    )
    jd = save_job_description(
        user_id=recruiter.id,
        original_file_name=None,
        file_type="txt",
        raw_text="Backend engineer with Python and SQL.",
        parsed_jd_json={"role": "Backend Engineer", "required_skills": ["Python", "SQL"]},
    )
    save_match_result(
        resume_id=candidate_resume.id,
        job_description_id=jd.id,
        score=88.0,
        result_json={"score": 88.0, "matched_required": ["Python", "SQL"]},
    )

    screenings = list_recent_candidate_screenings(user_id=recruiter.id, limit=5)

    assert screenings == [
        {
            "match_result_id": screenings[0]["match_result_id"],
            "candidate_name": "Candidate One",
            "role_context": "Backend Engineer",
            "score": 88.0,
            "created_at": screenings[0]["created_at"],
        }
    ]
