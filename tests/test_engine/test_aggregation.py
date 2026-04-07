"""Tests for daily → weekly/monthly price bar aggregation."""

from datetime import date

from haoinvest.engine.aggregation import aggregate_to_monthly, aggregate_to_weekly
from haoinvest.models import MarketType, PriceBar


def _bar(
    trade_date: str, o: float, h: float, low: float, c: float, v: float
) -> PriceBar:
    """Helper to create a PriceBar with defaults."""
    return PriceBar(
        symbol="600519",
        market_type=MarketType.A_SHARE,
        trade_date=date.fromisoformat(trade_date),
        open=o,
        high=h,
        low=low,
        close=c,
        volume=v,
    )


# --- Weekly aggregation ---


class TestAggregateToWeekly:
    def test_two_weeks(self):
        """10 trading days spanning 2 ISO weeks → 2 weekly bars."""
        # Week 1: 2026-03-30 (Mon) to 2026-04-03 (Fri)
        # Week 2: 2026-04-06 (Mon) to 2026-04-10 (Fri) — but only 4 days here
        bars = [
            _bar("2026-03-30", 100, 105, 98, 102, 1000),
            _bar("2026-03-31", 102, 108, 101, 107, 1200),
            _bar("2026-04-01", 107, 110, 106, 109, 1100),
            _bar("2026-04-02", 109, 112, 108, 111, 900),
            _bar("2026-04-03", 111, 115, 110, 113, 1300),
            _bar("2026-04-06", 113, 116, 112, 114, 800),
            _bar("2026-04-07", 114, 118, 113, 117, 1500),
            _bar("2026-04-08", 117, 120, 115, 119, 1000),
            _bar("2026-04-09", 119, 121, 118, 120, 1100),
        ]
        result = aggregate_to_weekly(bars)
        assert len(result) == 2

        w1, w2 = result
        # Week 1
        assert w1.trade_date == date(2026, 4, 3)  # last trading day
        assert w1.open == 100
        assert w1.high == 115
        assert w1.low == 98
        assert w1.close == 113
        assert w1.volume == 5500

        # Week 2
        assert w2.trade_date == date(2026, 4, 9)
        assert w2.open == 113
        assert w2.high == 121
        assert w2.low == 112
        assert w2.close == 120
        assert w2.volume == 4400

    def test_empty_input(self):
        assert aggregate_to_weekly([]) == []

    def test_single_bar(self):
        bars = [_bar("2026-04-01", 100, 105, 95, 102, 500)]
        result = aggregate_to_weekly(bars)
        assert len(result) == 1
        assert result[0].open == 100
        assert result[0].close == 102

    def test_unsorted_input(self):
        """Bars passed out of order should still aggregate correctly."""
        bars = [
            _bar("2026-04-02", 109, 112, 108, 111, 900),
            _bar("2026-04-01", 107, 110, 106, 109, 1100),
        ]
        result = aggregate_to_weekly(bars)
        assert len(result) == 1
        assert result[0].open == 107  # first by date
        assert result[0].close == 111  # last by date

    def test_iso_week_year_boundary(self):
        """Dec 29, 2025 (Mon) and Jan 2, 2026 (Fri) are in ISO week 2026-W01."""
        bars = [
            _bar("2025-12-29", 50, 55, 48, 52, 100),
            _bar("2025-12-30", 52, 56, 51, 54, 200),
            _bar("2026-01-02", 54, 58, 53, 57, 300),
        ]
        result = aggregate_to_weekly(bars)
        # All three should be in the same ISO week
        assert len(result) == 1
        assert result[0].open == 50
        assert result[0].close == 57
        assert result[0].volume == 600


# --- Monthly aggregation ---


class TestAggregateToMonthly:
    def test_two_months(self):
        """Bars spanning March and April → 2 monthly bars."""
        bars = [
            _bar("2026-03-30", 100, 105, 98, 102, 1000),
            _bar("2026-03-31", 102, 108, 101, 107, 1200),
            _bar("2026-04-01", 107, 110, 106, 109, 1100),
            _bar("2026-04-02", 109, 112, 108, 111, 900),
            _bar("2026-04-03", 111, 115, 110, 113, 1300),
        ]
        result = aggregate_to_monthly(bars)
        assert len(result) == 2

        m1, m2 = result
        assert m1.trade_date == date(2026, 3, 31)
        assert m1.open == 100
        assert m1.high == 108
        assert m1.low == 98
        assert m1.close == 107
        assert m1.volume == 2200

        assert m2.trade_date == date(2026, 4, 3)
        assert m2.open == 107
        assert m2.close == 113
        assert m2.volume == 3300

    def test_empty_input(self):
        assert aggregate_to_monthly([]) == []


# --- None handling ---


class TestNoneHandling:
    def test_none_volume(self):
        bars = [
            _bar("2026-04-01", 100, 105, 95, 102, 500),
            PriceBar(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 4, 2),
                open=102,
                high=108,
                low=100,
                close=106,
                volume=None,
            ),
        ]
        result = aggregate_to_weekly(bars)
        assert len(result) == 1
        assert result[0].volume == 500  # only non-None volume summed

    def test_all_none_high_low(self):
        bars = [
            PriceBar(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 4, 1),
                open=100,
                high=None,
                low=None,
                close=102,
                volume=None,
            ),
        ]
        result = aggregate_to_weekly(bars)
        assert len(result) == 1
        assert result[0].high is None
        assert result[0].low is None
        assert result[0].volume is None
