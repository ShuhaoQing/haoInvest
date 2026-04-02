"""Tests for engine.risk_engine — QuantStats based risk metrics."""

import numpy as np
import pandas as pd
import pytest

from haoinvest.engine.risk_engine import (
    compute_correlation_matrix,
    compute_risk_metrics,
)


def _make_returns(values: list[float], start: str = "2025-01-01") -> pd.Series:
    """Build a returns Series with DatetimeIndex."""
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series(values, index=idx)


class TestComputeRiskMetrics:
    def test_positive_returns(self):
        """All positive returns: positive total return, zero drawdown."""
        returns = _make_returns([0.01] * 30)
        result = compute_risk_metrics(returns)
        assert result.total_return_pct > 0
        assert result.max_drawdown_pct == 0.0
        assert result.sharpe_ratio is not None
        assert result.sharpe_ratio > 0
        # Sortino is None when there are no negative returns (downside dev = 0)

    def test_negative_returns(self):
        """All negative returns: negative total return, positive drawdown."""
        returns = _make_returns([-0.01] * 30)
        result = compute_risk_metrics(returns)
        assert result.total_return_pct < 0
        assert result.max_drawdown_pct > 0
        assert result.sharpe_ratio < 0

    def test_volatility_is_annualized_percentage(self):
        """Volatility should be expressed as an annualized percentage."""
        returns = _make_returns([0.01, -0.005, 0.02, -0.01, 0.015] * 20)
        result = compute_risk_metrics(returns)
        assert result.annualized_volatility is not None
        # Daily vol of ~1.1% * sqrt(252) ≈ 17%. Sanity check: between 5% and 50%
        assert 5 < result.annualized_volatility < 50

    def test_sortino_ratio_present(self):
        returns = _make_returns([0.01, -0.005, 0.02, -0.01, 0.015] * 20)
        result = compute_risk_metrics(returns)
        assert result.sortino_ratio is not None

    def test_single_return(self):
        """Single return should still produce some metrics."""
        returns = _make_returns([0.01])
        result = compute_risk_metrics(returns)
        # QuantStats returns NaN for vol/sharpe with 1 data point
        assert result.total_return_pct is not None


class TestComputeCorrelationMatrix:
    def test_constant_returns_edge_case(self):
        """Constant returns → std=0 → corr=NaN → returns None."""
        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        df = pd.DataFrame(
            {"A": [0.01] * 30, "B": [0.01] * 30},
            index=idx,
        )
        matrix = compute_correlation_matrix(df)
        assert "A" in matrix and "B" in matrix
        assert matrix["A"]["A"] is None
        assert matrix["A"]["B"] is None

    def test_varying_correlation(self):
        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        np.random.seed(42)
        a = np.random.normal(0.01, 0.02, 30)
        df = pd.DataFrame({"A": a, "B": a * 0.5 + 0.005}, index=idx)
        matrix = compute_correlation_matrix(df)
        assert matrix["A"]["B"] == pytest.approx(1.0, abs=0.01)

    def test_negative_correlation(self):
        idx = pd.date_range("2025-01-01", periods=30, freq="B")
        np.random.seed(42)
        a = np.random.normal(0.01, 0.02, 30)
        df = pd.DataFrame({"A": a, "B": -a}, index=idx)
        matrix = compute_correlation_matrix(df)
        assert matrix["A"]["B"] == pytest.approx(-1.0, abs=0.01)
