"""
Shared HTTP retry helper for GLM API calls.

Every module that calls the GLM chat completions API (jd_parsing,
resume_processing, answer_evaluation, question_generation,
semantic_matching, recruiter_intelligence) previously called ``httpx.post``
directly with no retry — a single transient failure (rate limit, momentary
server error) immediately surfaced as a raised exception. This is a real,
reproduced gap: the benchmark harness hit a real HTTP 429 after 46
consecutive calls (see ``tests/benchmark/README.md``), and a user hit the
same thing during normal use.

``post_with_retry`` is a drop-in replacement for the
``response = httpx.post(...); response.raise_for_status()`` pattern every
module already uses: same inputs, same successful return value, same
exceptions (``httpx.HTTPStatusError`` / ``httpx.HTTPError``) once retries are
exhausted — so no caller's ``except`` clause needs to change, only the one
line that made the call.

Deliberately narrow in scope: only HTTP 429 (rate limit) and 5xx (transient
server error) responses are retried. A connection-level failure (timeout,
DNS, connection refused) is NOT retried here and propagates immediately —
retrying an already-slow/hung connection is likely to repeat the same
slowness rather than help, and this codebase's GLM timeout is already 120
seconds per attempt, so stacking retries on top of that would turn an
already-slow failure into what feels like a hang instead of a fast, clear
error. A 4xx status other than 429 (400, 401, 404, ...) is never retried
either, since those are never going to succeed on a retry.
"""

from __future__ import annotations

import random
import time

import httpx

MAX_ATTEMPTS = 4
_BASE_DELAY_SECONDS = 5.0
_BACKOFF_MULTIPLIER = 3.0
_MAX_DELAY_SECONDS = 60.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _retry_delay_seconds(attempt: int, response: httpx.Response) -> float:
    """
    Honor a ``Retry-After`` header if the API sent one, in the plain-seconds
    form (an HTTP-date form falls back to computed backoff — providers
    rarely send that form for a chat-completions rate limit, and parsing it
    isn't worth the complexity). Otherwise exponential backoff with jitter:
    5s, 15s, 45s, capped at 60s.
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass  # not a plain seconds value -- fall through to backoff

    delay = min(_BASE_DELAY_SECONDS * (_BACKOFF_MULTIPLIER ** attempt), _MAX_DELAY_SECONDS)
    return delay + random.uniform(0, delay * 0.25)


def post_with_retry(
    url: str, *, headers: dict, json: dict, timeout: float,
    max_attempts: int = MAX_ATTEMPTS,
) -> httpx.Response:
    """
    POST with retry-on-transient-failure (rate limit, server error).

    Returns the successful ``httpx.Response`` (status 2xx). Raises
    ``httpx.HTTPStatusError`` if the final attempt still failed with a
    non-2xx status, or lets a connection-level ``httpx.HTTPError`` propagate
    immediately (never retried) — exactly what a plain
    ``httpx.post(...); response.raise_for_status()`` call would raise, so
    every existing caller's except-clause handling keeps working unchanged.
    """
    for attempt in range(max_attempts):
        response = httpx.post(url, headers=headers, json=json, timeout=timeout)

        is_last_attempt = attempt == max_attempts - 1
        if response.status_code in _RETRYABLE_STATUS_CODES and not is_last_attempt:
            time.sleep(_retry_delay_seconds(attempt, response))
            continue

        response.raise_for_status()
        return response

    raise AssertionError("unreachable: the loop above always returns or raises")
