"""Tests for guardrails emotion stats."""

from haoinvest.db import Database
from haoinvest.guardrails.emotion import (
    get_emotion_trade_stats,
    get_emotion_trade_stats_with_prices,
)
from haoinvest.models import (
    DecisionType,
    Emotion,
    JournalEntry,
    MarketType,
    Position,
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


def _add_journal(
    db: Database,
    content: str,
    decision: DecisionType,
    emotion: Emotion,
    symbols: list[str],
) -> None:
    db.add_journal_entry(
        JournalEntry(
            content=content,
            decision_type=decision,
            emotion=emotion,
            related_symbols=symbols,
        )
    )


class TestEmotionTradeStats:
    def test_stats_with_trades(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        _add_journal(db, "FOMO买入茅台", DecisionType.BUY, Emotion.FOMO, ["600519"])
        _add_journal(db, "FOMO买入五粮液", DecisionType.BUY, Emotion.FOMO, ["000858"])
        _add_position(db, "000858", 50, 200)

        stats = get_emotion_trade_stats(db)
        assert "fomo" in stats
        assert stats["fomo"].total_trades == 2

    def test_stats_empty_history(self, db: Database) -> None:
        stats = get_emotion_trade_stats(db)
        assert stats == {}

    def test_stats_by_symbol(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        _add_position(db, "000858", 50, 200)
        _add_journal(db, "FOMO买入茅台", DecisionType.BUY, Emotion.FOMO, ["600519"])
        _add_journal(db, "FOMO买入五粮液", DecisionType.BUY, Emotion.FOMO, ["000858"])

        stats = get_emotion_trade_stats(db, symbol="600519")
        assert "fomo" in stats
        assert stats["fomo"].total_trades == 1

    def test_profitable_pct_with_prices(self, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)  # avg_cost = 1000
        _add_position(db, "000858", 50, 200)  # avg_cost = 200
        _add_journal(db, "FOMO买入茅台", DecisionType.BUY, Emotion.FOMO, ["600519"])
        _add_journal(db, "FOMO买入五粮液", DecisionType.BUY, Emotion.FOMO, ["000858"])

        prices = {
            ("600519", "a_share"): 1200.0,  # profitable
            ("000858", "a_share"): 150.0,  # loss
        }
        stats = get_emotion_trade_stats_with_prices(db, prices)
        assert "fomo" in stats
        assert stats["fomo"].total_trades == 2
        assert stats["fomo"].profitable_pct == 50.0  # 1 out of 2
