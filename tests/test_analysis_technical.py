"""Tests for technical indicators: MA, EMA, MACD, RSI, Bollinger Bands."""

import math
from datetime import date, timedelta

import pytest

from haoinvest.analysis.math_utils import (
    compute_bollinger,
    compute_macd,
    compute_rsi,
    ema,
    sma,
)
from haoinvest.analysis.technical import analyze_technical
from haoinvest.db import Database
from haoinvest.models import MarketType, PriceBar


def _seed_prices(
    db: Database,
    symbol: str = "TEST",
    market_type: MarketType = MarketType.A_SHARE,
    days: int = 60,
    start_price: float = 100.0,
    daily_pct: float = 0.005,
) -> None:
    """Seed deterministic price bars with a fixed daily percentage change."""
    base_date = date(2025, 1, 1)
    bars = []
    price = start_price
    for i in range(days):
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=market_type,
                trade_date=base_date + timedelta(days=i),
                open=price * 0.998,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=1000000.0 + i * 10000,
            )
        )
        price *= 1 + daily_pct
    db.save_prices(bars)


def _seed_downtrend(
    db: Database,
    symbol: str = "DOWN",
    market_type: MarketType = MarketType.A_SHARE,
    days: int = 60,
) -> None:
    """Seed a consistent downtrend."""
    _seed_prices(db, symbol, market_type, days, start_price=200.0, daily_pct=-0.008)


# ---------------------------------------------------------------------------
# Unit tests for pure math helpers
# ---------------------------------------------------------------------------


class TestSMA:
    def test_correct_value(self):
        assert sma([1, 2, 3, 4, 5], 5) == 3.0

    def test_subset(self):
        result = sma([10, 20, 30, 40, 50], 3)
        assert result == pytest.approx(40.0)  # avg of [30, 40, 50]

    def test_insufficient_data(self):
        assert sma([1, 2], 5) is None

    def test_single_period(self):
        assert sma([42.0], 1) == 42.0


class TestEMA:
    def test_constant_values(self):
        """EMA of constant values should equal that constant."""
        result = ema([50.0] * 20, 10)
        assert result == pytest.approx(50.0)

    def test_weights_recent_more(self):
        """EMA should be closer to recent values than SMA when trend accelerates."""
        # Exponentially growing values — recent values much larger
        values = [1.05**i for i in range(40)]
        ema_val = ema(values, 10)
        sma_val = sma(values, 10)
        assert ema_val is not None
        assert sma_val is not None
        # EMA should be higher than SMA in an accelerating uptrend
        assert ema_val > sma_val

    def test_insufficient_data(self):
        assert ema([1, 2, 3], 10) is None


class TestMACD:
    def test_uptrend_positive_macd(self):
        """In a steady uptrend, MACD line should be positive."""
        # Generate 60 prices with upward trend
        closes = [100.0 * (1.005**i) for i in range(60)]
        macd_line, signal_line, histogram = compute_macd(closes)
        assert macd_line is not None
        assert macd_line > 0

    def test_downtrend_negative_macd(self):
        """In a steady downtrend, MACD line should be negative."""
        closes = [200.0 * (0.995**i) for i in range(60)]
        macd_line, _, _ = compute_macd(closes)
        assert macd_line is not None
        assert macd_line < 0

    def test_insufficient_data(self):
        closes = [100.0] * 20
        macd_line, signal_line, histogram = compute_macd(closes)
        assert macd_line is None
        assert signal_line is None
        assert histogram is None

    def test_signal_line_computed(self):
        """With enough data, signal line should be present."""
        closes = [100.0 * (1.003**i) for i in range(60)]
        _, signal_line, histogram = compute_macd(closes)
        assert signal_line is not None
        assert histogram is not None


