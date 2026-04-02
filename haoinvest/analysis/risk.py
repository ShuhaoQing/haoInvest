"""Risk metrics: volatility, max drawdown, Sharpe ratio, Sortino ratio."""

from datetime import date

from ..db import Database
from ..engine.databridge import daily_returns, multi_asset_prices
from ..engine.risk_engine import compute_correlation_matrix, compute_risk_metrics
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

    returns = daily_returns(bars)
    if len(returns) < 1:
        return RiskMetrics(
            num_days=len(bars),
            message="Not enough close prices for analysis",
        )

    result = compute_risk_metrics(returns, risk_free_rate)
    result.num_days = len(bars)
    return result


def portfolio_correlation(
    db: Database,
    symbols: list[tuple[str, MarketType]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Calculate correlation matrix between assets.

    Returns a dict with symbols as keys and correlation values.
    """
    prices_df = multi_asset_prices(db, symbols, start_date, end_date)
    if prices_df.empty or len(prices_df.columns) < 2:
        return {"message": "Need at least 2 assets with price data", "matrix": {}}

    returns_df = prices_df.pct_change().dropna()
    if len(returns_df) < 2:
        return {"message": "Need at least 2 data points for correlation", "matrix": {}}

    matrix = compute_correlation_matrix(returns_df)
    return {"matrix": matrix}
