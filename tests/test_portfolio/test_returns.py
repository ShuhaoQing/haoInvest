"""Tests for returns calculation."""

from datetime import datetime

from haoinvest.db import Database
from haoinvest.models import MarketType, Transaction, TransactionAction
from haoinvest.portfolio.manager import PortfolioManager
from haoinvest.portfolio.returns import (
    portfolio_returns_summary,
    realized_pnl,
    unrealized_pnl,
)


def _setup_trades(db: Database) -> PortfolioManager:
    pm = PortfolioManager(db)
    pm.add_trade(Transaction(
        symbol="600519", market_type=MarketType.A_SHARE,
        action=TransactionAction.BUY, quantity=100, price=1600.0,
        fee=5.0, executed_at=datetime(2026, 1, 1),
    ))
    pm.add_trade(Transaction(
        symbol="600519", market_type=MarketType.A_SHARE,
        action=TransactionAction.SELL, quantity=50, price=1800.0,
        fee=5.0, tax=45.0, executed_at=datetime(2026, 2, 1),
    ))
    return pm


class TestUnrealizedPnl:
    def test_basic(self, db: Database):
        _setup_trades(db)
        result = unrealized_pnl(db, "600519", MarketType.A_SHARE, current_price=1700.0)
        assert result.quantity == 50
        assert result.current_price == 1700.0
        # avg_cost = (100*1600 + 5) / 100 = 1600.05
        # unrealized = 50 * 1700 - 50 * 1600.05 = 85000 - 80002.5 = 4997.5
        assert result.unrealized_pnl == 4997.5

    def test_zero_position(self, db: Database):
        result = unrealized_pnl(db, "999999", MarketType.A_SHARE, current_price=100.0)
        assert result.quantity == 0
        assert result.unrealized_pnl == 0


class TestRealizedPnl:
    def test_basic(self, db: Database):
        _setup_trades(db)
        result = realized_pnl(db, "600519", MarketType.A_SHARE)
        assert result.num_sell_trades == 1
        # Sell 50 shares at 1800, fee=5, tax=45
        # proceeds = 50*1800 - 5 - 45 = 89950
        # cost of sold = 50 * 1600.05 = 80002.5
        # realized = 89950 - 80002.5 = 9947.5
        assert result.total_realized_pnl == 9947.5

    def test_no_trades(self, db: Database):
        result = realized_pnl(db, "999999", MarketType.A_SHARE)
        assert result.total_realized_pnl == 0
        assert result.num_sell_trades == 0

    def test_dividend_tracking(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(Transaction(
            symbol="600519", market_type=MarketType.A_SHARE,
            action=TransactionAction.BUY, quantity=100, price=1600.0,
            executed_at=datetime(2026, 1, 1),
        ))
        pm.add_trade(Transaction(
            symbol="600519", market_type=MarketType.A_SHARE,
            action=TransactionAction.DIVIDEND, quantity=100, price=25.0,
            executed_at=datetime(2026, 6, 1),
        ))
        result = realized_pnl(db, "600519", MarketType.A_SHARE)
        assert result.total_dividends == 2500.0


class TestPortfolioReturnsSummary:
    def test_multi_holding(self, db: Database):
        pm = PortfolioManager(db)
        pm.add_trade(Transaction(
            symbol="600519", market_type=MarketType.A_SHARE,
            action=TransactionAction.BUY, quantity=100, price=1600.0,
            executed_at=datetime(2026, 1, 1),
        ))
        pm.add_trade(Transaction(
            symbol="BTC_USDT", market_type=MarketType.CRYPTO,
            action=TransactionAction.BUY, quantity=0.1, price=85000.0,
            executed_at=datetime(2026, 1, 1),
        ))

        prices = {
            ("600519", MarketType.A_SHARE): 1800.0,
            ("BTC_USDT", MarketType.CRYPTO): 90000.0,
        }
        result = portfolio_returns_summary(db, prices)

        assert result.total_market_value == 100 * 1800 + 0.1 * 90000  # 189000
        assert result.total_unrealized_pnl > 0
        assert len(result.holdings) == 2
