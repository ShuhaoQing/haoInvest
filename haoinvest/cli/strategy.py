"""CLI commands for portfolio optimization and rebalancing."""

import json
from datetime import date, timedelta
from typing import Optional

import typer

from ..db import Database
from ..market import get_provider
from ..models import MarketType
from ..strategy.optimizer import suggest_allocation
from ..strategy.rebalance import calculate_rebalance
from .formatters import error_output, json_output, kv_output, tsv_output
from .market import _detect_market_type

app = typer.Typer(help="Strategy — optimize allocation, rebalance.")


def _init_db() -> Database:
    db = Database()
    db.init_schema()
    return db


def _ensure_prices_cached(db: Database, symbol: str, market_type: MarketType, start: date, end: date) -> None:
    """Fetch and cache price history if not already present."""
    existing = db.get_prices(symbol, market_type, start, end)
    if len(existing) > 10:
        return
    provider = get_provider(market_type)
    bars = provider.get_price_history(symbol, start, end)
    if bars:
        db.save_prices(bars)


@app.command()
def optimize(
    method: str = typer.Option("risk_parity", "--method", help="equal_weight, risk_parity, or min_volatility"),
    symbols: Optional[str] = typer.Option(None, "--symbols", "-s", help="Comma-separated symbols (default: all holdings)"),
    start: Optional[str] = typer.Option(None, "--start", help="Price history start date"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Suggest optimal portfolio allocation."""
    db = _init_db()
    end_date = date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",")]
        pairs = [(s, _detect_market_type(s)) for s in symbol_list]
    else:
        positions = db.get_positions(include_zero=False)
        if not positions:
            print("(no holdings)")
            return
        pairs = [(p.symbol, p.market_type) for p in positions]

    # Ensure price data cached
    for symbol, mt in pairs:
        _ensure_prices_cached(db, symbol, mt, start_date, end_date)

    try:
        result = suggest_allocation(db, pairs, method=method, start_date=start_date, end_date=end_date)
    except ValueError as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(result)
    else:
        kv_output({"Method": result.method, "Explanation": result.explanation})
        print()
        rows = [{"Symbol": s, "Weight%": round(w * 100, 2)} for s, w in result.weights.items()]
        tsv_output(rows, columns=["Symbol", "Weight%"])


@app.command()
def rebalance(
    target: Optional[str] = typer.Option(None, "--target", "-t", help='Target weights JSON, e.g. \'{"600519": 0.5, "BTC_USDT": 0.5}\''),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Calculate rebalance trades to reach target allocation."""
    db = _init_db()

    if target is None:
        error_output("--target is required. Provide target weights as JSON.")
        raise typer.Exit(1)

    try:
        target_weights = json.loads(target)
    except json.JSONDecodeError as e:
        error_output(f"Invalid JSON for --target: {e}")
        raise typer.Exit(1)

    # Fetch current prices for all symbols involved
    all_symbols = set(target_weights.keys())
    positions = db.get_positions(include_zero=False)
    for p in positions:
        all_symbols.add(p.symbol)

    current_prices: dict[str, float] = {}
    for symbol in all_symbols:
        mt = _detect_market_type(symbol)
        try:
            provider = get_provider(mt)
            current_prices[symbol] = provider.get_current_price(symbol)
        except Exception as e:
            error_output(f"Failed to get price for {symbol}: {e}")

    trades = calculate_rebalance(db, target_weights, current_prices)

    if not trades:
        print("(no rebalance needed)")
        return

    if use_json:
        json_output(trades)
    else:
        tsv_output(
            trades,
            columns=["symbol", "action", "quantity", "price", "current_weight", "target_weight", "trade_value"],
        )