class TestRSI:
    def test_strong_uptrend_high_rsi(self):
        """Strong uptrend should have RSI > 50."""
        closes = [100.0 * (1.02**i) for i in range(30)]
        rsi = compute_rsi(closes)
        assert rsi is not None
        assert rsi > 50

    def test_strong_downtrend_low_rsi(self):
        """Strong downtrend should have RSI < 50."""
        closes = [200.0 * (0.98**i) for i in range(30)]
        rsi = compute_rsi(closes)
        assert rsi is not None
        assert rsi < 50

    def test_range(self):
        """RSI should always be between 0 and 100."""
        closes = [100.0 + math.sin(i * 0.3) * 20 for i in range(50)]
        rsi = compute_rsi(closes)
        assert rsi is not None
        assert 0 <= rsi <= 100

    def test_insufficient_data(self):
        assert compute_rsi([100, 101, 102], 14) is None

    def test_all_gains(self):
        """All gains should give RSI = 100."""
        closes = [100.0 + i for i in range(20)]
        rsi = compute_rsi(closes)
        assert rsi == pytest.approx(100.0)


class TestBollinger:
    def test_symmetry(self):
        """Upper and lower bands equidistant from middle."""
        closes = [100.0 + math.sin(i * 0.5) * 5 for i in range(30)]
        upper, middle, lower = compute_bollinger(closes)
        assert upper is not None and middle is not None and lower is not None
        assert pytest.approx(upper - middle, abs=1e-10) == middle - lower

    def test_constant_prices(self):
        """Constant prices should give zero bandwidth (bands collapse to middle)."""
        closes = [50.0] * 25
        upper, middle, lower = compute_bollinger(closes)
        assert upper == middle == lower == 50.0

    def test_insufficient_data(self):
        upper, middle, lower = compute_bollinger([100.0] * 10, period=20)
        assert upper is None
        assert middle is None
        assert lower is None


# ---------------------------------------------------------------------------
# Integration tests for analyze_technical
# ---------------------------------------------------------------------------


class TestAnalyzeTechnical:
    def test_full_analysis(self, db):
        """End-to-end test with sufficient data."""
        _seed_prices(db, days=60)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is None
        assert result.latest_close is not None
        assert result.moving_averages.sma_20 is not None
        assert result.macd.macd_line is not None
        assert result.rsi.rsi is not None
        assert result.bollinger.upper is not None

    def test_insufficient_data(self, db):
        """Should return gracefully with message when not enough data."""
        _seed_prices(db, days=5)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is not None
        assert "Not enough" in result.message

    def test_uptrend_signals(self, db):
        """Uptrend should show positive indicators."""
        _seed_prices(db, days=60, daily_pct=0.01)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.moving_averages.trend == "上升趋势"
        assert result.macd.macd_line > 0

    def test_downtrend_signals(self, db):
        """Downtrend should show negative indicators."""
        _seed_downtrend(db, symbol="DOWN", days=60)
        result = analyze_technical(db, "DOWN", MarketType.A_SHARE)
        assert result.moving_averages.trend == "下降趋势"
        assert result.macd.macd_line < 0

    def test_verbose_adds_explanations(self, db):
        """verbose=True should populate explanation fields."""
        _seed_prices(db, days=60)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE, verbose=True)
        assert result.moving_averages.explanation is not None
        assert result.rsi.explanation is not None

    def test_partial_data_warning_14_to_19_days(self, db):
        """17 days (14–19 range): RSI available (needs 15+), MACD and Bollinger not — should warn about both."""
        _seed_prices(db, days=17)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is not None
        assert "MACD" in result.message
        assert "布林带" in result.message
        # RSI is still computed
        assert result.rsi.rsi is not None

    def test_partial_data_warning_20_to_25_days(self, db):
        """20–25 days: RSI and Bollinger available, MACD not — should warn about MACD only."""
        _seed_prices(db, days=22)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is not None
        assert "MACD" in result.message
        assert "布林带" not in result.message
        # Bollinger is computed
        assert result.bollinger.upper is not None

    def test_no_warning_with_sufficient_data(self, db):
        """26+ days: all indicators available — message should be None."""
        _seed_prices(db, days=60)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is None

    def test_math_helpers_not_in_technical_namespace(self):
        """Math helpers should live in math_utils, not technical."""
        import haoinvest.analysis.technical as t

        assert not hasattr(t, "_sma")
        assert not hasattr(t, "_ema")
        assert not hasattr(t, "_compute_macd")
        assert not hasattr(t, "_compute_rsi")
        assert not hasattr(t, "_compute_bollinger")
