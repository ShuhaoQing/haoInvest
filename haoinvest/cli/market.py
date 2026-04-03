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
    symbol: str = typer.Argument(
        help="Stock/crypto symbol(s), comma-separated for batch, e.g. 600519,000858"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get current price and basic info for symbol(s)."""
    symbol_list = [s.strip() for s in symbol.split(",")]

    if len(symbol_list) == 1:
        # Single symbol — kv_output (original behavior)
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
            "Name": info.name,
            "Price": price,
            "Currency": info.currency,
            "Sector": info.sector,
            "PE(TTM)": info.pe_ratio,
            "PB": info.pb_ratio,
            "MarketCap": info.total_market_cap,
            "MarketType": mt.value,
        }
        if use_json:
            json_output(result)
        else:
            kv_output(result)
    else:
        # Batch — tsv_output comparison table
        rows = []
        for s in symbol_list:
            mt = MarketType(market_type) if market_type else _detect_market_type(s)
            try:
                provider = get_provider(mt)
                price = provider.get_current_price(s)
                info = provider.get_basic_info(s)
                rows.append(
                    {
                        "Symbol": s,
                        "Name": info.name,
                        "Price": price,
                        "PE(TTM)": info.pe_ratio,
                        "PB": info.pb_ratio,
                        "Sector": info.sector,
                        "MarketCap": info.total_market_cap,
                    }
                )
            except (ValueError, RuntimeError) as e:
                rows.append({"Symbol": s, "Name": f"ERROR: {e}"})
        if use_json:
            json_output(rows)
        else:
            tsv_output(
                rows,
                columns=[
                    "Symbol",
                    "Name",
                    "Price",
                    "PE(TTM)",
                    "PB",
                    "Sector",
                    "MarketCap",
                ],
            )


@app.command()
def history(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    start: Optional[str] = typer.Option(
        None, "--start", "-s", help="Start date YYYY-MM-DD (default: 30 days ago)"
    ),
    end: Optional[str] = typer.Option(
        None, "--end", "-e", help="End date YYYY-MM-DD (default: today)"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
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
        tsv_output(
            bars, columns=["trade_date", "open", "high", "low", "close", "volume"]
        )


@app.command("sector-list")
def sector_list(
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """行业板块排行 — list all A-share industry sectors with performance."""
    from ..market.ashare_provider import AShareProvider

    try:
        rows = AShareProvider.get_sector_list()
    except Exception as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(rows)
    else:
        tsv_output(
            rows,
            columns=[
                "name",
                "change_pct",
                "total_market_cap",
                "turnover_rate",
                "rise_count",
                "fall_count",
            ],
        )


@app.command("sector")
def sector(
    name: str = typer.Argument(help="Sector name, e.g. 白酒, 银行, 半导体"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """行业板块成分股 — show constituents of a specific A-share sector."""
    from ..market.ashare_provider import AShareProvider

    try:
        rows = AShareProvider.get_sector_constituents(name)
    except Exception as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(rows)
    else:
        tsv_output(
            rows,
            columns=[
                "code",
                "name",
                "price",
                "change_pct",
                "pe_ratio",
                "pb_ratio",
                "total_market_cap",
            ],
        )
