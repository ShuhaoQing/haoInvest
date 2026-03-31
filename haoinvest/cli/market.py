"""CLI commands for market data queries."""

from datetime import date, timedelta
from typing import Optional

import typer

from ..market import get_provider
from ..models import MarketType
from .formatters import error_output, json_output, kv_output, tsv_output

app = typer.Typer(help="Market data — quotes, history, basic info.")


def _detect_market_type(symbol: str) -> MarketType:
    """Auto-detect market type from symbol format."""
    if symbol.isdigit() and len(symbol) == 6:
        return MarketType.A_SHARE
    upper = symbol.upper()
    if "_USDT" in upper or upper in ("BTC", "ETH", "SOL", "BNB", "DOGE", "XRP"):
        return MarketType.CRYPTO
    return MarketType.US


@app.command()
def quote(
    symbol: str = typer.Argument(help="Stock/crypto symbol, e.g. 600519, BTC_USDT, AAPL"),
    market_type: Optional[str] = typer.Option(None, "--market-type", "-m", help="Override: a_share, crypto, us"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get current price and basic info for a symbol."""
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    try:
        provider = get_provider(mt)
        price = provider.get_current_price(symbol)
        info = provider.get_basic_info(symbol)
    except (ValueError, RuntimeError) as e:
        error_output(str(e))
        raise typer.Exit(1)

    result = {
        "Symbol": symbol,
        "Name": info.get("name", ""),
        "Price": price,
        "Currency": info.get("currency", ""),
        "Sector": info.get("sector", ""),
        "PE(TTM)": info.get("pe_ratio"),
        "PB": info.get("pb_ratio"),
        "MarketCap": info.get("total_market_cap"),
        "MarketType": mt.value,
    }

    if use_json:
        json_output(result)
    else:
        kv_output(result)


@app.command()
def history(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    start: Optional[str] = typer.Option(None, "--start", "-s", help="Start date YYYY-MM-DD (default: 30 days ago)"),
    end: Optional[str] = typer.Option(None, "--end", "-e", help="End date YYYY-MM-DD (default: today)"),
    market_type: Optional[str] = typer.Option(None, "--market-type", "-m", help="Override: a_share, crypto, us"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get daily OHLCV price history for a symbol."""
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=30)

    try:
        provider = get_provider(mt)
        bars = provider.get_price_history(symbol, start_date, end_date)
    except (ValueError, RuntimeError) as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(bars)
    else:
        tsv_output(bars, columns=["date", "open", "high", "low", "close", "volume"])
