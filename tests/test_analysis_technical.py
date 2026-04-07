"""Tests for technical indicators via analyze_technical (adapter) and compute_technical (engine)."""

from datetime import date, timedelta

from haoinvest.analysis.technical import analyze_technical, analyze_technical_multi
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
        """17 days (14-19 range): RSI available, MACD and Bollinger not."""
        _seed_prices(db, days=17)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is not None
        assert "MACD" in result.message
        assert "布林带" in result.message
        assert result.rsi.rsi is not None

    def test_partial_data_warning_20_to_25_days(self, db):
        """20-25 days: RSI and Bollinger available, MACD not."""
        _seed_prices(db, days=22)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is not None
        assert "MACD" in result.message
        assert "布林带" not in result.message
        assert result.bollinger.upper is not None

    def test_no_warning_with_sufficient_data(self, db):
        """26+ days: all indicators available."""
        _seed_prices(db, days=60)
        result = analyze_technical(db, "TEST", MarketType.A_SHARE)
        assert result.message is None

    def test_math_helpers_not_in_technical_namespace(self):
        """Math helpers should not be in the technical module namespace."""
        import haoinvest.analysis.technical as t

        assert not hasattr(t, "_sma")
        assert not hasattr(t, "_ema")
        assert not hasattr(t, "_compute_macd")
        assert not hasattr(t, "_compute_rsi")
        assert not hasattr(t, "_compute_bollinger")


# ---------------------------------------------------------------------------
# Multi-timeframe analysis tests
# ---------------------------------------------------------------------------


class TestAnalyzeTechnicalMulti:
    def test_all_timeframes_with_sufficient_data(self, db):
        """2 years of data → daily/weekly/monthly all populated."""
        _seed_prices(db, days=730, daily_pct=0.002)
        result = analyze_technical_multi(db, "TEST", MarketType.A_SHARE)
        assert result.symbol == "TEST"
        assert result.daily.timeframe == "daily"
        assert result.weekly.timeframe == "weekly"
        assert result.monthly.timeframe == "monthly"
        # Daily should have full indicators
        assert result.daily.message is None
        assert result.daily.moving_averages.sma_20 is not None
        # Weekly should have indicators (730 days ≈ 104 weeks)
        assert result.weekly.moving_averages.sma_20 is not None
        assert result.weekly.macd.macd_line is not None
        # Monthly should have indicators (730 days ≈ 24 months)
        assert result.monthly.moving_averages.sma_20 is not None

    def test_short_data_monthly_insufficient(self, db):
        """30 days → daily OK, weekly may have limited data, monthly insufficient."""
        _seed_prices(db, days=30)
        result = analyze_technical_multi(db, "TEST", MarketType.A_SHARE)
        assert result.daily.message is None or "Not enough" not in (result.daily.message or "")
        # Monthly: 30 days = ~1 month bar, way under 14
        assert result.monthly.message is not None
        assert "Not enough" in result.monthly.message

    def test_timeframe_labels_correct(self, db):
        """Verify timeframe field is set correctly on each result."""
        _seed_prices(db, days=60)
        result = analyze_technical_multi(db, "TEST", MarketType.A_SHARE)
        assert result.daily.timeframe == "daily"
        assert result.weekly.timeframe == "weekly"
        assert result.monthly.timeframe == "monthly"
