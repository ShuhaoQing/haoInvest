"""CLI commands for stock and portfolio analysis."""

from datetime import date, timedelta
from typing import Optional

import typer

from ..analysis.fundamental import analyze_stock
from ..analysis.risk import calculate_risk_metrics, portfolio_correlation
from ..analysis.signals import aggregate_signals
from ..analysis.technical import analyze_technical
from ..analysis.volume import analyze_volume
from ..db import Database
from ..models import MarketType
from .formatters import error_output, json_output, kv_output
from .market import _detect_market_type

app = typer.Typer(help="Analysis — fundamental, risk, technical, volume, signals.")


def _init_db() -> Database:
    db = Database()
    db.init_schema()
    return db


def _ensure_prices_cached(
    db: Database, symbol: str, market_type: MarketType, start: date, end: date
) -> None:
    """Fetch and cache price history if not already present."""
    from ..market import get_provider

    existing = db.get_prices(symbol, market_type, start, end)
    if len(existing) > 10:
        return
    provider = get_provider(market_type)
    bars = provider.get_price_history(symbol, start, end)
    if bars:
        db.save_prices(bars)


@app.command()
def fundamental(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
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
        kv_output(
            {
                "Symbol": result.symbol,
                "Name": result.name,
                "Price": result.current_price,
                "PE(TTM)": result.pe_ratio,
                "PB": result.pb_ratio,
                "Sector": result.sector,
                "MarketCap": result.total_market_cap,
                "PE_Assessment": result.valuation.pe_assessment,
                "PB_Assessment": result.valuation.pb_assessment,
                "Overall": result.valuation.overall,
            }
        )


@app.command()
def risk(
    symbol: Optional[str] = typer.Option(
        None, "--symbol", "-s", help="Specific symbol (default: all holdings)"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Start date YYYY-MM-DD (default: 1 year ago)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="End date YYYY-MM-DD (default: today)"
    ),
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
        output = {"symbol": symbol, **result.model_dump()}
        if use_json:
            json_output(output)
        else:
            kv_output(output)
    else:
        # All holdings
        positions = db.get_positions(include_zero=False)
        if not positions:
            print("(no holdings)")
            return
        results = []
        for pos in positions:
            _ensure_prices_cached(db, pos.symbol, pos.market_type, start_date, end_date)
            metrics = calculate_risk_metrics(
                db, pos.symbol, pos.market_type, start_date, end_date
            )
            results.append({"symbol": pos.symbol, **metrics.model_dump()})
        if use_json:
            json_output(results)
        else:
            for r in results:
                kv_output(r)
                print()


@app.command()
def correlation(
    symbols: str = typer.Argument(help="Comma-separated symbols, e.g. 600519,000001"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override market type for all symbols"
    ),
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


@app.command()
def technical(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Start date YYYY-MM-DD (default: 1 year ago)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="End date YYYY-MM-DD (default: today)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Add Chinese explanations for learning"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Technical indicators — MA, MACD, RSI, Bollinger Bands."""
    db = _init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    _ensure_prices_cached(db, symbol, mt, start_date, end_date)
    result = analyze_technical(db, symbol, mt, start_date, end_date, verbose=verbose)

    if use_json:
        json_output(result)
    else:
        output = {"symbol": result.symbol, "date": str(result.latest_date)}
        if result.message:
            output["message"] = result.message
        else:
            ma = result.moving_averages
            output.update(
                {
                    "close": result.latest_close,
                    "SMA5": ma.sma_5,
                    "SMA10": ma.sma_10,
                    "SMA20": ma.sma_20,
                    "SMA60": ma.sma_60,
                    "EMA12": ma.ema_12,
                    "EMA26": ma.ema_26,
                    "MA_Trend": ma.trend,
                }
            )
            if verbose and ma.explanation:
                output["MA_Explain"] = ma.explanation
            output.update(
                {
                    "MACD": result.macd.macd_line,
                    "Signal": result.macd.signal_line,
                    "Histogram": result.macd.histogram,
                    "MACD_Signal": result.macd.signal,
                }
            )
            if verbose and result.macd.explanation:
                output["MACD_Explain"] = result.macd.explanation
            output.update(
                {
                    "RSI": result.rsi.rsi,
                    "RSI_Assessment": result.rsi.assessment,
                }
            )
            if verbose and result.rsi.explanation:
                output["RSI_Explain"] = result.rsi.explanation
            bb = result.bollinger
            output.update(
                {
                    "BB_Upper": bb.upper,
                    "BB_Middle": bb.middle,
                    "BB_Lower": bb.lower,
                    "BB_Bandwidth%": bb.bandwidth_pct,
                    "BB_Position": bb.position,
                }
            )
            if verbose and bb.explanation:
                output["BB_Explain"] = bb.explanation
        kv_output(output)


@app.command()
def volume(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Start date YYYY-MM-DD (default: 1 year ago)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="End date YYYY-MM-DD (default: today)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Add Chinese explanations for learning"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Volume analysis — anomaly detection, turnover ratio."""
    db = _init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    _ensure_prices_cached(db, symbol, mt, start_date, end_date)
    result = analyze_volume(db, symbol, mt, start_date, end_date, verbose=verbose)

    if use_json:
        json_output(result)
    else:
        output = {"symbol": result.symbol}
        if result.message:
            output["message"] = result.message
        else:
            output.update(
                {
                    "latest_volume": result.latest_volume,
                    "avg_volume_20d": result.avg_volume_20d,
                    "volume_ratio": result.volume_ratio,
                    "is_anomaly": result.is_anomaly,
                    "assessment": result.assessment,
                }
            )
            if verbose and result.explanation:
                output["explanation"] = result.explanation
        kv_output(output)


@app.command()
def signals(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    start: Optional[str] = typer.Option(
        None, "--start", help="Start date YYYY-MM-DD (default: 1 year ago)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", help="End date YYYY-MM-DD (default: today)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Add Chinese explanations for learning"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Signal summary — aggregated technical view."""
    db = _init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    _ensure_prices_cached(db, symbol, mt, start_date, end_date)
    result = aggregate_signals(db, symbol, mt, start_date, end_date, verbose=verbose)

    if use_json:
        json_output(result)
    else:
        output = {
            "symbol": result.symbol,
            "overall_signal": result.overall_signal,
            "confidence": result.confidence,
            "bullish": result.bullish_count,
            "bearish": result.bearish_count,
            "neutral": result.neutral_count,
        }
        for i, detail in enumerate(result.details):
            output[f"indicator_{i + 1}"] = detail
        kv_output(output)
        if verbose and result.explanation:
            print(result.explanation)
