"""Analysis report assembly — combines fundamental and risk data."""

from datetime import date

from ..db import Database
from ..models import MarketType
from .fundamental import analyze_stock
from .risk import calculate_risk_metrics


def full_stock_report(
    db: Database,
    symbol: str,
    market_type: MarketType,
    price_start: date | None = None,
    price_end: date | None = None,
) -> dict:
    """Generate a comprehensive analysis report for a single stock.

    Combines fundamental analysis with risk metrics from price history.
    Results are cached in the database.
    """
    # Check cache first
    cached = db.get_cached_analysis(symbol, "full_report")
    if cached:
        return cached

    fundamental = analyze_stock(symbol, market_type)
    risk = calculate_risk_metrics(db, symbol, market_type, price_start, price_end)

    report = {
        **fundamental,
        "risk_metrics": risk,
    }

    # Cache the result
    db.save_analysis(symbol, "full_report", report)

    return report
