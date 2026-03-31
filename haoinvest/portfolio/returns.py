"""Returns calculation: TWR, realized/unrealized P&L."""

from ..config import ZERO_THRESHOLD
from ..db import Database
from ..models import (
    HoldingSummary,
    MarketType,
    PortfolioSummary,
    RealizedPnL,
    TransactionAction,
    UnrealizedPnL,
)


def unrealized_pnl(
    db: Database, symbol: str, market_type: MarketType, current_price: float
) -> UnrealizedPnL:
    """Calculate unrealized P&L for a position."""
    pos = db.get_position(symbol, market_type)
    if pos is None or abs(pos.cached_quantity) < ZERO_THRESHOLD:
        return UnrealizedPnL(current_price=current_price)

    market_value = pos.cached_quantity * current_price
    cost_basis = pos.cached_quantity * pos.cached_avg_cost
    pnl = market_value - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

    # Sum all fees for this symbol
    txns = db.get_transactions(symbol=symbol, market_type=market_type)
    total_fees = sum(t.fee + t.tax for t in txns)

    return UnrealizedPnL(
        quantity=pos.cached_quantity,
        avg_cost=pos.cached_avg_cost,
        current_price=current_price,
        unrealized_pnl=round(pnl, 2),
        unrealized_pnl_pct=round(pnl_pct, 2),
        total_fees=round(total_fees, 2),
    )


def realized_pnl(db: Database, symbol: str, market_type: MarketType) -> RealizedPnL:
    """Calculate realized P&L from completed sell transactions.

    Uses weighted average cost at time of each sell.
    """
    txns = db.get_transactions(symbol=symbol, market_type=market_type)

    quantity = 0.0
    total_cost = 0.0
    realized = 0.0
    dividends = 0.0
    num_sells = 0

    for txn in txns:
        if txn.action == TransactionAction.BUY:
            total_cost += txn.quantity * txn.price + txn.fee + txn.tax
            quantity += txn.quantity

        elif txn.action == TransactionAction.SELL:
            if abs(quantity) < ZERO_THRESHOLD:
                continue
            avg_cost = total_cost / quantity
            sell_proceeds = txn.quantity * txn.price - txn.fee - txn.tax
            cost_of_sold = txn.quantity * avg_cost

            realized += sell_proceeds - cost_of_sold

            sell_ratio = min(txn.quantity / quantity, 1.0)
            total_cost *= 1 - sell_ratio
            quantity -= txn.quantity
            num_sells += 1

        elif txn.action == TransactionAction.DIVIDEND:
            dividends += (
                txn.quantity * txn.price
            )  # quantity=shares, price=dividend per share

        elif txn.action == TransactionAction.SPLIT:
            quantity *= txn.price

        elif txn.action == TransactionAction.TRANSFER_IN:
            total_cost += txn.quantity * txn.price
            quantity += txn.quantity

        elif txn.action == TransactionAction.TRANSFER_OUT:
            if abs(quantity) < ZERO_THRESHOLD:
                continue
            sell_ratio = min(txn.quantity / quantity, 1.0)
            total_cost *= 1 - sell_ratio
            quantity -= txn.quantity

    return RealizedPnL(
        total_realized_pnl=round(realized, 2),
        total_dividends=round(dividends, 2),
        num_sell_trades=num_sells,
    )


def portfolio_returns_summary(
    db: Database,
    current_prices: dict[tuple[str, MarketType], float],
) -> PortfolioSummary:
    """Calculate overall portfolio returns.

    Args:
        current_prices: mapping of (symbol, market_type) -> current_price
    """
    positions = db.get_positions(include_zero=False)

    total_market_value = 0.0
    total_cost_basis = 0.0
    holdings = []

    for pos in positions:
        key = (pos.symbol, pos.market_type)
        price = current_prices.get(key, pos.cached_avg_cost)

        mv = pos.cached_quantity * price
        cb = pos.cached_quantity * pos.cached_avg_cost
        pnl = mv - cb
        pnl_pct = (pnl / cb * 100) if cb > 0 else 0

        total_market_value += mv
        total_cost_basis += cb

        holdings.append(
            HoldingSummary(
                symbol=pos.symbol,
                market_type=pos.market_type.value,
                quantity=pos.cached_quantity,
                avg_cost=pos.cached_avg_cost,
                current_price=price,
                market_value=round(mv, 2),
                cost_basis=round(cb, 2),
                unrealized_pnl=round(pnl, 2),
                unrealized_pnl_pct=round(pnl_pct, 2),
            )
        )

    total_pnl = total_market_value - total_cost_basis
    total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0

    return PortfolioSummary(
        total_market_value=round(total_market_value, 2),
        total_cost_basis=round(total_cost_basis, 2),
        total_unrealized_pnl=round(total_pnl, 2),
        total_unrealized_pnl_pct=round(total_pnl_pct, 2),
        holdings=holdings,
    )
