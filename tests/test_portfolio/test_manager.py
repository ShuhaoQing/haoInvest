"""Tests for portfolio manager: buy/sell/position correctness."""

from datetime import datetime


from haoinvest.db import Database
from haoinvest.models import MarketType, Transaction, TransactionAction
from haoinvest.portfolio.manager import PortfolioManager


class TestBuySell:
    def test_single_buy(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1680.0,
                fee=5.0,
                executed_at=datetime(2026, 3, 28),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is not None
        assert pos.cached_quantity == 100
        # avg_cost includes fee: (100 * 1680 + 5) / 100 = 1680.05
        assert pos.cached_avg_cost == 1680.05

    def test_multiple_buys_weighted_avg(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1600.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1800.0,
                executed_at=datetime(2026, 3, 15),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is not None
        assert pos.cached_quantity == 200
        # (100*1600 + 100*1800) / 200 = 1700
        assert pos.cached_avg_cost == 1700.0

    def test_partial_sell(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=200,
                price=1700.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.SELL,
                quantity=100,
                price=1800.0,
                executed_at=datetime(2026, 3, 15),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is not None
        assert pos.cached_quantity == 100
        # avg_cost unchanged after sell
        assert pos.cached_avg_cost == 1700.0

    def test_full_sell_zeroes_position(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1700.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.SELL,
                quantity=100,
                price=1800.0,
                executed_at=datetime(2026, 3, 15),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is None

    def test_sell_with_fees_and_tax(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1700.0,
                fee=5.0,
                tax=0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.SELL,
                quantity=50,
                price=1800.0,
                fee=5.0,
                tax=45.0,
                executed_at=datetime(2026, 3, 15),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is not None
        assert pos.cached_quantity == 50


class TestCryptoFloatPrecision:
    def test_small_crypto_trades(self, db: Database):
        """Buy 0.001 BTC three times, sell 0.003 BTC — should be zero."""
        pm = PortfolioManager(db)
        for _ in range(3):
            pm.add_trade(
                Transaction(
                    symbol="BTC_USDT",
                    market_type=MarketType.CRYPTO,
                    action=TransactionAction.BUY,
                    quantity=0.001,
                    price=87000.0,
                    executed_at=datetime(2026, 3, 28),
                )
            )
        pm.add_trade(
            Transaction(
                symbol="BTC_USDT",
                market_type=MarketType.CRYPTO,
                action=TransactionAction.SELL,
                quantity=0.003,
                price=88000.0,
                executed_at=datetime(2026, 3, 28),
            )
        )
        pos = pm.get_holding("BTC_USDT", MarketType.CRYPTO)
        assert pos is None


class TestSplitAndDividend:
    def test_stock_split(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1700.0,
                executed_at=datetime(2026, 1, 1),
            )
        )
        # 2:1 split — price field stores ratio
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.SPLIT,
                quantity=0,
                price=2.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pos = pm.get_holding("600519", MarketType.A_SHARE)
        assert pos is not None
        assert pos.cached_quantity == 200
        # avg_cost halved: 170000 / 200 = 850
        assert pos.cached_avg_cost == 850.0


class TestRebuildPositions:
    def test_rebuild_matches_incremental(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1700.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.SELL,
                quantity=50,
                price=1800.0,
                executed_at=datetime(2026, 3, 15),
            )
        )

        pos_before = pm.get_holding("600519", MarketType.A_SHARE)
        pm.rebuild_all_positions()
        pos_after = pm.get_holding("600519", MarketType.A_SHARE)

        assert pos_before is not None and pos_after is not None
        assert pos_before.cached_quantity == pos_after.cached_quantity
        assert pos_before.cached_avg_cost == pos_after.cached_avg_cost


class TestPortfolioSummary:
    def test_allocation_percentages(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(
            Transaction(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1000.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        pm.add_trade(
            Transaction(
                symbol="000858",
                market_type=MarketType.A_SHARE,
                action=TransactionAction.BUY,
                quantity=100,
                price=1000.0,
                executed_at=datetime(2026, 3, 1),
            )
        )
        summary = pm.get_portfolio_summary()
        assert len(summary) == 2
        total_alloc = sum(s.allocation_pct for s in summary)
        assert abs(total_alloc - 100.0) < 0.01
