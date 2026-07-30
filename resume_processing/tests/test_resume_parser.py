"""Unit tests for resume_parser.py."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from resume_processing.exceptions import ResumeParsingError
from resume_processing.resume_parser import parse_resume_text, strip_markdown_fences

VALID_RESUME_JSON = (
    '{"name": "Jane Doe", "email": "jane@email.com", "phone": "", '
    '"linkedin": "", "github": "", "skills": ["Python"], '
    '"education": [], "experience": [], "projects": [], "certifications": []}'
)


def _mock_response(content: str, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = content
    response.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }

    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=MagicMock(),
            response=response,
        )
    else:
        response.raise_for_status.return_value = None

    return response


@patch("resume_processing.resume_parser.get_glm_api_key", return_value="test-key")
@patch("resume_processing.resume_parser.httpx.post")
def test_parse_resume_text_success(mock_post: MagicMock, _mock_key: MagicMock) -> None:
    mock_post.return_value = _mock_response(VALID_RESUME_JSON)

    result = parse_resume_text("Jane Doe\nPython developer")

    assert '"name": "Jane Doe"' in result
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["model"]
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-key"


@patch("resume_processing.resume_parser.get_glm_api_key", return_value="test-key")
@patch("resume_processing.resume_parser.httpx.post")
def test_parse_resume_text_strips_markdown_fences(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    fenced = f"```json\n{VALID_RESUME_JSON}\n```"
    mock_post.return_value = _mock_response(fenced)

    result = parse_resume_text("Jane Doe")

    assert result.startswith("{")
    assert result.endswith("}")


def test_strip_markdown_fences_plain_json() -> None:
    assert strip_markdown_fences('{"name": "Jane"}') == '{"name": "Jane"}'


def test_strip_markdown_fences_with_fence() -> None:
    raw = '```json\n{"name": "Jane"}\n```'
    assert strip_markdown_fences(raw) == '{"name": "Jane"}'


def test_parse_resume_text_rejects_empty_input() -> None:
    with pytest.raises(ResumeParsingError, match="empty"):
        parse_resume_text("   ")


@patch("resume_processing.resume_parser.get_glm_api_key", return_value="test-key")
@patch("resume_processing.resume_parser.httpx.post")
def test_parse_resume_text_http_error(
    mock_post: MagicMock, _mock_key: MagicMock
) -> None:
    mock_post.return_value = _mock_response("Unauthorized", status_code=401)

    with pytest.raises(ResumeParsingError, match="HTTP 401"):
        parse_resume_text("Jane Doe")
