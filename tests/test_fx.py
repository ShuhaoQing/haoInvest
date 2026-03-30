"""Tests for currency conversion."""

from haoinvest.fx import convert
import pytest


def test_same_currency():
    assert convert(100.0, "CNY", "CNY") == 100.0


def test_usd_to_cny():
    result = convert(100.0, "USD", "CNY")
    assert result > 700  # Roughly 7.25x
    assert result < 800


def test_usdt_to_cny():
    result = convert(1.0, "USDT", "CNY")
    assert result > 7.0
    assert result < 8.0


def test_case_insensitive():
    result = convert(100.0, "usd", "cny")
    assert result > 700


def test_unknown_currency_raises():
    with pytest.raises(ValueError, match="No exchange rate"):
        convert(100.0, "XYZ", "ABC")
