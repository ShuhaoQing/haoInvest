"""Tests for guardrails alerts system."""

from datetime import date, datetime, timedelta

import pytest

from haoinvest.db import Database
from haoinvest.guardrails.alerts import get_recent_price_change, scan_alerts
from haoinvest.models import (
    AlertType,
    DecisionType,
    Emotion,
    JournalEntry,
    MarketType,
    Position,
    PriceBar,
)


def _add_position(db: Database, symbol: str, qty: float, avg_cost: float) -> None:
    db.upsert_position(
        Position(symbol=symbol, market_type=MarketType.A_SHARE, cached_quantity=qty, cached_avg_cost=avg_cost)
    )


def _add_price_bars(db: Database, symbol: str, prices: list[tuple[date, float]]) -> None:
    bars = [
        PriceBar(symbol=symbol, market_type=MarketType.A_SHARE, trade_date=d, close=p)
        for d, p in prices
    ]
    db.save_prices(bars)


class TestScanAlerts:
    def test_gain_threshold_alert(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1400.0}  # +40%
        alerts = scan_alerts(db, prices)
        gain_alerts = [a for a in alerts if a.alert_type == AlertType.GAIN_REVIEW]
        assert len(gain_alerts) == 1
        assert gain_alerts[0].current_pnl_pct == 40.0
        assert "浮盈" in gain_alerts[0].message

    def test_loss_threshold_alert(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 850.0}  # -15%
        alerts = scan_alerts(db, prices)
        loss_alerts = [a for a in alerts if a.alert_type == AlertType.LOSS_REVIEW]
        assert len(loss_alerts) == 1
        assert loss_alerts[0].current_pnl_pct == -15.0

    def test_rapid_change_alert(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        today = date.today()
        # Price 7 days ago was 900, now 1020 → ~13.3% weekly change
        _add_price_bars(db, "600519", [
            (today - timedelta(days=10), 900.0),
            (today - timedelta(days=7), 900.0),
            (today - timedelta(days=3), 950.0),
            (today, 1020.0),
        ])
        prices = {("600519", MarketType.A_SHARE): 1020.0}
        alerts = scan_alerts(db, prices)
        rapid_alerts = [a for a in alerts if a.alert_type == AlertType.RAPID_CHANGE]
        assert len(rapid_alerts) == 1
        assert "近7天" in rapid_alerts[0].message

    def test_no_alerts(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1050.0}  # +5%, under all thresholds
        alerts = scan_alerts(db, prices)
        assert alerts == []

    def test_alert_includes_thesis(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        db.add_journal_entry(JournalEntry(
            content="看好茅台长期消费升级",
            decision_type=DecisionType.BUY,
            emotion=Emotion.RATIONAL,
            related_symbols=["600519"],
        ))
        prices = {("600519", MarketType.A_SHARE): 1400.0}  # +40%
        alerts = scan_alerts(db, prices)
        assert len(alerts) >= 1
        assert alerts[0].original_thesis == "看好茅台长期消费升级"


class TestRecentPriceChange:
    def test_with_data(self, db: Database) -> None:
        today = date.today()
        _add_price_bars(db, "600519", [
            (today - timedelta(days=32), 900.0),
            (today - timedelta(days=20), 950.0),
            (today - timedelta(days=7), 980.0),
            (today - timedelta(days=3), 1000.0),
            (today, 1050.0),
        ])
        result = get_recent_price_change(db, "600519", MarketType.A_SHARE)
        assert result.one_week_pct is not None
        assert result.one_month_pct is not None
        # 1w: (1050 - 980) / 980 = 7.1%
        assert abs(result.one_week_pct - 7.1) < 0.2
        # 1m: (1050 - 950) / 950 = 10.5% (closest bar to 30 days ago)
        assert result.one_month_pct is not None

    def test_insufficient_data_returns_none(self, db: Database) -> None:
        result = get_recent_price_change(db, "600519", MarketType.A_SHARE)
        assert result.one_week_pct is None
        assert result.one_month_pct is None
