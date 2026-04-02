"""Tests for engine.optimization_engine — PyPortfolioOpt based optimization."""

import numpy as np
import pandas as pd

from haoinvest.engine.optimization_engine import equal_weight, optimize_portfolio


def _make_prices(n_days: int = 252, seed: int = 42) -> pd.DataFrame:
    """Build a 3-asset prices DataFrame with realistic characteristics."""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {
            "LOW_VOL": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.005, n_days)),
            "MED_VOL": 100 * np.cumprod(1 + np.random.normal(0.0005, 0.015, n_days)),
            "HIGH_VOL": 100 * np.cumprod(1 + np.random.normal(0.0008, 0.03, n_days)),
        },
        index=dates,
    )


class TestEqualWeight:
    def test_two_assets(self):
        assert equal_weight(["A", "B"]) == {"A": 0.5, "B": 0.5}

    def test_empty(self):
        assert equal_weight([]) == {}

    def test_sums_to_one(self):
        weights = equal_weight(["A", "B", "C", "D", "E"])
        assert abs(sum(weights.values()) - 1.0) < 1e-10


class TestOptimizePortfolio:
    def test_equal_weight_method(self):
        prices = _make_prices()
        weights = optimize_portfolio(prices, method="equal_weight")
        assert len(weights) == 3
        for w in weights.values():
            assert abs(w - 1 / 3) < 0.01

    def test_risk_parity(self):
        prices = _make_prices()
        weights = optimize_portfolio(prices, method="risk_parity")
        assert abs(sum(weights.values()) - 1.0) < 0.01
        # Low vol asset should get highest weight
        assert weights["LOW_VOL"] > weights["HIGH_VOL"]

    def test_min_volatility(self):
        prices = _make_prices()
        weights = optimize_portfolio(prices, method="min_volatility")
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_max_sharpe(self):
        prices = _make_prices()
        weights = optimize_portfolio(prices, method="max_sharpe")
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_unknown_method_falls_back(self):
        """Unknown method falls back to equal weight via the except clause."""
        prices = _make_prices()
        weights = optimize_portfolio(prices, method="unknown_magic")
        # Falls back to equal_weight
        assert len(weights) == 3

    def test_insufficient_data_falls_back(self):
        """Too few rows falls back to equal weight."""
        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        prices = pd.DataFrame({"A": [100, 101, 102], "B": [50, 51, 52]}, index=dates)
        weights = optimize_portfolio(prices, method="min_volatility")
        assert weights == {"A": 0.5, "B": 0.5}

    def test_empty_df_falls_back(self):
        prices = pd.DataFrame()
        weights = optimize_portfolio(prices, method="risk_parity")
        assert weights == {}
