"""Tests for currency conversion."""

from unittest.mock import patch

import pytest

from haoinvest.fx import convert


# --- Unit tests (no network) ---


def test_same_currency():
    assert convert(100.0, "CNY", "CNY") == 100.0


def test_usd_to_cny_fallback():
    """Uses fallback rate when live API fails."""
    with patch("haoinvest.fx._fetch_live_rate", side_effect=Exception("no network")):
        result = convert(100.0, "USD", "CNY")
        assert result == 725.0  # fallback rate 7.25


def test_usdt_to_cny_fallback():
    with patch("haoinvest.fx._fetch_live_rate", side_effect=Exception("no network")):
        result = convert(1.0, "USDT", "CNY")
        assert result == 7.25


def test_case_insensitive():
    with patch("haoinvest.fx._fetch_live_rate", side_effect=Exception("no network")):
        result = convert(100.0, "usd", "cny")
        assert result == 725.0


def test_unknown_currency_raises():
    with pytest.raises(ValueError, match="No exchange rate"):
        convert(100.0, "XYZ", "ABC")


# --- Integration tests (call real API) ---


@pytest.mark.integration
def test_usd_to_cny_live():
    result = convert(100.0, "USD", "CNY")
    assert 600 < result < 900


@pytest.mark.integration
def test_usdt_to_cny_live():
    result = convert(1.0, "USDT", "CNY")
    assert 6.0 < result < 9.0
