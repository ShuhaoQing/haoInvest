"""Convert between PriceBar (SQLite layer) and pandas DataFrame (library layer)."""

import math
from datetime import date

import pandas as pd

from ..db import Database
from ..models import MarketType, PriceBar


def pricebars_to_dataframe(bars: list[PriceBar]) -> pd.DataFrame:
    """PriceBar list to OHLCV DataFrame with DatetimeIndex.

    Columns: open, high, low, close, volume.
    Sorted by date ascending. Rows with None close are dropped.
    """
    records = [
        {
            "date": pd.Timestamp(b.trade_date),
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ]
    if not records:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    df = pd.DataFrame(records).set_index("date").sort_index()
    df = df.dropna(subset=["close"])
    return df


def closes_series(bars: list[PriceBar]) -> pd.Series:
    """Extract close prices as pd.Series with DatetimeIndex."""
    df = pricebars_to_dataframe(bars)
    return df["close"]


def daily_returns(bars: list[PriceBar]) -> pd.Series:
    """Daily percentage returns from PriceBars, first NaN dropped."""
    closes = closes_series(bars)
    return closes.pct_change().dropna()


def multi_asset_prices(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Multi-asset close prices DataFrame (one column per symbol).

    Dates aligned via inner join (only days where ALL assets have data).
    Used by PyPortfolioOpt for covariance estimation.
    """
    series_dict: dict[str, pd.Series] = {}
    for symbol, market_type in symbols_with_market:
        bars = db.get_prices(symbol, market_type, start_date, end_date)
        if bars:
            series_dict[symbol] = closes_series(bars)

    if not series_dict:
        return pd.DataFrame()

    df = pd.DataFrame(series_dict)
    df = df.dropna()
    return df


def safe_float(val) -> float | None:
    """Convert pandas scalar (including NaN/NaT/None) to float or None."""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None
