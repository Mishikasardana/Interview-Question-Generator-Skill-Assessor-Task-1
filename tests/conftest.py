"""Shared pytest fixtures for cross-module and E2E tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def valid_jd_json() -> dict:
    return json.loads((FIXTURES_DIR / "valid_jd.json").read_text(encoding="utf-8"))


@pytest.fixture
def valid_resume_json() -> dict:
    return json.loads((FIXTURES_DIR / "valid_resume.json").read_text(encoding="utf-8"))


@pytest.fixture
def valid_evaluation_json() -> dict:
    return json.loads(
        (FIXTURES_DIR / "valid_evaluation.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def valid_questions_json() -> dict:
    return json.loads(
        (FIXTURES_DIR / "valid_questions.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_jd_text() -> str:
    return (
        "We are hiring a Backend Engineer with Python, SQL, and Docker experience. "
        "Bachelor's degree required."
    )
