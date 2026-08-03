"""Tests for glm_http.post_with_retry — mocked httpx.post and time.sleep, no real network, no real waiting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from glm_http import post_with_retry


def _mock_response(status_code: int, headers: dict | None = None) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.text = f"status {status_code}"

    def _raise_for_status():
        if status_code >= 400:
            request = httpx.Request("POST", "https://example/api")
            raise httpx.HTTPStatusError(
                f"HTTP {status_code}", request=request,
                response=httpx.Response(status_code, request=request, text=response.text),
            )

    response.raise_for_status.side_effect = _raise_for_status
    return response


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_returns_immediately_on_success(mock_post, mock_sleep):
    mock_post.return_value = _mock_response(200)

    response = post_with_retry(
        "https://example/api", headers={}, json={}, timeout=10.0,
    )

    assert response.status_code == 200
    mock_post.assert_called_once()
    mock_sleep.assert_not_called()


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_retries_on_429_then_succeeds(mock_post, mock_sleep):
    mock_post.side_effect = [_mock_response(429), _mock_response(200)]

    response = post_with_retry(
        "https://example/api", headers={}, json={}, timeout=10.0,
    )

    assert response.status_code == 200
    assert mock_post.call_count == 2
    mock_sleep.assert_called_once()


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_retries_on_5xx(mock_post, mock_sleep):
    mock_post.side_effect = [_mock_response(503), _mock_response(200)]

    response = post_with_retry(
        "https://example/api", headers={}, json={}, timeout=10.0,
    )

    assert response.status_code == 200
    assert mock_post.call_count == 2


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_raises_after_exhausting_attempts(mock_post, mock_sleep):
    mock_post.return_value = _mock_response(429)

    with pytest.raises(httpx.HTTPStatusError):
        post_with_retry("https://example/api", headers={}, json={}, timeout=10.0, max_attempts=3)

    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2  # sleeps between attempts, not after the last one


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_does_not_retry_non_retryable_status(mock_post, mock_sleep):
    mock_post.return_value = _mock_response(401)

    with pytest.raises(httpx.HTTPStatusError):
        post_with_retry("https://example/api", headers={}, json={}, timeout=10.0)

    mock_post.assert_called_once()
    mock_sleep.assert_not_called()


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_honors_retry_after_header(mock_post, mock_sleep):
    mock_post.side_effect = [_mock_response(429, headers={"Retry-After": "7"}), _mock_response(200)]

    post_with_retry("https://example/api", headers={}, json={}, timeout=10.0)

    mock_sleep.assert_called_once_with(7.0)


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_falls_back_to_backoff_when_retry_after_unparseable(mock_post, mock_sleep):
    mock_post.side_effect = [
        _mock_response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        _mock_response(200),
    ]

    post_with_retry("https://example/api", headers={}, json={}, timeout=10.0)

    mock_sleep.assert_called_once()
    slept_seconds = mock_sleep.call_args.args[0]
    assert slept_seconds > 0  # computed backoff, not the unparsed header value


@patch("glm_http.time.sleep")
@patch("glm_http.httpx.post")
def test_post_with_retry_connection_error_propagates_immediately(mock_post, mock_sleep):
    request = httpx.Request("POST", "https://example/api")
    mock_post.side_effect = httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(httpx.ConnectTimeout):
        post_with_retry("https://example/api", headers={}, json={}, timeout=10.0)

    mock_post.assert_called_once()
    mock_sleep.assert_not_called()
