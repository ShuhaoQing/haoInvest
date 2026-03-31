"""Tests for journal manager."""

from datetime import datetime

from haoinvest.db import Database
from haoinvest.journal import JournalManager
from haoinvest.models import (
    DecisionType,
    Emotion,
    MarketType,
    Transaction,
    TransactionAction,
)
from haoinvest.portfolio.manager import PortfolioManager


class TestJournalCrud:
    def test_create_and_get(self, db: Database):
        jm = JournalManager(db)
        entry_id = jm.create_entry(
            content="看好消费复苏",
            decision_type=DecisionType.BUY,
            emotion=Emotion.RATIONAL,
            related_symbols=["600519"],
        )
        assert entry_id > 0
        entries = jm.get_entries()
        assert len(entries) == 1
        assert entries[0].content == "看好消费复苏"
        assert entries[0].related_symbols == ["600519"]

    def test_filter_by_symbol(self, db: Database):
        jm = JournalManager(db)
        jm.create_entry(content="entry1", related_symbols=["600519"])
        jm.create_entry(content="entry2", related_symbols=["000858"])
        entries = jm.get_entries(symbol="600519")
        assert len(entries) == 1

    def test_add_retrospective(self, db: Database):
        jm = JournalManager(db)
        entry_id = jm.create_entry(content="test entry")
        jm.add_retrospective(entry_id, "回头看这个决策是正确的")
        entries = jm.get_entries()
        assert entries[0].retrospective == "回头看这个决策是正确的"


class TestDecisionStats:
    def test_stats_with_entries(self, db: Database):
        jm = JournalManager(db)
        jm.create_entry("买入茅台", DecisionType.BUY, Emotion.RATIONAL, ["600519"])
        jm.create_entry("卖出比亚迪", DecisionType.SELL, Emotion.FEARFUL, ["002594"])
        jm.create_entry("持有观望", DecisionType.HOLD, Emotion.UNCERTAIN)

        stats = jm.get_decision_stats(days=90)
        assert stats["total_entries"] == 3
        assert stats["decision_distribution"]["buy"] == 1
        assert stats["emotion_distribution"]["rational"] == 1
        # Buy and sell entries without retrospective should be in needs_review
        assert len(stats["needs_retrospective"]) == 2

    def test_empty_stats(self, db: Database):
        jm = JournalManager(db)
        stats = jm.get_decision_stats()
        assert stats["total_entries"] == 0


class TestRetrospectiveContext:
    def test_with_related_transactions(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1680.0,
                executed_at=datetime(2026, 3, 28),
            )
        )

        jm = JournalManager(db)
        entry_id = jm.create_entry(
            "买入茅台因为三季报超预期",
            DecisionType.BUY,
            Emotion.CONFIDENT,
            ["600519"],
        )

        context = jm.prepare_retrospective_context(entry_id)
        assert context is not None
        assert context["entry"]["content"] == "买入茅台因为三季报超预期"
        assert len(context["related_transactions"]) == 1
        assert context["related_transactions"][0]["symbol"] == "600519"

    def test_nonexistent_entry(self, db: Database):
        jm = JournalManager(db)
        assert jm.prepare_retrospective_context(999) is None
