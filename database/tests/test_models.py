"""
Sanity tests for database.models.

These verify every model's CREATE TABLE statement compiles cleanly against
the PostgreSQL dialect (catching type/column typos) without needing a live
database connection. A real PostgreSQL instance was not available in this
environment to run full integration tests against — these tests are the
next best thing: proof the schema itself is well-formed. Before deploying,
run `python -m database.init_db` against a real Postgres instance to create
the tables for real, and exercise database/repositories.py end-to-end.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from database.models import (
    Answer,
    AuthToken,
    Base,
    Evaluation,
    InterviewSession,
    JobDescription,
    MatchResult,
    Question,
    QuestionSet,
    Report,
    Resume,
    User,
)

_ALL_MODELS = [
    User,
    AuthToken,
    Resume,
    JobDescription,
    MatchResult,
    QuestionSet,
    Question,
    InterviewSession,
    Answer,
    Evaluation,
    Report,
]


def test_every_model_table_compiles_for_postgresql():
    dialect = postgresql.dialect()
    for model in _ALL_MODELS:
        sql = str(CreateTable(model.__table__).compile(dialect=dialect))
        assert "CREATE TABLE" in sql
        assert model.__tablename__ in sql


def test_all_models_share_one_metadata_registry():
    # Every model must inherit from the same Base, or init_db()'s
    # Base.metadata.create_all() would silently skip tables.
    for model in _ALL_MODELS:
        assert model.metadata is Base.metadata


def test_expected_tables_are_registered():
    expected_tables = {
        "users", "auth_tokens", "resumes", "job_descriptions", "match_results",
        "question_sets", "questions", "interview_sessions", "answers",
        "evaluations", "reports",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
