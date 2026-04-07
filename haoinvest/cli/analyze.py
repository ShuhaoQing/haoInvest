"""CLI commands for stock and portfolio analysis."""

from datetime import date, timedelta
from typing import Optional

import typer

from ..analysis.cache import ensure_prices_cached
from ..analysis.fundamental import analyze_stock
from ..analysis.registry import (
    MODULES,
    any_needs_prices,
    max_lookback_days,
    parse_modules,
)
from ..analysis.risk import calculate_risk_metrics, portfolio_correlation
from ..analysis.signals import aggregate_signals
from ..analysis.technical import analyze_technical, analyze_technical_multi
from ..analysis.volume import analyze_volume
from ..models import MarketType
from ._shared import init_db
from .formatters import (
    error_output,
    json_output,
    kv_output,
    section_header,
    timeframe_section,
    tsv_output,
)
from .market import _detect_market_type

app = typer.Typer(help="Analysis — fundamental, risk, technical, volume, signals.")


@app.command()
def fundamental(
    symbol: str = typer.Argument(
        help="Stock/crypto symbol(s), comma-separated for batch"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show financial health assessment"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Fundamental analysis — valuation, financial health, growth metrics."""
    symbol_list = [s.strip() for s in symbol.split(",")]

    if len(symbol_list) == 1:
        # Single symbol — kv_output
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        try:
            result = analyze_stock(symbol, mt)
        except (ValueError, RuntimeError) as e:
            error_output(str(e))
            raise typer.Exit(1)

        if use_json:
            json_output(result)
        else:
            output: dict = {
                "Symbol": result.symbol,
                "Name": result.name,
                "Price": result.current_price,
                "PE(TTM)": result.pe_ratio,
                "PB": result.pb_ratio,
                "Sector": result.sector,
                "Industry": result.industry,
                "MarketCap": result.total_market_cap,
                "ROE(%)": result.roe,
                "ROA(%)": result.roa,
                "DebtToEquity": result.debt_to_equity,
                "RevenueGrowth": result.revenue_growth,
                "ProfitMargin": result.profit_margin,
                "GrossMargin": result.gross_margin,
                "OperatingMargin": result.operating_margin,
                "CurrentRatio": result.current_ratio,
                "FreeCashFlow": result.free_cash_flow,
                "PEG": result.peg_ratio,
                "PE_Assessment": result.valuation.pe_assessment,
                "PB_Assessment": result.valuation.pb_assessment,
                "Overall_Valuation": result.valuation.overall,
            }
            if verbose:
                fh = result.financial_health
                output.update(
                    {
                        "Profitability": fh.profitability,
                        "Growth": fh.growth,
                        "Leverage": fh.leverage,
                        "CashFlow": fh.cash_flow,
                        "FinancialHealth": fh.overall,
                    }
                )
            kv_output(output)
    else:
        # Batch — tsv comparison table
        rows = []
        for s in symbol_list:
            mt = MarketType(market_type) if market_type else _detect_market_type(s)
            try:
                r = analyze_stock(s, mt)
                row: dict = {
                    "Symbol": r.symbol,
                    "Name": r.name,
                    "Price": r.current_price,
                    "PE": r.pe_ratio,
                    "PB": r.pb_ratio,
                    "ROE(%)": r.roe,
                    "Growth": r.revenue_growth,
                    "Margin": r.profit_margin,
                    "D/E": r.debt_to_equity,
                    "Valuation": r.valuation.overall,
                }
                if verbose:
                    row["Health"] = r.financial_health.overall
                rows.append(row)
            except (ValueError, RuntimeError) as e:
                rows.append({"Symbol": s, "Name": f"ERROR: {e}"})
        if use_json:
            json_output(rows)
        else:
            columns = [
                "Symbol",
                "Name",
                "Price",
                "PE",
                "PB",
                "ROE(%)",
                "Growth",
                "Margin",
                "D/E",
                "Valuation",
            ]
            if verbose:
                columns.append("Health")
            tsv_output(rows, columns=columns)


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
    """Risk metrics — volatility, drawdown, Sharpe ratio, Sortino ratio."""
    db = init_db()
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    if symbol:
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        ensure_prices_cached(db, symbol, mt, start_date, end_date)
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
            ensure_prices_cached(db, pos.symbol, pos.market_type, start_date, end_date)
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
    db = init_db()
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    symbol_list = [s.strip() for s in symbols.split(",")]
    pairs = []
    for s in symbol_list:
        mt = MarketType(market_type) if market_type else _detect_market_type(s)
        ensure_prices_cached(db, s, mt, start_date, end_date)
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
    symbol: str = typer.Argument(
        help="Stock/crypto symbol(s), comma-separated for batch"
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
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Add Chinese explanations for learning"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Technical indicators — MA, MACD, RSI, Bollinger Bands (daily/weekly/monthly)."""
    db = init_db()
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=1095)
    symbol_list = [s.strip() for s in symbol.split(",")]

    if len(symbol_list) == 1:
        # Single symbol — multi-timeframe output
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        ensure_prices_cached(db, symbol, mt, start_date, end_date)
        multi = analyze_technical_multi(
            db, symbol, mt, start_date, end_date, verbose=verbose
        )

        if use_json:
            json_output(multi)
        else:
            # Monthly and weekly: compact timeframe sections
            if multi.monthly:
                timeframe_section("月线技术指标 (Monthly)", multi.monthly, verbose)
            if multi.weekly:
                timeframe_section("周线技术指标 (Weekly)", multi.weekly, verbose)

            # Daily: preserve original kv_output format for backward compatibility
            result = multi.daily
            print()  # blank line before daily section
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
    else:
        # Batch — tsv comparison table with key indicators
        rows = []
        for s in symbol_list:
            mt = MarketType(market_type) if market_type else _detect_market_type(s)
            ensure_prices_cached(db, s, mt, start_date, end_date)
            result = analyze_technical(db, s, mt, start_date, end_date)
            if result.message:
                rows.append({"Symbol": s, "Trend": result.message})
            else:
                rows.append(
                    {
                        "Symbol": s,
                        "Close": result.latest_close,
                        "Trend": result.moving_averages.trend,
                        "MACD": result.macd.signal,
                        "RSI": result.rsi.rsi,
                        "RSI_Zone": result.rsi.assessment,
                        "BB_Pos": result.bollinger.position,
                    }
                )
        if use_json:
            json_output(rows)
        else:
            tsv_output(
                rows,
                columns=[
                    "Symbol",
                    "Close",
                    "Trend",
                    "MACD",
                    "RSI",
                    "RSI_Zone",
                    "BB_Pos",
                ],
            )


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
    db = init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    ensure_prices_cached(db, symbol, mt, start_date, end_date)
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
    db = init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    ensure_prices_cached(db, symbol, mt, start_date, end_date)
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


@app.command()
def peer(
    symbol: str = typer.Argument(help="Stock symbol to find peers for"),
    top_n: int = typer.Option(10, "--top", "-n", help="Number of peers to show"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """同行业对比 — compare a stock with its sector peers."""
    from ..analysis.peer import find_peers

    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    try:
        rows = find_peers(symbol, mt, top_n=top_n)
    except (ValueError, RuntimeError) as e:
        error_output(str(e))
        raise typer.Exit(1)

    # Check for message-only results (errors/unsupported)
    if rows and "message" in rows[0]:
        print(rows[0]["message"])
        return

    if use_json:
        json_output(rows)
    else:
        tsv_output(
            rows,
            columns=["Symbol", "Name", "Price", "Change%", "PE", "PB", "MarketCap"],
        )


@app.command()
def report(
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
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """综合分析报告 — full report with buy-readiness checklist."""
    from ..analysis.report import full_stock_report

    db = init_db()
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    end_date = date.fromisoformat(end) if end else date.today()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=365)

    ensure_prices_cached(db, symbol, mt, start_date, end_date)

    try:
        r = full_stock_report(
            db, symbol, mt, start_date, end_date, include_technical=True
        )
    except (ValueError, RuntimeError) as e:
        error_output(str(e))
        raise typer.Exit(1)

    if use_json:
        json_output(r)
    else:
        # Section: Basic Info
        print("=== 基本信息 ===")
        kv_output(
            {
                "Symbol": r.symbol,
                "Name": r.name,
                "Price": r.current_price,
                "Sector": r.sector,
                "Industry": r.industry,
                "MarketCap": r.total_market_cap,
            }
        )
        # Section: Valuation
        print("\n=== 估值分析 ===")
        kv_output(
            {
                "PE(TTM)": r.pe_ratio,
                "PB": r.pb_ratio,
                "PEG": r.peg_ratio,
                "PE_Assessment": r.valuation.pe_assessment,
                "PB_Assessment": r.valuation.pb_assessment,
                "Overall": r.valuation.overall,
            }
        )
        # Section: Financial Health
        print("\n=== 财务健康 ===")
        kv_output(
            {
                "ROE(%)": r.roe,
                "ROA(%)": r.roa,
                "DebtToEquity": r.debt_to_equity,
                "RevenueGrowth": r.revenue_growth,
                "ProfitMargin": r.profit_margin,
                "GrossMargin": r.gross_margin,
                "CurrentRatio": r.current_ratio,
                "FreeCashFlow": r.free_cash_flow,
            }
        )
        if r.financial_health:
            kv_output(
                {
                    "Profitability": r.financial_health.profitability,
                    "Growth": r.financial_health.growth,
                    "Leverage": r.financial_health.leverage,
                    "CashFlow": r.financial_health.cash_flow,
                    "FinancialHealth": r.financial_health.overall,
                }
            )
        # Section: Risk
        print("\n=== 风险指标 ===")
        rm = r.risk_metrics
        kv_output(
            {
                "Volatility": rm.annualized_volatility,
                "MaxDrawdown%": rm.max_drawdown_pct,
                "Sharpe": rm.sharpe_ratio,
                "Sortino": rm.sortino_ratio,
                "TotalReturn%": rm.total_return_pct,
            }
        )
        # Section: Technical
        if r.signals:
            print("\n=== 技术面 ===")
            kv_output(
                {
                    "Signal": r.signals.overall_signal,
                    "Confidence": r.signals.confidence,
                    "Bullish": r.signals.bullish_count,
                    "Bearish": r.signals.bearish_count,
                }
            )
        # Section: Checklist
        if r.checklist:
            print("\n=== 买入准备度 ===")
            for item in r.checklist.items:
                print(f"  {item.dimension}: {item.score}/5 — {item.assessment}")
            print(f"  总分: {r.checklist.total_score}/{r.checklist.max_score}")
            print(f"  建议: {r.checklist.recommendation}")


@app.command()
def run(
    symbol: str = typer.Argument(help="Symbol(s), comma-separated for batch"),
    modules: str = typer.Option(
        "all",
        "--modules",
        help="Comma-separated: fundamental,technical,risk,volume,signals,peer,checklist",
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    start: Optional[str] = typer.Option(None, "--start", help="Start date YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, "--end", help="End date YYYY-MM-DD"),
    top_n: int = typer.Option(10, "--top-n", help="Number of peers (peer module)"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Add explanations for learning"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Composable analysis — choose which modules to run in a single call.

    Examples:
        analyze run 600519                              # all modules
        analyze run 600519 --modules fundamental,risk   # selective
        analyze run 600519,000858 --modules fundamental # batch
    """
    try:
        module_names = parse_modules(modules)
    except ValueError as e:
        error_output(str(e))
        raise typer.Exit(1)

    symbol_list = [s.strip() for s in symbol.split(",")]
    end_date = date.fromisoformat(end) if end else date.today()
    lookback = max_lookback_days(module_names)
    start_date = (
        date.fromisoformat(start) if start else end_date - timedelta(days=lookback)
    )

    db = init_db()
    needs_prices = any_needs_prices(module_names)
    is_batch = len(symbol_list) > 1

    # JSON accumulator for batch mode
    json_results: dict = {}

    for sym in symbol_list:
        mt = MarketType(market_type) if market_type else _detect_market_type(sym)

        if needs_prices:
            ensure_prices_cached(db, sym, mt, start_date, end_date)

        results: dict = {}
        for name in module_names:
            if name == "checklist":
                continue  # post-processing, handled below
            mod = MODULES[name]
            try:
                results[name] = mod.runner(
                    db,
                    sym,
                    mt,
                    start_date,
                    end_date,
                    verbose=verbose,
                    top_n=top_n,
                )
            except (ValueError, RuntimeError) as e:
                results[name] = {"error": str(e)}

        # Checklist post-processing
        if "checklist" in module_names:
            fund = results.get("fundamental")
            risk_r = results.get("risk")
            sig = results.get("signals")
            if (
                fund
                and risk_r
                and not isinstance(fund, dict)
                and not isinstance(risk_r, dict)
            ):
                from ..analysis.report import compute_checklist_from_parts

                results["checklist"] = compute_checklist_from_parts(
                    fund, risk_r, sig if sig and not isinstance(sig, dict) else None
                )
            else:
                results["checklist"] = {
                    "error": "checklist requires fundamental + risk modules"
                }

        if use_json:
            # Build JSON-serializable dict
            sym_data: dict = {}
            for name in module_names:
                r = results.get(name)
                if r is None:
                    continue
                if isinstance(r, dict):
                    sym_data[name] = r
                elif isinstance(r, list):
                    sym_data[name] = r
                else:
                    sym_data[name] = r.model_dump() if hasattr(r, "model_dump") else r
            if is_batch:
                json_results[sym] = sym_data
            else:
                json_results = sym_data
        else:
            # Text output with section headers
            for name in module_names:
                r = results.get(name)
                if r is None:
                    continue

                section_header(name, sym if is_batch else None)

                if isinstance(r, dict):
                    # Error or simple dict
                    kv_output(r)
                    continue

                mod = MODULES[name]
                fmt_type, fmt_data = mod.formatter(r, verbose)

                if fmt_type == "kv":
                    kv_output(fmt_data)
                elif fmt_type == "tsv":
                    rows, columns = fmt_data
                    tsv_output(rows, columns=columns)
                elif fmt_type == "technical":
                    # Multi-timeframe technical output
                    multi = fmt_data
                    if multi.monthly:
                        timeframe_section("月线 (Monthly)", multi.monthly, verbose)
                    if multi.weekly:
                        timeframe_section("周线 (Weekly)", multi.weekly, verbose)
                    if multi.daily:
                        daily = multi.daily
                        if daily.message:
                            print(f"  {daily.message}")
                        else:
                            daily_kv: dict = {
                                "Close": daily.latest_close,
                                "Trend": daily.moving_averages.trend,
                                "MACD_Signal": daily.macd.signal,
                                "RSI": daily.rsi.rsi,
                                "RSI_Zone": daily.rsi.assessment,
                                "BB_Position": daily.bollinger.position,
                            }
                            if verbose:
                                if daily.moving_averages.explanation:
                                    daily_kv["MA_Explain"] = (
                                        daily.moving_averages.explanation
                                    )
                                if daily.macd.explanation:
                                    daily_kv["MACD_Explain"] = daily.macd.explanation
                                if daily.rsi.explanation:
                                    daily_kv["RSI_Explain"] = daily.rsi.explanation
                                if daily.bollinger.explanation:
                                    daily_kv["BB_Explain"] = daily.bollinger.explanation
                            kv_output(daily_kv)

    if use_json:
        json_output(json_results)
