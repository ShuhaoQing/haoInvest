"""Pre-trade data aggregation — single call for agent trade review."""

from __future__ import annotations

import logging
from datetime import date

from ..config import ZERO_THRESHOLD
from ..db import Database
from ..models import (
    CurrentPositionInfo,
    MarketType,
    PortfolioContext,
    PreTradeData,
)
from .alerts import get_recent_price_change, scan_alerts
from .emotion import get_emotion_trade_stats_with_prices
from .rules import load_config, validate_trade

logger = logging.getLogger(__name__)


def collect_pre_trade_data(
    db: Database,
    symbol: str,
    market_type: MarketType,
    action: str,
    quantity: float,
    price: float,
    current_prices: dict[tuple[str, MarketType], float],
    cash_balance: float = 0.0,
) -> PreTradeData:
    """Collect all data needed for agent pre-trade review in one call.

    Aggregates: rule violations, portfolio context, current position,
    alerts, recent price change, emotion stats, and original thesis.
    """
    # 1. Simulated rule violations
    violations = validate_trade(
        db, symbol, market_type, action, quantity, price, current_prices, cash_balance
    )

    # 2. Portfolio context
    portfolio_context = _build_portfolio_context(db, current_prices, cash_balance)

    # 3. Current position info
    current_position = _build_current_position(
        db, symbol, market_type, current_prices, portfolio_context
    )

    # 4. Alerts for this symbol
    all_alerts = scan_alerts(db, current_prices)
    symbol_alerts = [a for a in all_alerts if a.symbol == symbol]

    # 5. Recent price change
    recent_change = get_recent_price_change(db, symbol, market_type)

    # 6. Emotion stats (with current prices for accurate profitability)
    price_key_map = {(s, mt.value): p for (s, mt), p in current_prices.items()}
    emotion_stats = get_emotion_trade_stats_with_prices(db, price_key_map)

    # 7. Original thesis
    original_thesis = _get_thesis(db, symbol)

    return PreTradeData(
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        simulated_violations=violations,
        portfolio_context=portfolio_context,
        current_position=current_position,
        current_alerts=symbol_alerts,
        recent_price_change=recent_change,
        emotion_stats=emotion_stats,
        original_thesis=original_thesis,
    )


def _build_portfolio_context(
    db: Database,
    current_prices: dict[tuple[str, MarketType], float],
    cash_balance: float,
) -> PortfolioContext | None:
    """Build portfolio-level context for the agent."""
    positions = db.get_positions(include_zero=False)
    if not positions:
        return None

    total_mv = 0.0
    sector_values: dict[str, float] = {}

    for pos in positions:
        key = (pos.symbol, pos.market_type)
        price = current_prices.get(key, pos.cached_avg_cost)
        mv = pos.cached_quantity * price
        total_mv += mv

        # Try to get sector
        from .rules import _get_sector_for_symbol

        sector = _get_sector_for_symbol(db, pos.symbol, pos.market_type)
        if sector:
            sector_values[sector] = sector_values.get(sector, 0) + mv

    if total_mv <= 0:
        return None

    sector_allocations = {
        s: round(v / total_mv * 100, 1) for s, v in sector_values.items()
    }

    return PortfolioContext(
        total_positions=len(positions),
        total_market_value=round(total_mv, 2),
        sector_allocations=sector_allocations,
        cash_balance=cash_balance if cash_balance > 0 else None,
    )


def _build_current_position(
    db: Database,
    symbol: str,
    market_type: MarketType,
    current_prices: dict[tuple[str, MarketType], float],
    portfolio_context: PortfolioContext | None,
) -> CurrentPositionInfo | None:
    """Build current position info for the target symbol."""
    pos = db.get_position(symbol, market_type)
    if pos is None or abs(pos.cached_quantity) < ZERO_THRESHOLD:
        return None

    key = (symbol, market_type)
    price = current_prices.get(key, pos.cached_avg_cost)
    mv = pos.cached_quantity * price
    cost_basis = pos.cached_quantity * pos.cached_avg_cost
    pnl_pct = (mv - cost_basis) / cost_basis * 100 if cost_basis > ZERO_THRESHOLD else 0

    total_mv = portfolio_context.total_market_value if portfolio_context else mv
    alloc_pct = mv / total_mv * 100 if total_mv > 0 else 100.0

    # Holding days
    txns = db.get_transactions(symbol=symbol, market_type=market_type)
    buy_txns = [t for t in txns if t.action.value == "buy"]
    holding_days = None
    if buy_txns:
        first_buy = min(t.executed_at for t in buy_txns)
        holding_days = (date.today() - first_buy.date()).days

    return CurrentPositionInfo(
        symbol=symbol,
        quantity=pos.cached_quantity,
        avg_cost=pos.cached_avg_cost,
        market_value=round(mv, 2),
        unrealized_pnl_pct=round(pnl_pct, 1),
        allocation_pct=round(alloc_pct, 1),
        holding_days=holding_days,
    )


def _get_thesis(db: Database, symbol: str) -> str | None:
    """Get the original buy thesis from journal."""
    entries = db.get_journal_entries(symbol=symbol, limit=50)
    buy_entries = [e for e in entries if e.decision_type and e.decision_type.value == "buy"]
    if buy_entries:
        return buy_entries[-1].content
    return None
