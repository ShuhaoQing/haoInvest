"""Tests for market source common utilities — prefix routing."""

import pytest

from haoinvest.market.sources._common import (
    exchange_prefix,
    market_prefix,
)


class TestMarketPrefix:
    """Verify symbol-to-exchange prefix routing."""

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            # Shanghai main board
            ("600519", "sh"),
            ("601877", "sh"),
            # Shanghai STAR board
            ("688001", "sh"),
            # Shanghai ETF (51xxxx)
            ("511360", "sh"),
            ("513130", "sh"),
            ("518880", "sh"),
            # Cross-market ETF (56xxxx) — must route via sh
            ("563020", "sh"),
            ("560010", "sh"),
            # Shenzhen main board
            ("000001", "sz"),
            ("000988", "sz"),
            # Shenzhen SME
            ("002001", "sz"),
            ("002463", "sz"),
            # Shenzhen ChiNext
            ("300750", "sz"),
            # Shanghai B-share
            ("900001", "sh"),
            # Shenzhen ETF (15xxxx)
            ("159915", "sz"),
        ],
    )
    def test_market_prefix(self, symbol: str, expected: str) -> None:
        assert market_prefix(symbol) == expected


class TestExchangePrefix:
    """Verify eastmoney exchange prefix mapping."""

    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("600519", "SH"),
            ("563020", "SH"),
            ("518880", "SH"),
            ("000988", "SZ"),
            ("002463", "SZ"),
        ],
    )
    def test_exchange_prefix(self, symbol: str, expected: str) -> None:
        assert exchange_prefix(symbol) == expected
