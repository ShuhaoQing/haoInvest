"""Analysis module registry — maps module names to runners and formatters.

Each module defines how to execute an analysis and how to format its output
for the CLI. Used by the composable `analyze run` command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from ..db import Database
from ..models import MarketType


@dataclass
class AnalysisModule:
    """A single analysis module that can be composed into a run command."""

    name: str
    runner: Callable[..., Any]
    formatter: Callable[..., tuple[str, Any]]
    needs_prices: bool = True
    default_lookback_days: int = 365
    # Extra kwargs this module accepts (e.g., top_n for peer)
    extra_kwargs: list[str] = field(default_factory=list)


# -- Runners: thin wrappers to normalize call signatures --


def _run_fundamental(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .fundamental import analyze_stock

    return analyze_stock(symbol, market_type)


def _run_technical(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .technical import analyze_technical_multi

    verbose = kwargs.get("verbose", False)
    return analyze_technical_multi(db, symbol, market_type, start, end, verbose=verbose)


def _run_risk(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .risk import calculate_risk_metrics

    return calculate_risk_metrics(db, symbol, market_type, start, end)


def _run_volume(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .volume import analyze_volume

    verbose = kwargs.get("verbose", False)
    return analyze_volume(db, symbol, market_type, start, end, verbose=verbose)


def _run_signals(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .signals import aggregate_signals

    verbose = kwargs.get("verbose", False)
    return aggregate_signals(db, symbol, market_type, start, end, verbose=verbose)


def _run_peer(
    db: Database,
    symbol: str,
    market_type: MarketType,
    start: date,
    end: date,
    **kwargs: Any,
) -> Any:
    from .peer import find_peers

    top_n = kwargs.get("top_n", 10)
    return find_peers(symbol, market_type, top_n=top_n)


# -- Formatters: convert results to (output_type, data) --
# "kv" -> dict for kv_output
# "tsv" -> (list[dict], columns) for tsv_output
# "technical" -> special multi-timeframe format


def _format_fundamental(result: Any, verbose: bool = False) -> tuple[str, Any]:
    output: dict[str, Any] = {
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
        "CurrentRatio": result.current_ratio,
        "FreeCashFlow": result.free_cash_flow,
        "PEG": result.peg_ratio,
        "PE_Assessment": result.valuation.pe_assessment,
        "PB_Assessment": result.valuation.pb_assessment,
        "Overall_Valuation": result.valuation.overall,
    }
    if verbose and result.financial_health:
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
    return ("kv", output)


def _format_technical(result: Any, verbose: bool = False) -> tuple[str, Any]:
    return ("technical", result)


def _format_risk(result: Any, verbose: bool = False) -> tuple[str, Any]:
    return (
        "kv",
        {
            "Volatility": result.annualized_volatility,
            "MaxDrawdown%": result.max_drawdown_pct,
            "Sharpe": result.sharpe_ratio,
            "Sortino": result.sortino_ratio,
            "TotalReturn%": result.total_return_pct,
        },
    )


def _format_volume(result: Any, verbose: bool = False) -> tuple[str, Any]:
    output: dict[str, Any] = {}
    if result.message:
        output["message"] = result.message
    else:
        output.update(
            {
                "LatestVolume": result.latest_volume,
                "AvgVolume20d": result.avg_volume_20d,
                "VolumeRatio": result.volume_ratio,
                "IsAnomaly": result.is_anomaly,
                "Assessment": result.assessment,
            }
        )
        if verbose and result.explanation:
            output["Explanation"] = result.explanation
    return ("kv", output)


def _format_signals(result: Any, verbose: bool = False) -> tuple[str, Any]:
    output: dict[str, Any] = {
        "OverallSignal": result.overall_signal,
        "Confidence": result.confidence,
        "Bullish": result.bullish_count,
        "Bearish": result.bearish_count,
        "Neutral": result.neutral_count,
    }
    for i, detail in enumerate(result.details):
        output[f"Indicator_{i + 1}"] = detail
    if verbose and result.explanation:
        output["Explanation"] = result.explanation
    return ("kv", output)


def _format_peer(result: Any, verbose: bool = False) -> tuple[str, Any]:
    if result and "message" in result[0]:
        return ("kv", {"message": result[0]["message"]})
    columns = ["Symbol", "Name", "Price", "Change%", "PE", "PB", "MarketCap"]
    return ("tsv", (result, columns))


def _format_checklist(result: Any, verbose: bool = False) -> tuple[str, Any]:
    output: dict[str, Any] = {}
    for item in result.items:
        output[item.dimension] = f"{item.score}/5 — {item.assessment}"
    output["TotalScore"] = f"{result.total_score}/{result.max_score}"
    output["Recommendation"] = result.recommendation
    return ("kv", output)


# -- Module resolution --


def parse_modules(modules_str: str) -> list[str]:
    """Parse --modules flag. 'all' expands to all modules in order."""
    if modules_str.strip().lower() == "all":
        return list(MODULES.keys())
    names = [m.strip().lower() for m in modules_str.split(",") if m.strip()]
    unknown = [n for n in names if n not in MODULES]
    if unknown:
        valid = ", ".join(MODULES.keys())
        raise ValueError(f"Unknown module(s): {', '.join(unknown)}. Valid: {valid}")
    return names


def max_lookback_days(module_names: list[str]) -> int:
    """Return the max default_lookback_days across requested modules."""
    return max(
        (MODULES[n].default_lookback_days for n in module_names if n in MODULES),
        default=365,
    )


def any_needs_prices(module_names: list[str]) -> bool:
    """Return True if any requested module needs cached price data."""
    return any(MODULES[n].needs_prices for n in module_names if n in MODULES)


# -- Registry --

MODULES: dict[str, AnalysisModule] = {
    "fundamental": AnalysisModule(
        name="fundamental",
        runner=_run_fundamental,
        formatter=_format_fundamental,
        needs_prices=False,
        default_lookback_days=0,
    ),
    "technical": AnalysisModule(
        name="technical",
        runner=_run_technical,
        formatter=_format_technical,
        needs_prices=True,
        default_lookback_days=1095,
    ),
    "risk": AnalysisModule(
        name="risk",
        runner=_run_risk,
        formatter=_format_risk,
        needs_prices=True,
    ),
    "volume": AnalysisModule(
        name="volume",
        runner=_run_volume,
        formatter=_format_volume,
        needs_prices=True,
    ),
    "signals": AnalysisModule(
        name="signals",
        runner=_run_signals,
        formatter=_format_signals,
        needs_prices=True,
    ),
    "peer": AnalysisModule(
        name="peer",
        runner=_run_peer,
        formatter=_format_peer,
        needs_prices=False,
        default_lookback_days=0,
        extra_kwargs=["top_n"],
    ),
    "checklist": AnalysisModule(
        name="checklist",
        runner=lambda *a, **kw: None,  # placeholder — computed as post-processing
        formatter=_format_checklist,
        needs_prices=False,
        default_lookback_days=0,
    ),
}
