"""Aggregate daily price bars into weekly/monthly bars."""

from collections import defaultdict
from datetime import date
from typing import Callable

from ..models import PriceBar


def aggregate_to_weekly(daily_bars: list[PriceBar]) -> list[PriceBar]:
    """Aggregate daily bars into weekly bars (ISO week: Monday–Sunday)."""
    return _aggregate_bars(
        daily_bars,
        group_key=lambda d: d.isocalendar()[:2],  # (iso_year, iso_week)
    )


def aggregate_to_monthly(daily_bars: list[PriceBar]) -> list[PriceBar]:
    """Aggregate daily bars into monthly bars (calendar month)."""
    return _aggregate_bars(
        daily_bars,
        group_key=lambda d: (d.year, d.month),
    )


def _aggregate_bars(
    bars: list[PriceBar],
    group_key: Callable[[date], tuple],
) -> list[PriceBar]:
    """Group daily bars by key and aggregate OHLCV per group.

    Sorts input by trade_date first so open/close pick the correct first/last bar.
    """
    if not bars:
        return []

    sorted_bars = sorted(bars, key=lambda b: b.trade_date)
    groups: dict[tuple, list[PriceBar]] = defaultdict(list)
    for bar in sorted_bars:
        groups[group_key(bar.trade_date)].append(bar)

    result: list[PriceBar] = []
    for group_bars in groups.values():
        highs = [b.high for b in group_bars if b.high is not None]
        lows = [b.low for b in group_bars if b.low is not None]
        volumes = [b.volume for b in group_bars if b.volume is not None]

        result.append(
            PriceBar(
                symbol=group_bars[0].symbol,
                market_type=group_bars[0].market_type,
                trade_date=group_bars[-1].trade_date,
                open=group_bars[0].open,
                high=max(highs) if highs else None,
                low=min(lows) if lows else None,
                close=group_bars[-1].close,
                volume=sum(volumes) if volumes else None,
            )
        )

    return sorted(result, key=lambda b: b.trade_date)
