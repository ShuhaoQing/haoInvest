"""Portfolio optimization backed by PyPortfolioOpt."""

from datetime import date

from ..db import Database
from ..engine.databridge import multi_asset_prices
from ..engine.optimization_engine import equal_weight, optimize_portfolio
from ..models import AllocationSuggestion, MarketType

EXPLANATIONS = {
    "equal_weight": (
        "等权配置：每个资产分配相同比例。最简单的分散化策略，"
        "适合对各资产没有特别偏好时使用。"
    ),
    "risk_parity": (
        "风险平价(HRP)：使用层次聚类和协方差矩阵，"
        "让每个资产对组合总风险的贡献大致相等。"
    ),
    "min_volatility": (
        "最小波动率：通过均值-方差优化，找到波动率最小的资产组合。"
        "考虑了资产间的相关性。"
    ),
    "max_sharpe": (
        "最大夏普比率：在给定风险下追求最大收益，找到风险调整后收益最优的资产组合。"
    ),
}


def suggest_allocation(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    method: str = "risk_parity",
    start_date: date | None = None,
    end_date: date | None = None,
) -> AllocationSuggestion:
    """Generate allocation suggestion with explanation.

    Args:
        method: "equal_weight", "risk_parity", "min_volatility", or "max_sharpe"
    """
    if method not in EXPLANATIONS:
        raise ValueError(
            f"Unknown method: {method}. Use one of: {', '.join(EXPLANATIONS.keys())}."
        )

    symbols = [s for s, _ in symbols_with_market]

    if method == "equal_weight":
        weights = equal_weight(symbols)
    else:
        prices_df = multi_asset_prices(db, symbols_with_market, start_date, end_date)
        if prices_df.empty or len(prices_df) < 5:
            weights = equal_weight(symbols)
        else:
            weights = optimize_portfolio(prices_df, method)

    return AllocationSuggestion(
        method=method,
        weights=weights,
        explanation=EXPLANATIONS[method],
    )
