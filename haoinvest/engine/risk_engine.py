"""Risk metric computation using QuantStats."""

import pandas as pd
import quantstats as qs

from ..models import RiskMetrics
from .databridge import safe_float


def compute_risk_metrics(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
) -> RiskMetrics:
    """Compute risk metrics from a daily returns Series (with DatetimeIndex).

    Returns a RiskMetrics model. The num_days field is left at 0 — the adapter fills it in.
    """
    daily_rf = risk_free_rate / 252

    ann_vol = safe_float(qs.stats.volatility(returns, periods=252))
    max_dd = safe_float(qs.stats.max_drawdown(returns))
    sharpe = safe_float(qs.stats.sharpe(returns, rf=daily_rf, periods=252))
    sortino = safe_float(qs.stats.sortino(returns, rf=daily_rf, periods=252))
    total_return = safe_float(qs.stats.comp(returns))

    return RiskMetrics(
        annualized_volatility=round(ann_vol * 100, 2) if ann_vol is not None else None,
        max_drawdown_pct=round(abs(max_dd) * 100, 2) if max_dd is not None else None,
        sharpe_ratio=round(sharpe, 2) if sharpe is not None else None,
        sortino_ratio=round(sortino, 2) if sortino is not None else None,
        total_return_pct=round(total_return * 100, 2)
        if total_return is not None
        else None,
    )


def compute_correlation_matrix(
    returns_df: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """Pearson correlation matrix from multi-column returns DataFrame."""
    corr = returns_df.corr()
    result: dict[str, dict[str, float]] = {}
    for col in corr.columns:
        result[col] = {}
        for row in corr.index:
            val = safe_float(corr.loc[row, col])
            result[col][row] = round(val, 4) if val is not None else 0.0
    return result
