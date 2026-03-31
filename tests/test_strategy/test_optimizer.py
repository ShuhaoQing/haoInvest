"""Tests for portfolio optimization strategies."""

from datetime import date

from haoinvest.db import Database
from haoinvest.models import MarketType, PriceBar
from haoinvest.strategy.optimizer import equal_weight, risk_parity, suggest_allocation


class TestEqualWeight:
    def test_two_assets(self):
        weights = equal_weight(["A", "B"])
        assert weights == {"A": 0.5, "B": 0.5}

    def test_three_assets(self):
        weights = equal_weight(["A", "B", "C"])
        assert abs(sum(weights.values()) - 1.0) < 1e-10
        assert abs(weights["A"] - 0.3333) < 0.001

    def test_empty(self):
        assert equal_weight([]) == {}

    def test_single_asset(self):
        weights = equal_weight(["A"])
        assert weights == {"A": 1.0}


class TestRiskParity:
    def _seed_prices(self, db: Database):
        """Seed price data: asset A is low vol, asset B is high vol."""
        from datetime import timedelta

        bars_a = []
        bars_b = []
        base_a = 100.0
        base_b = 100.0
        start = date(2026, 1, 2)

        for i in range(60):
            trade_date = start + timedelta(days=i)
            base_a *= 1 + 0.005 * (1 if i % 2 == 0 else -1)
            bars_a.append(
                PriceBar(
                    symbol="A",
                    market_type=MarketType.A_SHARE,
                    trade_date=trade_date,
                    close=round(base_a, 2),
                )
            )
            base_b *= 1 + 0.03 * (1 if i % 2 == 0 else -1)
            bars_b.append(
                PriceBar(
                    symbol="B",
                    market_type=MarketType.A_SHARE,
                    trade_date=trade_date,
                    close=round(base_b, 2),
                )
            )

        db.save_prices(bars_a)
        db.save_prices(bars_b)

    def test_low_vol_gets_higher_weight(self, db: Database):
        self._seed_prices(db)
        weights = risk_parity(
            db,
            [("A", MarketType.A_SHARE), ("B", MarketType.A_SHARE)],
        )
        assert "A" in weights and "B" in weights
        assert weights["A"] > weights["B"]  # Low vol asset gets more weight
        assert abs(sum(weights.values()) - 1.0) < 1e-10

    def test_falls_back_to_equal_weight(self, db: Database):
        """No price data → falls back to equal weight."""
        weights = risk_parity(
            db,
            [("X", MarketType.A_SHARE), ("Y", MarketType.A_SHARE)],
        )
        assert weights["X"] == 0.5
        assert weights["Y"] == 0.5


class TestSuggestAllocation:
    def test_equal_weight_method(self, db: Database):
        result = suggest_allocation(
            db,
            [("A", MarketType.A_SHARE), ("B", MarketType.A_SHARE)],
            method="equal_weight",
        )
        assert result.method == "equal_weight"
        assert abs(sum(result.weights.values()) - 1.0) < 1e-10
        assert "等权" in result.explanation

    def test_unknown_method_raises(self, db: Database):
        import pytest

        with pytest.raises(ValueError, match="Unknown method"):
            suggest_allocation(db, [], method="magic")
