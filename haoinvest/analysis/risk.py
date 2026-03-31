"""Risk metrics: volatility, max drawdown, Sharpe ratio."""

import math
from datetime import date

from ..db import Database
from ..models import MarketType, RiskMetrics


def calculate_risk_metrics(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    risk_free_rate: float = 0.02,
) -> RiskMetrics:
    """Calculate risk metrics for a single asset from cached price history.

    Args:
        risk_free_rate: Annualized risk-free rate (default 2% for China).
    """
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    if len(bars) < 2:
        return RiskMetrics(
            num_days=len(bars),
            message="Not enough price data for analysis",
        )

    closes = [b.close for b in bars if b.close is not None]
    if len(closes) < 2:
        return RiskMetrics(
            num_days=len(bars),
            message="Not enough close prices for analysis",
        )

    daily_returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
    ]

    # Annualized volatility (assuming 252 trading days)
    if len(daily_returns) > 1:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        daily_vol = math.sqrt(variance)
        ann_vol = daily_vol * math.sqrt(252)
    else:
        ann_vol = None
        mean_return = daily_returns[0] if daily_returns else 0

    # Max drawdown
    peak = closes[0]
    max_dd = 0.0
    for price in closes[1:]:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        if dd > max_dd:
            max_dd = dd

    # Total return
    total_return_pct = (closes[-1] - closes[0]) / closes[0] * 100

    # Sharpe ratio
    if ann_vol and ann_vol > 0:
        ann_return = mean_return * 252
        sharpe = (ann_return - risk_free_rate) / ann_vol
    else:
        sharpe = None

    return RiskMetrics(
        annualized_volatility=round(ann_vol * 100, 2) if ann_vol else None,
        max_drawdown_pct=round(max_dd * 100, 2),
        sharpe_ratio=round(sharpe, 2) if sharpe is not None else None,
        total_return_pct=round(total_return_pct, 2),
        num_days=len(closes),
    )


def portfolio_correlation(
    db: Database,
    symbols: list[tuple[str, MarketType]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Calculate correlation matrix between assets.

    Returns a dict with symbols as keys and correlation values.
    Simple Pearson correlation on daily returns.
    """
    returns_by_symbol: dict[str, list[float]] = {}

    for symbol, market_type in symbols:
        bars = db.get_prices(symbol, market_type, start_date, end_date)
        closes = [b.close for b in bars if b.close is not None]
        if len(closes) < 2:
            continue
        returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
        ]
        returns_by_symbol[symbol] = returns

    if len(returns_by_symbol) < 2:
        return {"message": "Need at least 2 assets with price data", "matrix": {}}

    # Align lengths (use shortest common length)
    min_len = min(len(r) for r in returns_by_symbol.values())
    aligned = {s: r[:min_len] for s, r in returns_by_symbol.items()}

    syms = list(aligned.keys())
    matrix: dict[str, dict[str, float]] = {}

    for s1 in syms:
        matrix[s1] = {}
        for s2 in syms:
            matrix[s1][s2] = round(_pearson(aligned[s1], aligned[s2]), 4)

    return {"matrix": matrix}


def _pearson(x: list[float], y: list[float]) -> float:
    """Calculate Pearson correlation coefficient."""
    n = len(x)
    if n == 0:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)
