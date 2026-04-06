"""Tests for guardrails pre-trade data aggregation."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from haoinvest.db import Database
from haoinvest.guardrails.pre_trade_data import collect_pre_trade_data
from haoinvest.models import (
    DecisionType,
    Emotion,
    JournalEntry,
    MarketType,
    Position,
    PriceBar,
    Transaction,
    TransactionAction,
)


def _add_position(db: Database, symbol: str, qty: float, avg_cost: float) -> None:
    db.upsert_position(
        Position(symbol=symbol, market_type=MarketType.A_SHARE, cached_quantity=qty, cached_avg_cost=avg_cost)
    )


@patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
class TestCollectPreTradeData:
    def test_full_data(self, _mock_sector, db: Database) -> None:
        # Set up position, journal, price history
        _add_position(db, "600519", 100, 1000)
        _add_position(db, "000858", 200, 150)

        db.add_journal_entry(JournalEntry(
            content="看好茅台长期消费逻辑",
            decision_type=DecisionType.BUY,
            emotion=Emotion.RATIONAL,
            related_symbols=["600519"],
        ))

        today = date.today()
        db.save_prices([
            PriceBar(symbol="600519", market_type=MarketType.A_SHARE, trade_date=today - timedelta(days=10), close=1000),
            PriceBar(symbol="600519", market_type=MarketType.A_SHARE, trade_date=today, close=1100),
        ])

        prices = {
            ("600519", MarketType.A_SHARE): 1100.0,
            ("000858", MarketType.A_SHARE): 150.0,
        }

        result = collect_pre_trade_data(
            db, "600519", MarketType.A_SHARE, "buy", 50, 1100.0, prices
        )

        assert result.symbol == "600519"
        assert result.action == "buy"
        assert result.quantity == 50
        assert result.price == 1100.0
        assert result.portfolio_context is not None
        assert result.portfolio_context.total_positions == 2
        assert result.current_position is not None
        assert result.current_position.symbol == "600519"
        assert result.current_position.quantity == 100
        assert result.original_thesis == "看好茅台长期消费逻辑"

    def test_empty_portfolio(self, _mock_sector, db: Database) -> None:
        prices: dict[tuple[str, MarketType], float] = {}
        result = collect_pre_trade_data(
            db, "600519", MarketType.A_SHARE, "buy", 100, 1800.0, prices
        )
        assert result.portfolio_context is None
        assert result.current_position is None
        assert result.emotion_stats == {}
        assert result.original_thesis is None

    def test_no_journal(self, _mock_sector, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1100.0}
        result = collect_pre_trade_data(
            db, "600519", MarketType.A_SHARE, "buy", 50, 1100.0, prices
        )
        assert result.original_thesis is None

    def test_no_price_history(self, _mock_sector, db: Database) -> None:
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1100.0}
        result = collect_pre_trade_data(
            db, "600519", MarketType.A_SHARE, "buy", 50, 1100.0, prices
        )
        assert result.recent_price_change.one_week_pct is None
        assert result.recent_price_change.one_month_pct is None
