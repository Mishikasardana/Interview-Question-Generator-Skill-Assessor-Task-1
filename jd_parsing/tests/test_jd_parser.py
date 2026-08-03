"""Tests for jd_parsing.jd_parser — GLM call layer (mocked, no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from jd_parsing.exceptions import JDParsingError
from jd_parsing.jd_parser import parse_jd_text

VALID_JD_JSON = json.dumps(
    {
        "role": "Backend Engineer",
        "required_skills": ["Python"],
        "preferred_skills": [],
        "responsibilities": [],
        "experience_level": "",
        "education_requirement": "",
    }
)


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = content
    response.json.return_value = {"choices": [{"message": {"content": content}}]}

    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=MagicMock(),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None

    return response


def test_parse_jd_text_rejects_empty_string():
    with pytest.raises(JDParsingError, match="empty"):
        parse_jd_text("   ")


def test_parse_jd_text_rejects_non_string_input():
    with pytest.raises(JDParsingError, match="Expected str"):
        parse_jd_text(None)  # type: ignore[arg-type]


@patch("jd_parsing.jd_parser.get_glm_api_key", return_value="test-key")
@patch("jd_parsing.jd_parser.httpx.post")
def test_parse_jd_text_success(mock_post: MagicMock, _mock_key: MagicMock):
    mock_post.return_value = _mock_response(VALID_JD_JSON)

    result = parse_jd_text("We are hiring a backend engineer.")

    assert result == VALID_JD_JSON
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


@patch("jd_parsing.jd_parser.get_glm_api_key", return_value="test-key")
@patch("jd_parsing.jd_parser.httpx.post")
def test_parse_jd_text_strict_mode_appends_instruction(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response(VALID_JD_JSON)

    parse_jd_text("JD text", strict=True)

    system_message = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "Return ONLY valid JSON" in system_message


@patch("jd_parsing.jd_parser.get_glm_api_key", return_value="test-key")
@patch("jd_parsing.jd_parser.httpx.post")
def test_parse_jd_text_raises_on_http_error(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response("Unauthorized", status_code=401)

    with pytest.raises(JDParsingError, match="HTTP 401"):
        parse_jd_text("We are hiring.")


@patch("jd_parsing.jd_parser.get_glm_api_key", return_value="test-key")
@patch("jd_parsing.jd_parser.httpx.post")
def test_parse_jd_text_raises_on_empty_model_content(
    mock_post: MagicMock, _mock_key: MagicMock
):
    mock_post.return_value = _mock_response("   ")

    with pytest.raises(JDParsingError, match="empty content"):
        parse_jd_text("We are hiring.")


@patch("jd_parsing.jd_parser.get_glm_api_key", return_value="test-key")
@patch("jd_parsing.jd_parser.httpx.post")
def test_parse_jd_text_raises_on_unexpected_response_shape(
    mock_post: MagicMock, _mock_key: MagicMock
):
    response = MagicMock()
    response.status_code = 200
    response.text = '{"unexpected": true}'
    response.json.return_value = {"unexpected": True}
    response.raise_for_status.return_value = None
    mock_post.return_value = response

    with pytest.raises(JDParsingError, match="Unexpected GLM API response"):
        parse_jd_text("We are hiring.")
