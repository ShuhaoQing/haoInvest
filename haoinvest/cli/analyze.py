"""CLI commands for stock and portfolio analysis."""

from datetime import date, timedelta
from typing import Optional

import typer

from ..analysis.fundamental import analyze_stock
from ..analysis.report import full_stock_report
from ..analysis.risk import calculate_risk_metrics, portfolio_correlation
from ..db import Database
from ..models import MarketType
from .formatters import error_output, json_output, kv_output
from .market import _detect_market_type

app = typer.Typer(help="Analysis — fundamental, risk, correlation.")


def _init_db() -> Database:
    db = Database()
    db.init_schema()
    return db


def _ensure_prices_cached(db: Database, symbol: str, market_type: MarketType, start: date, end: date) -> None:
    """Fetch and cache price history if not already present."""
    from ..market import get_provider

    existing = db.get_prices(symbol, market_type, start, end)
    if len(existing) > 10:
        return
    provider = get_provider(market_type)
    bars = provider.get_price_history(symbol, start, end)
    if bars:
        db.save_prices(symbol, market_type, bars)


@app.command()
def fundamental(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    market_type: Optional[str] = typer.Option(None, "--market-type", "-m", help="Override: a_share, crypto, us"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Fundamental analysis — PE/PB, valuation assessment."""
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    try:
        result = analyze_stock(symbol, mt)
    except (ValueError, RuntimeError) as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(result)
    else:
        kv_output({
            "Symbol": result["symbol"],
            "Name": result["name"],
            "Price": result["current_price"],
            "PE(TTM)": result["pe_ratio"],
            "PB": result["pb_ratio"],
            "Sector": result["sector"],
            "MarketCap": result["total_market_cap"],
            "PE_Assessment": result["valuation"]["pe_assessment"],
            "PB_Assessment": result["valuation"]["pb_assessment"],
            "Overall": result["valuation"]["overall"],
        })


@app.command()
def risk(
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Specific symbol (default: all holdings)"),
    market_type: Optional[str] = typer.Option(None, "--market-type", "-m", help="Override: a_share, crypto, us"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date YYYY-MM-DD (default: 1 year ago)"),
    end: Optional[str] = typer.Option(None, "--end", help="End date YYYY-MM-DD (default: today)"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Risk metrics — volatility, drawdown, Sharpe ratio."""
    db = _init_db()
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    if symbol:
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        _ensure_prices_cached(db, symbol, mt, start_date, end_date)
        result = calculate_risk_metrics(db, symbol, mt, start_date, end_date)
        result["symbol"] = symbol
        if use_json:
            json_output(result)
        else:
            kv_output(result)
    else:
        # All holdings
        positions = db.get_positions(include_zero=False)
        if not positions:
            print("(no holdings)")
            return
        results = []
        for pos in positions:
            _ensure_prices_cached(db, pos.symbol, pos.market_type, start_date, end_date)
            metrics = calculate_risk_metrics(db, pos.symbol, pos.market_type, start_date, end_date)
            metrics["symbol"] = pos.symbol
            results.append(metrics)
        if use_json:
            json_output(results)
        else:
            for r in results:
                kv_output(r)
                print()


@app.command()
def correlation(
    symbols: str = typer.Argument(help="Comma-separated symbols, e.g. 600519,000001"),
    market_type: Optional[str] = typer.Option(None, "--market-type", "-m", help="Override market type for all symbols"),
    start: Optional[str] = typer.Option(None, "--start", help="Start date YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, "--end", help="End date YYYY-MM-DD"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Correlation matrix between assets."""
    db = _init_db()
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    symbol_list = [s.strip() for s in symbols.split(",")]
    pairs = []
    for s in symbol_list:
        mt = MarketType(market_type) if market_type else _detect_market_type(s)
        _ensure_prices_cached(db, s, mt, start_date, end_date)
        pairs.append((s, mt))

    result = portfolio_correlation(db, pairs, start_date, end_date)

    if use_json:
        json_output(result)
    else:
        matrix = result.get("matrix", {})
        if not matrix:
            print(result.get("message", "(no data)"))
            return
        syms = list(matrix.keys())
        print("\t" + "\t".join(syms))
        for s in syms:
            row = "\t".join(str(matrix[s].get(s2, "")) for s2 in syms)
            print(f"{s}\t{row}")
