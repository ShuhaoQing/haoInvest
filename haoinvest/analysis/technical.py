"""Technical indicators: MA, EMA, MACD, RSI, Bollinger Bands."""

from datetime import date

from ..db import Database
from ..engine.databridge import pricebars_to_dataframe
from ..engine.technical_engine import compute_technical
from ..models import MarketType, TechnicalIndicators


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
