"""Portfolio optimization using PyPortfolioOpt."""

import numpy as np
import pandas as pd
from pypfopt import EfficientFrontier, HRPOpt, expected_returns, risk_models
from pypfopt.exceptions import OptimizationError


def equal_weight(symbols: list[str]) -> dict[str, float]:
    """Equal weight allocation across all symbols."""
    if not symbols:
        return {}
    w = round(1.0 / len(symbols), 4)
    weights = {s: w for s in symbols}
    remainder = 1.0 - sum(weights.values())
    weights[symbols[-1]] = round(weights[symbols[-1]] + remainder, 4)
    return weights


def optimize_portfolio(
    prices_df: pd.DataFrame,
    method: str = "risk_parity",
    risk_free_rate: float = 0.02,
) -> dict[str, float]:
    """Optimize portfolio weights.

    Args:
        prices_df: Close prices DataFrame (columns=symbols, index=dates).
        method: One of equal_weight, risk_parity, min_volatility, max_sharpe.
        risk_free_rate: Annualized risk-free rate.

    Returns:
        {symbol: weight} where weights sum to ~1.0.
        Falls back to equal_weight on optimization failure.
    """
    symbols = list(prices_df.columns)

    if method == "equal_weight":
        return equal_weight(symbols)

    valid_methods = {"risk_parity", "min_volatility", "max_sharpe"}
    if method not in valid_methods:
        raise ValueError(
            f"Unknown method: {method}. "
            f"Use 'equal_weight', {', '.join(sorted(valid_methods))}."
        )

    if prices_df.empty or len(prices_df) < 5:
        return equal_weight(symbols)

    try:
        if method == "risk_parity":
            return _hrp(prices_df)
        elif method == "min_volatility":
            return _min_volatility(prices_df)
        else:
            return _max_sharpe(prices_df, risk_free_rate)
    except (OptimizationError, ValueError, np.linalg.LinAlgError):
        return equal_weight(symbols)


def _hrp(prices_df: pd.DataFrame) -> dict[str, float]:
    """Hierarchical Risk Parity — uses correlation structure."""
    returns = prices_df.pct_change().dropna()
    hrp = HRPOpt(returns)
    weights = hrp.optimize()
    return {s: round(float(w), 4) for s, w in weights.items()}


def _min_volatility(prices_df: pd.DataFrame) -> dict[str, float]:
    """Minimum volatility via mean-variance optimization."""
    mu = expected_returns.mean_historical_return(prices_df)
    S = risk_models.sample_cov(prices_df)
    ef = EfficientFrontier(mu, S)
    ef.min_volatility()
    return {s: round(float(w), 4) for s, w in ef.clean_weights().items()}


def _max_sharpe(prices_df: pd.DataFrame, risk_free_rate: float) -> dict[str, float]:
    """Maximum Sharpe ratio via mean-variance optimization."""
    mu = expected_returns.mean_historical_return(prices_df)
    S = risk_models.sample_cov(prices_df)
    ef = EfficientFrontier(mu, S)
    ef.max_sharpe(risk_free_rate=risk_free_rate)
    return {s: round(float(w), 4) for s, w in ef.clean_weights().items()}
