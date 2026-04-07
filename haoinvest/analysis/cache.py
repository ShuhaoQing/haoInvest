"""Price data caching — ensure price history is available before analysis."""

from datetime import date, timedelta

from ..db import Database
from ..market import get_provider
from ..models import MarketType


def ensure_prices_cached(
    db: Database, symbol: str, market_type: MarketType, start: date, end: date
) -> None:
    """Fetch and cache price history if not already present.

    Includes gap-fill: if cached data doesn't cover the requested start date,
    fetches the missing earlier portion.
    """
    existing = db.get_prices(symbol, market_type, start, end)
    if len(existing) > 10:
        earliest_cached = min(b.trade_date for b in existing)
        if earliest_cached <= start + timedelta(days=7):
            return
        provider = get_provider(market_type)
        bars = provider.get_price_history(symbol, start, earliest_cached)
        if bars:
            db.save_prices(bars)
        return
    provider = get_provider(market_type)
    bars = provider.get_price_history(symbol, start, end)
    if bars:
        db.save_prices(bars)
