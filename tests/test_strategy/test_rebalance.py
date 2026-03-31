"""Tests for rebalance calculation."""

from datetime import datetime

from haoinvest.db import Database
from haoinvest.models import MarketType, Transaction, TransactionAction
from haoinvest.portfolio.manager import PortfolioManager
from haoinvest.strategy.rebalance import calculate_rebalance


class TestRebalance:
    def _setup_portfolio(self, db: Database) -> None:
        pm = PortfolioManager(db)
        # 80% in A, 20% in B by cost
        pm.add_trade(Transaction(
            symbol="A", market_type=MarketType.A_SHARE,
            action=TransactionAction.BUY, quantity=80, price=100.0,
            executed_at=datetime(2026, 1, 1),
        ))
        pm.add_trade(Transaction(
            symbol="B", market_type=MarketType.A_SHARE,
            action=TransactionAction.BUY, quantity=20, price=100.0,
            executed_at=datetime(2026, 1, 1),
        ))

    def test_rebalance_to_equal_weight(self, db: Database):
        self._setup_portfolio(db)
        trades = calculate_rebalance(
            db,
            target_weights={"A": 0.5, "B": 0.5},
            current_prices={"A": 100.0, "B": 100.0},
        )
        # Should sell some A and buy some B
        sell_a = next((t for t in trades if t.symbol == "A"), None)
        buy_b = next((t for t in trades if t.symbol == "B"), None)
        assert sell_a is not None and sell_a.action == "sell"
        assert buy_b is not None and buy_b.action == "buy"

    def test_skip_small_adjustments(self, db: Database):
        self._setup_portfolio(db)
        # Target is almost the same as current
        trades = calculate_rebalance(
            db,
            target_weights={"A": 0.798, "B": 0.202},
            current_prices={"A": 100.0, "B": 100.0},
        )
        assert len(trades) == 0

    def test_new_asset_appears_as_buy(self, db: Database):
        self._setup_portfolio(db)
        trades = calculate_rebalance(
            db,
            target_weights={"A": 0.4, "B": 0.3, "C": 0.3},
            current_prices={"A": 100.0, "B": 100.0, "C": 50.0},
        )
        buy_c = next((t for t in trades if t.symbol == "C"), None)
        assert buy_c is not None and buy_c.action == "buy"

    def test_empty_portfolio(self, db: Database):
        trades = calculate_rebalance(
            db,
            target_weights={"A": 0.5, "B": 0.5},
            current_prices={"A": 100.0, "B": 100.0},
        )
        assert len(trades) == 0
