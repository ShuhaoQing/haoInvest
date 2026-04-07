"""Output formatters for CLI commands.

Three formats:
- Key-Value text: for single records (quote, basic info)
- TSV: for tabular data (holdings, price history)
- JSON: for complex nested data or when --json is used
"""

import json
import sys
from typing import Any

from pydantic import BaseModel


def _to_dict(data: dict[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(data, BaseModel):
        return data.model_dump()
    return data


def kv_output(data: dict[str, Any] | BaseModel) -> None:
    """Print key-value pairs, one per line. Skips None values."""
    for key, value in _to_dict(data).items():
        if value is None:
            continue
        print(f"{key}: {value}")


def tsv_output(
    rows: list[dict[str, Any] | BaseModel], columns: list[str] | None = None
) -> None:
    """Print tab-separated table with header row.

    Args:
        rows: List of dicts or models with consistent keys.
        columns: Column names to include (and their order). If None, uses all keys.
    """
    if not rows:
        print("(empty)")
        return
    dict_rows = [_to_dict(r) for r in rows]
    if columns is None:
        columns = list(dict_rows[0].keys())
    print("\t".join(columns))
    for row in dict_rows:
        print("\t".join(str(row.get(c, "")) for c in columns))


def json_output(data: Any) -> None:
    """Print JSON with Chinese characters preserved."""
    if isinstance(data, BaseModel):
        data = data.model_dump()
    elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
        data = [item.model_dump() for item in data]
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def timeframe_section(
    label: str,
    result: Any,
    verbose: bool = False,
) -> None:
    """Print a compact technical indicator section for a single timeframe."""
    print(f"\n📊 {label}")
    if result.message:
        print(f"  {result.message}")
        return
    ma = result.moving_averages
    print(
        f"  MA: SMA5={ma.sma_5}  SMA10={ma.sma_10}  SMA20={ma.sma_20}"
        f" | EMA12={ma.ema_12}  EMA26={ma.ema_26}"
    )
    if verbose and ma.explanation:
        print(f"  MA说明: {ma.explanation}")
    macd = result.macd
    print(
        f"  MACD: DIF={macd.macd_line}  DEA={macd.signal_line}  MACD={macd.histogram}"
    )
    if verbose and macd.explanation:
        print(f"  MACD说明: {macd.explanation}")
    print(f"  RSI(14): {result.rsi.rsi}")
    if verbose and result.rsi.explanation:
        print(f"  RSI说明: {result.rsi.explanation}")


def section_header(name: str, symbol: str | None = None) -> None:
    """Print a section header like === risk === or === risk: 600519 ===."""
    if symbol:
        print(f"\n=== {name}: {symbol} ===")
    else:
        print(f"\n=== {name} ===")


def error_output(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)
