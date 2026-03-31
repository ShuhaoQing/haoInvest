"""Rebalance calculation: compare current vs target allocation."""

from ..db import Database
from ..models import MarketType, RebalanceTrade


def calculate_rebalance(
    db: Database,
    target_weights: dict[str, float],
    current_prices: dict[str, float],
    total_portfolio_value: float | None = None,
) -> list[RebalanceTrade]:
    """Calculate rebalance trades to move from current to target allocation.

    Args:
        target_weights: {symbol: target_weight} where weights sum to 1.0
        current_prices: {symbol: current_price}
        total_portfolio_value: If provided, use this as total value.
            Otherwise, calculate from current positions.
    """
    positions = db.get_positions(include_zero=False)
    pos_map = {p.symbol: p for p in positions}

    # Calculate current portfolio value
    if total_portfolio_value is None:
        total_portfolio_value = sum(
            pos_map[s].cached_quantity * current_prices.get(s, pos_map[s].cached_avg_cost)
            for s in pos_map
        )

    if total_portfolio_value <= 0:
        return []

    # Calculate current weights
    current_weights: dict[str, float] = {}
    for symbol, pos in pos_map.items():
        price = current_prices.get(symbol, pos.cached_avg_cost)
        current_weights[symbol] = (pos.cached_quantity * price) / total_portfolio_value

    # Calculate required trades
    trades = []
    all_symbols = set(list(target_weights.keys()) + list(current_weights.keys()))

    for symbol in sorted(all_symbols):
        current_w = current_weights.get(symbol, 0.0)
        target_w = target_weights.get(symbol, 0.0)
        diff_w = target_w - current_w

        if abs(diff_w) < 0.005:  # Skip tiny adjustments (< 0.5%)
            continue

        price = current_prices.get(symbol)
        if price is None or price <= 0:
            trades.append(RebalanceTrade(
                symbol=symbol,
                action="buy" if diff_w > 0 else "sell",
                current_weight=round(current_w * 100, 2),
                target_weight=round(target_w * 100, 2),
                trade_value=round(abs(diff_w) * total_portfolio_value, 2),
                note="需要提供当前价格才能计算具体数量",
            ))
            continue

        trade_value = abs(diff_w) * total_portfolio_value
        quantity = trade_value / price

        trades.append(RebalanceTrade(
            symbol=symbol,
            action="buy" if diff_w > 0 else "sell",
            quantity=round(quantity, 4),
            price=price,
            current_weight=round(current_w * 100, 2),
            target_weight=round(target_w * 100, 2),
            trade_value=round(trade_value, 2),
        ))

    return trades
