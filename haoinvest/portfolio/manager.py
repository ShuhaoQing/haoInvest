"""Portfolio management: add trades, view holdings, sync positions."""

from ..config import PRECISION, ZERO_THRESHOLD
from ..db import Database
from ..models import (
    HoldingSummary,
    MarketType,
    Position,
    Transaction,
    TransactionAction,
)


class PortfolioManager:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add_trade(self, txn: Transaction) -> int:
        """Record a trade and update cached position."""
        txn_id = self.db.add_transaction(txn)
        self._sync_position(txn.symbol, txn.market_type)
        return txn_id

    def get_holdings(self) -> list[Position]:
        """Get all non-zero positions."""
        return self.db.get_positions(include_zero=False)

    def get_holding(self, symbol: str, market_type: MarketType) -> Position | None:
        """Get a specific position."""
        pos = self.db.get_position(symbol, market_type)
        if pos and abs(pos.cached_quantity) < ZERO_THRESHOLD:
            return None
        return pos

    def rebuild_all_positions(self) -> None:
        """Rebuild all cached positions from transactions (source of truth)."""
        all_txns = self.db.get_transactions()
        # Group by (symbol, market_type)
        groups: dict[tuple[str, str], list[Transaction]] = {}
        for txn in all_txns:
            key = (txn.symbol, txn.market_type.value)
            groups.setdefault(key, []).append(txn)

        for (symbol, mt_val), txns in groups.items():
            market_type = MarketType(mt_val)
            quantity, avg_cost = _compute_position(txns, market_type)
            self.db.upsert_position(
                Position(
                    symbol=symbol,
                    market_type=market_type,
                    currency=txns[0].currency,
                    cached_quantity=quantity,
                    cached_avg_cost=avg_cost,
                )
            )

    def get_total_cost(self) -> float:
        """Total cost basis of all holdings in their local currencies."""
        holdings = self.get_holdings()
        return sum(h.cached_quantity * h.cached_avg_cost for h in holdings)

    def get_portfolio_summary(self) -> list[HoldingSummary]:
        """Get a summary of all holdings with allocation percentages."""
        holdings = self.get_holdings()
        total_cost = sum(h.cached_quantity * h.cached_avg_cost for h in holdings)

        result = []
        for h in holdings:
            position_cost = h.cached_quantity * h.cached_avg_cost
            result.append(
                HoldingSummary(
                    symbol=h.symbol,
                    market_type=h.market_type.value,
                    quantity=h.cached_quantity,
                    avg_cost=h.cached_avg_cost,
                    position_cost=round(position_cost, 2),
                    allocation_pct=round(position_cost / total_cost * 100, 2)
                    if total_cost > 0
                    else 0,
                    currency=h.currency,
                )
            )
        return result

    def _sync_position(self, symbol: str, market_type: MarketType) -> None:
        """Recalculate cached position for a symbol from transactions."""
        txns = self.db.get_transactions(symbol=symbol, market_type=market_type)
        quantity, avg_cost = _compute_position(txns, market_type)

        currency = txns[0].currency if txns else "CNY"
        self.db.upsert_position(
            Position(
                symbol=symbol,
                market_type=market_type,
                currency=currency,
                cached_quantity=quantity,
                cached_avg_cost=avg_cost,
            )
        )


def _compute_position(
    txns: list[Transaction], market_type: MarketType
) -> tuple[float, float]:
    """Compute quantity and average cost from a list of transactions.

    Uses weighted average cost method for buys.
    Sells reduce quantity but don't change avg_cost.
    """
    quantity = 0.0
    total_cost = 0.0  # total cost basis = quantity * avg_cost
    precision = PRECISION.get(market_type.value, {"price": 2, "quantity": 2})

    for txn in txns:
        if txn.action == TransactionAction.BUY:
            cost_of_purchase = txn.quantity * txn.price + txn.fee + txn.tax
            total_cost += cost_of_purchase
            quantity += txn.quantity

        elif txn.action == TransactionAction.SELL:
            if abs(quantity) < ZERO_THRESHOLD:
                continue
            # Reduce quantity, reduce total_cost proportionally
            sell_ratio = min(txn.quantity / quantity, 1.0)
            total_cost *= 1 - sell_ratio
            quantity -= txn.quantity

        elif txn.action == TransactionAction.TRANSFER_IN:
            total_cost += txn.quantity * txn.price
            quantity += txn.quantity

        elif txn.action == TransactionAction.TRANSFER_OUT:
            if abs(quantity) < ZERO_THRESHOLD:
                continue
            sell_ratio = min(txn.quantity / quantity, 1.0)
            total_cost *= 1 - sell_ratio
            quantity -= txn.quantity

        elif txn.action == TransactionAction.SPLIT:
            # price field stores the split ratio (e.g., 2.0 for 2:1 split)
            quantity *= txn.price
            # avg_cost adjusts inversely
            # total_cost stays the same

        elif txn.action == TransactionAction.DIVIDEND:
            # Dividends don't change quantity or avg_cost
            # They are tracked as realized income separately
            pass

    # Clean up near-zero
    if abs(quantity) < ZERO_THRESHOLD:
        quantity = 0.0
        total_cost = 0.0

    avg_cost = total_cost / quantity if quantity > 0 else 0.0
    avg_cost = round(avg_cost, precision["price"])
    quantity = round(quantity, precision["quantity"])

    return quantity, avg_cost
