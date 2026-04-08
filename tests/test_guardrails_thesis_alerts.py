"""Tests for thesis review alerts in guardrails."""

from datetime import date, datetime, timedelta

from haoinvest.db import Database
from haoinvest.guardrails.alerts import scan_alerts
from haoinvest.models import (
    AlertType,
    InvestmentThesis,
    MarketType,
    Position,
    ThesisStatus,
)


def _add_position(db: Database, symbol: str, qty: float, avg_cost: float) -> None:
    db.upsert_position(
        Position(
            symbol=symbol,
            market_type=MarketType.A_SHARE,
            cached_quantity=qty,
            cached_avg_cost=avg_cost,
        )
    )


class TestThesisReviewAlerts:
    def test_overdue_thesis_triggers_alert(self, db: Database) -> None:
        """A thesis past its review interval should trigger THESIS_REVIEW alert."""
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="消费升级",
                review_interval_days=30,
            )
        )
        # Backdate created_at to 40 days ago
        db.conn.execute(
            "UPDATE investment_theses SET created_at = ? WHERE id = ?",
            ((datetime.now() - timedelta(days=40)).isoformat(), tid),
        )
        db.conn.commit()

        # Need a position for scan_alerts to run, but thesis alerts are independent
        prices: dict[tuple[str, MarketType], float] = {}
        alerts = scan_alerts(db, prices)
        thesis_alerts = [a for a in alerts if a.alert_type == AlertType.THESIS_REVIEW]
        assert len(thesis_alerts) == 1
        assert "未审查" in thesis_alerts[0].message
        assert thesis_alerts[0].symbol == "600519"

    def test_recently_reviewed_no_alert(self, db: Database) -> None:
        """A recently reviewed thesis should not trigger an alert."""
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="消费升级",
                review_interval_days=30,
            )
        )
        db.mark_thesis_reviewed(tid)

        prices: dict[tuple[str, MarketType], float] = {}
        alerts = scan_alerts(db, prices)
        thesis_alerts = [a for a in alerts if a.alert_type == AlertType.THESIS_REVIEW]
        assert len(thesis_alerts) == 0

    def test_invalidated_thesis_no_alert(self, db: Database) -> None:
        """Invalidated theses should not trigger review alerts."""
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="消费升级",
                review_interval_days=1,
            )
        )
        db.update_thesis_status(tid, ThesisStatus.INVALIDATED, reason="thesis broken")
        # Backdate to ensure overdue
        db.conn.execute(
            "UPDATE investment_theses SET created_at = ? WHERE id = ?",
            ((datetime.now() - timedelta(days=10)).isoformat(), tid),
        )
        db.conn.commit()

        prices: dict[tuple[str, MarketType], float] = {}
        alerts = scan_alerts(db, prices)
        thesis_alerts = [a for a in alerts if a.alert_type == AlertType.THESIS_REVIEW]
        assert len(thesis_alerts) == 0
