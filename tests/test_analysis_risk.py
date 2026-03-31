"""Tests for risk metrics calculation."""

from datetime import date

from haoinvest.db import Database
from haoinvest.models import MarketType, PriceBar
from haoinvest.analysis.risk import calculate_risk_metrics, portfolio_correlation


def _seed_uptrend(db: Database, symbol: str = "TEST") -> None:
    """Seed 30 days of steadily rising prices."""
    bars = []
    price = 100.0
    for i in range(30):
        price *= 1.01  # 1% daily gain
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 1, 2 + i),
                close=round(price, 2),
            )
        )
    db.save_prices(bars)


class TestRiskMetrics:
    def test_basic_metrics(self, db: Database):
        _seed_uptrend(db)
        result = calculate_risk_metrics(db, "TEST", MarketType.A_SHARE)
        assert result.num_days == 30
        assert result.total_return_pct is not None
        assert result.total_return_pct > 0
        assert result.max_drawdown_pct is not None
        # Constant uptrend has 0 drawdown
        assert result.max_drawdown_pct == 0.0

    def test_not_enough_data(self, db: Database):
        db.save_prices(
            [
                PriceBar(
                    symbol="X",
                    market_type=MarketType.A_SHARE,
                    trade_date=date(2026, 1, 2),
                    close=100.0,
                )
            ]
        )
        result = calculate_risk_metrics(db, "X", MarketType.A_SHARE)
        assert result.annualized_volatility is None
        assert result.message is not None and "Not enough" in result.message


class TestCorrelation:
    def test_perfectly_correlated(self, db: Database):
        """Two assets with same daily returns should have correlation ~1.0."""
        bars_a = [
            PriceBar(
                symbol="A",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 1, 2 + i),
                close=100.0 * (1.01**i),
            )
            for i in range(30)
        ]
        bars_b = [
            PriceBar(
                symbol="B",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 1, 2 + i),
                close=50.0 * (1.01**i),
            )
            for i in range(30)
        ]
        db.save_prices(bars_a)
        db.save_prices(bars_b)

        result = portfolio_correlation(
            db, [("A", MarketType.A_SHARE), ("B", MarketType.A_SHARE)]
        )
        assert result["matrix"]["A"]["B"] > 0.99
