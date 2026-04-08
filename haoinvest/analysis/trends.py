"""Historical financial trend analysis using multi-period eastmoney data."""

from ..models import MarketType


def financial_trends(
    symbol: str,
    market_type: MarketType,
    periods: int = 8,
) -> list[dict]:
    """Fetch multi-period financial data and return trend rows.

    Each row represents one reporting period with key metrics.
    Only available for A-shares (eastmoney data source).
    Returns empty list for non-A-share markets.
    """
    if market_type != MarketType.A_SHARE:
        return [{"message": f"Financial trends not available for {market_type.value}"}]

    from ..market.sources import eastmoney
    from ..market.sources._common import bypass_proxy

    with bypass_proxy():
        rows = eastmoney.get_financial_indicators(symbol, periods=periods)

    if not rows:
        return [{"message": f"No multi-period financial data for {symbol}"}]

    return [
        {
            "report_date": r.get("report_date", ""),
            "roe": r.get("roe"),
            "revenue_growth": r.get("revenue_growth"),
            "net_profit_growth": r.get("net_profit_growth"),
            "gross_margin": r.get("gross_margin"),
            "profit_margin": r.get("profit_margin"),
            "eps": r.get("eps"),
            "dividend_yield": r.get("dividend_yield"),
        }
        for r in rows
    ]
