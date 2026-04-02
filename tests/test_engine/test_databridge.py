"""Tests for engine.databridge — PriceBar to DataFrame conversion."""

from datetime import date, timedelta

import pandas as pd

from haoinvest.engine.databridge import (
    closes_series,
    daily_returns,
    multi_asset_prices,
    pricebars_to_dataframe,
    safe_float,
)
from haoinvest.models import MarketType, PriceBar


def _make_bars(
    closes: list[float],
    symbol: str = "TEST",
    start: date = date(2025, 1, 1),
) -> list[PriceBar]:
    """Helper to build PriceBar list from close prices."""
    bars = []
    for i, c in enumerate(closes):
        d = start + timedelta(days=i)
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=MarketType.A_SHARE,
                trade_date=d,
                open=c - 0.5,
                high=c + 1.0,
                low=c - 1.0,
                close=c,
                volume=1000.0 * (i + 1),
            )
        )
    return bars


class TestPricebarsToDataframe:
    def test_basic_conversion(self):
        bars = _make_bars([10.0, 11.0, 12.0])
        df = pricebars_to_dataframe(bars)

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 3
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df["close"].iloc[0] == 10.0
        assert df["close"].iloc[-1] == 12.0

    def test_sorted_by_date(self):
        bars = _make_bars([10.0, 11.0, 12.0])
        bars.reverse()
        df = pricebars_to_dataframe(bars)
        assert df.index.is_monotonic_increasing

    def test_drops_none_close(self):
        bars = _make_bars([10.0, 11.0])
        bars[0].close = None
        df = pricebars_to_dataframe(bars)
        assert len(df) == 1

    def test_empty_input(self):
        df = pricebars_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert "close" in df.columns


class TestClosesSeries:
    def test_returns_series(self):
        bars = _make_bars([10.0, 11.0, 12.0])
        s = closes_series(bars)
        assert isinstance(s, pd.Series)
        assert len(s) == 3
        assert s.iloc[-1] == 12.0


class TestDailyReturns:
    def test_returns_pct_change(self):
        bars = _make_bars([100.0, 110.0, 99.0])
        ret = daily_returns(bars)
        assert len(ret) == 2
        assert abs(ret.iloc[0] - 0.10) < 1e-10
        assert abs(ret.iloc[1] - (-0.1)) < 1e-10

    def test_single_bar_returns_empty(self):
        bars = _make_bars([100.0])
        ret = daily_returns(bars)
        assert len(ret) == 0


class TestMultiAssetPrices:
    def test_builds_multi_column_df(self, db):
        bars_a = _make_bars([10.0, 11.0, 12.0], symbol="A")
        bars_b = _make_bars([20.0, 21.0, 22.0], symbol="B")
        db.save_prices(bars_a)
        db.save_prices(bars_b)

        df = multi_asset_prices(
            db,
            [("A", MarketType.A_SHARE), ("B", MarketType.A_SHARE)],
        )
        assert list(df.columns) == ["A", "B"]
        assert len(df) == 3

    def test_inner_join_alignment(self, db):
        bars_a = _make_bars([10.0, 11.0, 12.0], symbol="A")
        # B has only 2 bars (missing first day)
        bars_b = _make_bars([21.0, 22.0], symbol="B", start=date(2025, 1, 2))
        db.save_prices(bars_a)
        db.save_prices(bars_b)

        df = multi_asset_prices(
            db,
            [("A", MarketType.A_SHARE), ("B", MarketType.A_SHARE)],
        )
        assert len(df) == 2

    def test_empty_when_no_data(self, db):
        df = multi_asset_prices(db, [("X", MarketType.A_SHARE)])
        assert len(df) == 0


class TestSafeFloat:
    def test_normal_float(self):
        assert safe_float(3.14) == 3.14

    def test_nan_returns_none(self):
        assert safe_float(float("nan")) is None

    def test_none_returns_none(self):
        assert safe_float(None) is None

    def test_int_converts(self):
        assert safe_float(42) == 42.0

    def test_invalid_returns_none(self):
        assert safe_float("not a number") is None
