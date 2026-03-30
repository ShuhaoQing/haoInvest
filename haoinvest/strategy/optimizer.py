"""Portfolio optimization: simple strategies without PyPortfolioOpt.

Provides equal weight, risk parity, and min volatility allocations
using basic math. PyPortfolioOpt can be added later when holdings > 10.
"""

import math
from datetime import date

from ..db import Database
from ..models import MarketType


def equal_weight(symbols: list[str]) -> dict[str, float]:
    """Equal weight allocation across all symbols.

    Returns: {symbol: weight} where weights sum to 1.0.
    """
    if not symbols:
        return {}
    w = round(1.0 / len(symbols), 4)
    weights = {s: w for s in symbols}
    # Adjust last to ensure exact sum of 1.0
    remainder = 1.0 - sum(weights.values())
    weights[symbols[-1]] = round(weights[symbols[-1]] + remainder, 4)
    return weights


def risk_parity(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, float]:
    """Risk parity allocation: weight inversely proportional to volatility.

    Assets with lower volatility get higher allocation, so each contributes
    roughly equal risk to the portfolio.

    Returns: {symbol: weight} where weights sum to 1.0.
    """
    vols: dict[str, float] = {}

    for symbol, market_type in symbols_with_market:
        bars = db.get_prices(symbol, market_type, start_date, end_date)
        closes = [b.close for b in bars if b.close is not None]
        if len(closes) < 2:
            continue
        daily_returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, len(closes))
        ]
        mean_r = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        vol = math.sqrt(variance) * math.sqrt(252)  # annualized
        if vol > 0:
            vols[symbol] = vol

    if not vols:
        return equal_weight([s for s, _ in symbols_with_market])

    # Inverse vol weights
    inv_vols = {s: 1.0 / v for s, v in vols.items()}
    total_inv = sum(inv_vols.values())
    weights = {s: round(iv / total_inv, 4) for s, iv in inv_vols.items()}

    # Adjust for rounding
    remainder = 1.0 - sum(weights.values())
    last_key = list(weights.keys())[-1]
    weights[last_key] = round(weights[last_key] + remainder, 4)

    return weights


def min_volatility(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, float]:
    """Minimum volatility allocation (simplified).

    For ≤5 assets, uses inverse-variance weighting as approximation.
    For a proper solution, use PyPortfolioOpt with covariance matrix.

    Returns: {symbol: weight} where weights sum to 1.0.
    """
    # For small portfolios, inverse-variance is a reasonable approximation
    # It ignores correlations but is simple and interpretable
    return risk_parity(db, symbols_with_market, start_date, end_date)


def suggest_allocation(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    method: str = "risk_parity",
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Generate allocation suggestion with explanation.

    Args:
        method: "equal_weight", "risk_parity", or "min_volatility"

    Returns dict with: method, weights, explanation.
    """
    symbols = [s for s, _ in symbols_with_market]

    if method == "equal_weight":
        weights = equal_weight(symbols)
        explanation = (
            "等权配置：每个资产分配相同比例。最简单的分散化策略，"
            "适合对各资产没有特别偏好时使用。"
        )
    elif method == "risk_parity":
        weights = risk_parity(db, symbols_with_market, start_date, end_date)
        explanation = (
            "风险平价：按波动率的倒数加权，波动率低的资产配置更多。"
            "目标是让每个资产对组合总风险的贡献大致相等。"
        )
    elif method == "min_volatility":
        weights = min_volatility(db, symbols_with_market, start_date, end_date)
        explanation = (
            "最小波动率：目标是最小化组合整体波动率。"
            "当前使用逆方差加权近似（忽略相关性），持仓超过10个时建议使用 PyPortfolioOpt。"
        )
    else:
        raise ValueError(f"Unknown method: {method}. Use 'equal_weight', 'risk_parity', or 'min_volatility'.")

    return {
        "method": method,
        "weights": weights,
        "explanation": explanation,
    }
