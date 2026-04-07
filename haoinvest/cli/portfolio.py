"""CLI commands for portfolio management."""

from datetime import datetime
from typing import Optional

import typer

from ..market import get_provider
from ..models import MarketType, Transaction, TransactionAction
from ..portfolio.manager import PortfolioManager
from ..portfolio.returns import portfolio_returns_summary, realized_pnl, unrealized_pnl
from ._shared import init_db
from .formatters import error_output, json_output, kv_output, tsv_output
from .market import _detect_market_type

app = typer.Typer(help="Portfolio — holdings, trades, returns.")


@app.command("list")
def list_holdings(
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View all current holdings."""
    db = init_db()
    pm = PortfolioManager(db)
    summary = pm.get_portfolio_summary()

    if not summary:
        print("(no holdings)")
        return

    if use_json:
        json_output(summary)
    else:
        tsv_output(
            summary,
            columns=[
                "symbol",
                "market_type",
                "quantity",
                "avg_cost",
                "position_cost",
                "allocation_pct",
                "currency",
            ],
        )


@app.command("add-trade")
def add_trade(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    action: str = typer.Argument(
        help="buy, sell, dividend, split, transfer_in, transfer_out"
    ),
    quantity: float = typer.Argument(help="Number of units"),
    price: float = typer.Argument(help="Price per unit"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    fee: float = typer.Option(0.0, "--fee", help="Commission/fee"),
    tax: float = typer.Option(0.0, "--tax", help="Stamp tax"),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Date YYYY-MM-DD (default: now)"
    ),
    currency: str = typer.Option("CNY", "--currency", help="Currency code"),
    note: str = typer.Option("", "--note", "-n", help="Trade note"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Record a trade transaction."""
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)

    try:
        txn_action = TransactionAction(action)
    except ValueError:
        error_output(
            f"Invalid action: {action}. Use: buy, sell, dividend, split, transfer_in, transfer_out"
        )
        raise typer.Exit(1)

    executed_at = datetime.fromisoformat(date) if date else datetime.now()

    txn = Transaction(
        symbol=symbol,
        market_type=mt,
        action=txn_action,
        quantity=quantity,
        price=price,
        fee=fee,
        tax=tax,
        currency=currency,
        executed_at=executed_at,
        note=note,
    )

    db = init_db()

    # Advisory guardrail check before trade
    try:
        from ..guardrails.rules import validate_trade as _validate

        _prices: dict[tuple[str, MarketType], float] = {}
        for pos in db.get_positions(include_zero=False):
            try:
                _provider = get_provider(pos.market_type)
                _prices[(pos.symbol, pos.market_type)] = _provider.get_current_price(
                    pos.symbol
                )
            except Exception:
                pass
        _prices[(symbol, mt)] = price
        _violations = _validate(db, symbol, mt, action, quantity, price, _prices)
        for _v in _violations:
            print(f"  ⚠ {_v.message}", file=__import__("sys").stderr)
    except Exception:
        pass  # guardrails are advisory, never block

    pm = PortfolioManager(db)
    txn_id = pm.add_trade(txn)

    result = {
        "transaction_id": txn_id,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
    }

    if use_json:
        json_output(result)
    else:
        kv_output(result)


@app.command()
def returns(
    symbol: Optional[str] = typer.Option(
        None, "--symbol", "-s", help="Specific symbol (default: all holdings)"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View returns — unrealized P&L for holdings."""
    db = init_db()

    if symbol:
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        try:
            provider = get_provider(mt)
            price = provider.get_current_price(symbol)
        except Exception as e:
            error_output(f"Failed to get price for {symbol}: {e}")
            raise typer.Exit(1)

        upnl = unrealized_pnl(db, symbol, mt, price)
        rpnl = realized_pnl(db, symbol, mt)
        output = {"symbol": symbol, **upnl.model_dump(), **rpnl.model_dump()}

        if use_json:
            json_output(output)
        else:
            kv_output(output)
    else:
        # All holdings — fetch current prices
        positions = db.get_positions(include_zero=False)
        if not positions:
            print("(no holdings)")
            return

        prices: dict[tuple[str, MarketType], float] = {}
        for pos in positions:
            try:
                provider = get_provider(pos.market_type)
                prices[(pos.symbol, pos.market_type)] = provider.get_current_price(
                    pos.symbol
                )
            except Exception as e:
                error_output(f"Failed to get price for {pos.symbol}: {e}")

        summary = portfolio_returns_summary(db, prices)

        if use_json:
            json_output(summary)
        else:
            kv_output(
                {
                    "TotalMarketValue": summary.total_market_value,
                    "TotalCostBasis": summary.total_cost_basis,
                    "TotalUnrealizedPnL": summary.total_unrealized_pnl,
                    "TotalUnrealizedPnL%": summary.total_unrealized_pnl_pct,
                }
            )
            print()
            tsv_output(
                summary.holdings,
                columns=[
                    "symbol",
                    "market_type",
                    "quantity",
                    "avg_cost",
                    "current_price",
                    "unrealized_pnl",
                    "unrealized_pnl_pct",
                ],
            )
