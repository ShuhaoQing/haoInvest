"""Technical indicators: MA, EMA, MACD, RSI, Bollinger Bands."""

from datetime import date

from ..db import Database
from ..engine.aggregation import aggregate_to_monthly, aggregate_to_weekly
from ..engine.databridge import pricebars_to_dataframe
from ..engine.technical_engine import compute_technical
from ..models import MarketType, MultiTimeframeTechnical, TechnicalIndicators


def analyze_technical(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = False,
) -> TechnicalIndicators:
    """Calculate all technical indicators for a stock from cached price history.

    When verbose=True, each sub-result includes a Chinese explanation
    of what the indicator value means for a beginner investor.
    """
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    df = pricebars_to_dataframe(bars)

    mt_str = market_type.value

    if len(df) < 14:
        return TechnicalIndicators(
            symbol=symbol,
            market_type=mt_str,
            message=f"Not enough price data ({len(df)} days, need at least 14)",
        )

    result = compute_technical(df, verbose=verbose)
    result.symbol = symbol
    result.market_type = mt_str
    return result


def analyze_technical_multi(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start_date: date | None = None,
    end_date: date | None = None,
    verbose: bool = False,
) -> MultiTimeframeTechnical:
    """Calculate technical indicators across daily, weekly, and monthly timeframes."""
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    mt_str = market_type.value

    def _compute_for_bars(bar_list: list, timeframe: str) -> TechnicalIndicators:
        df = pricebars_to_dataframe(bar_list)
        if len(df) < 14:
            return TechnicalIndicators(
                symbol=symbol,
                market_type=mt_str,
                timeframe=timeframe,
                message=f"Not enough {timeframe} data ({len(df)} bars, need at least 14)",
            )
        result = compute_technical(df, verbose=verbose)
        result.symbol = symbol
        result.market_type = mt_str
        result.timeframe = timeframe
        return result

    daily = _compute_for_bars(bars, "daily")
    weekly = _compute_for_bars(aggregate_to_weekly(bars), "weekly")
    monthly = _compute_for_bars(aggregate_to_monthly(bars), "monthly")

    return MultiTimeframeTechnical(
        symbol=symbol,
        market_type=mt_str,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
    )
