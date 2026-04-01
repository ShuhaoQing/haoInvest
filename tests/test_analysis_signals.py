"""Tests for signal aggregation."""

from datetime import date, timedelta

from haoinvest.analysis.signals import aggregate_signals
from haoinvest.db import Database
from haoinvest.models import MarketType, PriceBar


def _seed_trend(
    db: Database,
    symbol: str,
    daily_pct: float,
    days: int = 60,
    start_price: float = 100.0,
) -> None:
    """Seed price data with a trend and deterministic noise.

    Adds zig-zag noise so RSI doesn't saturate at 0 or 100 in monotonic series.
    """
    import math

    base_date = date(2025, 1, 1)
    bars = []
    price = start_price
    for i in range(days):
        # Add small zig-zag: ±0.3% alternating noise on top of trend
        noise = 0.003 * math.sin(i * 2.5)
        close = price * (1 + noise)
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=MarketType.A_SHARE,
                trade_date=base_date + timedelta(days=i),
                open=close * 0.998,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=1_000_000.0,
            )
        )
        price *= 1 + daily_pct
    db.save_prices(bars)


class TestSignalAggregation:
    def test_uptrend_ma_bullish(self, db):
        """In an uptrend, MA trend should be bullish."""
        _seed_trend(db, "UP", daily_pct=0.005, days=60)
        result = aggregate_signals(db, "UP", MarketType.A_SHARE)
        # MA is trend-following and should be bullish
        assert any("多头排列" in d for d in result.details)
        assert result.bullish_count + result.bearish_count + result.neutral_count == 4

    def test_downtrend_ma_bearish(self, db):
        """In a downtrend, MA trend should be bearish."""
        _seed_trend(db, "DOWN", daily_pct=-0.005, days=60)
        result = aggregate_signals(db, "DOWN", MarketType.A_SHARE)
        assert any("空头排列" in d for d in result.details)

    def test_trend_vs_mean_reversion_conflict(self, db):
        """Strong trends create natural conflict between trend and mean-reversion indicators."""
        _seed_trend(db, "STRONG", daily_pct=0.01, days=60)
        result = aggregate_signals(db, "STRONG", MarketType.A_SHARE)
        # Both bullish (MA/MACD) and bearish (RSI overbought/BB upper) signals present
        assert result.bullish_count > 0
        assert result.bearish_count > 0

    def test_details_populated(self, db):
        """Details should list per-indicator signals."""
        _seed_trend(db, "TEST", daily_pct=0.005, days=60)
        result = aggregate_signals(db, "TEST", MarketType.A_SHARE)
        assert len(result.details) >= 4  # at least MA, MACD, RSI, Bollinger

    def test_vote_counts_sum(self, db):
        """Bullish + bearish + neutral should equal total indicators (4)."""
        _seed_trend(db, "TEST", daily_pct=0.005, days=60)
        result = aggregate_signals(db, "TEST", MarketType.A_SHARE)
        total = result.bullish_count + result.bearish_count + result.neutral_count
        assert total == 4

    def test_confidence_reflects_agreement(self, db):
        """Confidence should reflect degree of indicator agreement."""
        _seed_trend(db, "UP", daily_pct=0.005, days=60)
        result = aggregate_signals(db, "UP", MarketType.A_SHARE)
        # With 4 indicators, max_votes determines confidence
        max_votes = max(
            result.bullish_count, result.bearish_count, result.neutral_count
        )
        if max_votes >= 4:
            assert result.confidence == "高"
        elif max_votes >= 3:
            assert result.confidence == "中"
        else:
            assert result.confidence == "低"

    def test_insufficient_data(self, db):
        """Should handle insufficient data gracefully."""
        _seed_trend(db, "SHORT", daily_pct=0.01, days=5)
        result = aggregate_signals(db, "SHORT", MarketType.A_SHARE)
        # Should have a message about insufficient data
        assert result.overall_signal == "中性"

    def test_verbose_explanation(self, db):
        """verbose=True should populate explanation."""
        _seed_trend(db, "VERB", daily_pct=0.01, days=60)
        result = aggregate_signals(db, "VERB", MarketType.A_SHARE, verbose=True)
        assert result.explanation is not None
        assert "综合信号" in result.explanation


class TestAggregateSignalsPartialData:
    def test_partial_data_returns_graceful_summary(self, db):
        """With 14–25 days, aggregate_signals returns a summary with no overall signal."""
        base_date = date(2025, 1, 1)
        bars = []
        price = 100.0
        for i in range(22):
            bars.append(
                PriceBar(
                    symbol="TEST",
                    market_type=MarketType.A_SHARE,
                    trade_date=base_date + timedelta(days=i),
                    open=price * 0.998,
                    high=price * 1.01,
                    low=price * 0.99,
                    close=price,
                    volume=1000000.0,
                )
            )
            price *= 1.005
        db.save_prices(bars)
        result = aggregate_signals(db, "TEST", MarketType.A_SHARE)
        # No crash; when tech.message is set, signals.py returns early with no votes
        assert result.symbol == "TEST"
        assert result.details == []
        assert result.bullish_count == 0
        assert result.bearish_count == 0
