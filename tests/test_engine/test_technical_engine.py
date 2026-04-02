"""Tests for engine.technical_engine — pandas-ta based indicator computation."""

import math
from datetime import date, timedelta

import pandas as pd

from haoinvest.engine.technical_engine import compute_technical


def _make_ohlcv_df(
    closes: list[float],
    start: date = date(2025, 1, 1),
) -> pd.DataFrame:
    """Build an OHLCV DataFrame from close prices."""
    records = []
    for i, c in enumerate(closes):
        records.append(
            {
                "date": pd.Timestamp(start + timedelta(days=i)),
                "open": c * 0.998,
                "high": c * 1.01,
                "low": c * 0.99,
                "close": c,
                "volume": 1000000.0 + i * 10000,
            }
        )
    return pd.DataFrame(records).set_index("date")


class TestComputeTechnical:
    def test_full_indicators_with_60_days(self):
        """60 days of uptrend data should produce all indicators."""
        closes = [100.0 * (1.005**i) for i in range(60)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        assert result.latest_close is not None
        assert result.moving_averages.sma_5 is not None
        assert result.moving_averages.sma_20 is not None
        assert result.moving_averages.sma_60 is not None
        assert result.moving_averages.ema_12 is not None
        assert result.macd.macd_line is not None
        assert result.macd.signal_line is not None
        assert result.macd.histogram is not None
        assert result.rsi.rsi is not None
        assert result.bollinger.upper is not None
        assert result.message is None

    def test_uptrend_detection(self):
        closes = [100.0 * (1.01**i) for i in range(60)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        assert result.moving_averages.trend == "上升趋势"
        assert result.macd.macd_line > 0
        assert result.macd.signal == "金叉"

    def test_downtrend_detection(self):
        closes = [200.0 * (0.99**i) for i in range(60)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        assert result.moving_averages.trend == "下降趋势"
        assert result.macd.macd_line < 0
        # Histogram sign depends on MACD vs signal line convergence,
        # not trend direction alone — only assert MACD line is negative

    def test_rsi_range(self):
        closes = [100.0 + math.sin(i * 0.3) * 20 for i in range(50)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        assert result.rsi.rsi is not None
        assert 0 <= result.rsi.rsi <= 100

    def test_rsi_strong_uptrend(self):
        closes = [100.0 * (1.02**i) for i in range(30)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)
        assert result.rsi.rsi > 50

    def test_bollinger_symmetry(self):
        closes = [100.0 + math.sin(i * 0.5) * 5 for i in range(30)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        bb = result.bollinger
        assert bb.upper is not None and bb.middle is not None and bb.lower is not None
        assert abs((bb.upper - bb.middle) - (bb.middle - bb.lower)) < 0.01

    def test_insufficient_data_macd(self):
        """17 days: RSI available but MACD not."""
        closes = [100.0 * (1.005**i) for i in range(17)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)

        assert result.rsi.rsi is not None
        assert result.macd.macd_line is None
        assert result.message is not None
        assert "MACD" in result.message

    def test_verbose_mode(self):
        closes = [100.0 * (1.005**i) for i in range(60)]
        df = _make_ohlcv_df(closes)
        result = compute_technical(df, verbose=True)

        assert result.moving_averages.explanation is not None
        assert result.rsi.explanation is not None

    def test_symbol_and_market_type_are_empty(self):
        """Engine returns empty strings; adapter fills them in."""
        closes = [100.0] * 20
        df = _make_ohlcv_df(closes)
        result = compute_technical(df)
        assert result.symbol == ""
        assert result.market_type == ""
