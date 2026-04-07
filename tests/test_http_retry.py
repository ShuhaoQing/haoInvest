"""Tests for the http_retry module."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests

from haoinvest.http_retry import _is_retryable, api_retry


class TestIsRetryable:
    """Test the _is_retryable predicate."""

    def test_requests_connection_error(self):
        assert _is_retryable(requests.ConnectionError()) is True

    def test_requests_timeout(self):
        assert _is_retryable(requests.Timeout()) is True

    def test_httpx_connect_error(self):
        assert _is_retryable(httpx.ConnectError("fail")) is True

    def test_httpx_timeout(self):
        assert _is_retryable(httpx.ReadTimeout("timeout")) is True

    def test_requests_500_error(self):
        resp = MagicMock()
        resp.status_code = 500
        exc = requests.HTTPError(response=resp)
        assert _is_retryable(exc) is True

    def test_requests_503_error(self):
        resp = MagicMock()
        resp.status_code = 503
        exc = requests.HTTPError(response=resp)
        assert _is_retryable(exc) is True

    def test_requests_400_not_retryable(self):
        resp = MagicMock()
        resp.status_code = 400
        exc = requests.HTTPError(response=resp)
        assert _is_retryable(exc) is False

    def test_requests_404_not_retryable(self):
        resp = MagicMock()
        resp.status_code = 404
        exc = requests.HTTPError(response=resp)
        assert _is_retryable(exc) is False

    def test_httpx_500_error(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        exc = httpx.HTTPStatusError("500", request=request, response=response)
        assert _is_retryable(exc) is True

    def test_httpx_404_not_retryable(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        exc = httpx.HTTPStatusError("404", request=request, response=response)
        assert _is_retryable(exc) is False

    def test_value_error_not_retryable(self):
        assert _is_retryable(ValueError("bad data")) is False

    def test_runtime_error_not_retryable(self):
        assert _is_retryable(RuntimeError("unexpected")) is False


class TestApiRetry:
    """Test the api_retry decorator behavior."""

    @patch("haoinvest.http_retry._log_retry")
    def test_retries_on_connection_error_then_succeeds(self, mock_log):
        call_count = 0

        @api_retry
        def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests.ConnectionError("connection refused")
            return "success"

        result = flaky_call()
        assert result == "success"
        assert call_count == 3

    def test_no_retry_on_value_error(self):
        call_count = 0

        @api_retry
        def bad_call():
            nonlocal call_count
            call_count += 1
            raise ValueError("not found")

        with pytest.raises(ValueError, match="not found"):
            bad_call()
        assert call_count == 1

    @patch("haoinvest.http_retry._log_retry")
    def test_gives_up_after_max_attempts(self, mock_log):
        call_count = 0

        @api_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise requests.ConnectionError("always down")

        with pytest.raises(requests.ConnectionError):
            always_fails()
        assert call_count == 3
