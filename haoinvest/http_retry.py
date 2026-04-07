"""Shared retry decorator for external API calls.

Provides exponential backoff with jitter for transient network errors
and server-side failures (5xx). Does NOT retry client errors (4xx).
"""

import logging

import httpx
import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors worth retrying."""
    # Network-level errors (connection refused, DNS failure, timeout)
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True

    # HTTP 5xx server errors
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500

    return False


def _log_retry(retry_state) -> None:
    logger.debug(
        "Retrying %s (attempt %d) after %s",
        retry_state.fn.__name__ if retry_state.fn else "unknown",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome else "unknown",
    )


api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
    before_sleep=_log_retry,
)
