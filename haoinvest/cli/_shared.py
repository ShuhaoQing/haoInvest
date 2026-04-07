"""Shared CLI utilities — DB init, price fetching."""

from ..db import Database
from ..market import get_provider
from ..models import MarketType
from .formatters import error_output


def init_db() -> Database:
    """Initialize database with schema."""
    db = Database()
    db.init_schema()
    return db


def fetch_current_prices(db: Database) -> dict[tuple[str, MarketType], float]:
    """Fetch current prices for all non-zero holdings."""
    positions = db.get_positions(include_zero=False)
    prices: dict[tuple[str, MarketType], float] = {}
    for pos in positions:
        try:
            provider = get_provider(pos.market_type)
            prices[(pos.symbol, pos.market_type)] = provider.get_current_price(
                pos.symbol
            )
        except Exception as e:
            error_output(f"Failed to get price for {pos.symbol}: {e}")
    return prices
