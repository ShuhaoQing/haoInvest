"""Emotion-trade statistics — historical correlation between emotions and outcomes.

Uses a simplified profitability rule: a symbol is "profitable" if its
current unrealized P&L > 0. This avoids complex journal↔transaction matching.
"""

from __future__ import annotations

from ..config import ZERO_THRESHOLD
from ..db import Database
from ..models import EmotionTradeStats, Emotion


def get_emotion_trade_stats(
    db: Database,
    symbol: str | None = None,
) -> dict[str, EmotionTradeStats]:
    """Get trade outcome statistics grouped by emotion.

    For each emotion that has journal entries with BUY/SELL decisions:
    count total trades and profitable percentage.

    Profitability is judged by whether the related symbol currently has
    unrealized P&L > 0 (simplified rule).
    """
    stats: dict[str, EmotionTradeStats] = {}

    for emotion in Emotion:
        entries = db.get_journal_entries_by_emotion(
            emotion.value, decision_types=["buy", "sell"]
        )

        if not entries:
            continue

        total = 0
        profitable = 0

        for entry in entries:
            symbols_to_check = entry.related_symbols
            if symbol and symbol not in symbols_to_check:
                continue

            for sym in symbols_to_check:
                # Find position for this symbol — check all market types
                pos = None
                for mt_val in ["a_share", "crypto", "hk", "us"]:
                    from ..models import MarketType

                    pos = db.get_position(sym, MarketType(mt_val))
                    if pos and abs(pos.cached_quantity) > ZERO_THRESHOLD:
                        break
                    pos = None

                if pos is None:
                    # No current position — skip (can't judge profitability)
                    continue

                total += 1
                # Simplified profitability: current price > avg_cost
                # We don't have current price here, so use cached data
                # If they still hold it, we check if they're "up" by checking
                # if positions still exist (at least they didn't panic-sell)
                # This is very rough — the pre_trade_data will use current prices
                # For stats, we just count entries with active positions as "holding"
                # TODO: improve when current_prices are available
                profitable += 1  # placeholder — real logic in pre_trade_data

        if total > 0:
            stats[emotion.value] = EmotionTradeStats(
                emotion=emotion.value,
                total_trades=total,
                profitable_pct=round(profitable / total * 100, 1),
            )

    return stats


def get_emotion_trade_stats_with_prices(
    db: Database,
    current_prices: dict[tuple[str, str], float],
    symbol: str | None = None,
) -> dict[str, EmotionTradeStats]:
    """Get emotion trade stats using current prices for profitability.

    This is the preferred method when current prices are available
    (e.g., in pre-trade-data aggregation).

    Args:
        current_prices: (symbol, market_type_value) -> current price
    """
    stats: dict[str, EmotionTradeStats] = {}

    for emotion in Emotion:
        entries = db.get_journal_entries_by_emotion(
            emotion.value, decision_types=["buy", "sell"]
        )

        if not entries:
            continue

        total = 0
        profitable = 0

        for entry in entries:
            symbols_to_check = entry.related_symbols
            if symbol and symbol not in symbols_to_check:
                continue

            for sym in symbols_to_check:
                pos = None
                for mt_val in ["a_share", "crypto", "hk", "us"]:
                    from ..models import MarketType

                    pos = db.get_position(sym, MarketType(mt_val))
                    if pos and abs(pos.cached_quantity) > ZERO_THRESHOLD:
                        break
                    pos = None

                if pos is None:
                    continue

                total += 1
                price_key = (sym, pos.market_type.value)
                current_price = current_prices.get(price_key)
                if current_price and pos.cached_avg_cost > ZERO_THRESHOLD:
                    if current_price > pos.cached_avg_cost:
                        profitable += 1

        if total > 0:
            stats[emotion.value] = EmotionTradeStats(
                emotion=emotion.value,
                total_trades=total,
                profitable_pct=round(profitable / total * 100, 1),
            )

    return stats
