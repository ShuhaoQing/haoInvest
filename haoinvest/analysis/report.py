"""Analysis report assembly — combines fundamental and risk data."""

from datetime import date

from ..db import Database
from ..models import MarketType, StockReport
from .fundamental import analyze_stock
from .risk import calculate_risk_metrics
from .signals import aggregate_signals
from .technical import analyze_technical
from .volume import analyze_volume


def full_stock_report(
    db: Database,
    symbol: str,
    market_type: MarketType,
    price_start: date | None = None,
    price_end: date | None = None,
    include_technical: bool = False,
) -> StockReport:
    """Generate a comprehensive analysis report for a single stock.

    Combines fundamental analysis with risk metrics from price history.
    When include_technical=True, also adds technical indicators, volume
    analysis, and aggregated signals.
    Results are cached in the database.
    """
    date_suffix = f"_{price_start}_{price_end}" if (price_start or price_end) else ""
    cache_key = f"full_report_tech{date_suffix}" if include_technical else f"full_report{date_suffix}"
    cached = db.get_cached_analysis(symbol, cache_key)
    if cached:
        return StockReport.model_validate(cached)

    fundamental = analyze_stock(symbol, market_type)
    risk = calculate_risk_metrics(db, symbol, market_type, price_start, price_end)

    report = StockReport(
        symbol=fundamental.symbol,
        name=fundamental.name,
        sector=fundamental.sector,
        market_type=fundamental.market_type,
        current_price=fundamental.current_price,
        currency=fundamental.currency,
        pe_ratio=fundamental.pe_ratio,
        pb_ratio=fundamental.pb_ratio,
        total_market_cap=fundamental.total_market_cap,
        valuation=fundamental.valuation,
        risk_metrics=risk,
    )

    if include_technical:
        report.technical = analyze_technical(
            db, symbol, market_type, price_start, price_end
        )
        report.volume = analyze_volume(db, symbol, market_type, price_start, price_end)
        report.signals = aggregate_signals(
            db, symbol, market_type, price_start, price_end
        )

    # Cache the result
    db.save_analysis(symbol, cache_key, report.model_dump())

    return report
