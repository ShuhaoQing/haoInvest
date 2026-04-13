"""Shared utilities for market data sources."""

import os
from contextlib import contextmanager
from typing import Any

_PROXY_VARS = (
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


@contextmanager
def bypass_proxy():
    """Temporarily remove proxy env vars so requests to domestic APIs go direct."""
    saved = {}
    for var in _PROXY_VARS:
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        yield
    finally:
        os.environ.update(saved)


def _is_sh(symbol: str) -> bool:
    """Check if symbol belongs to Shanghai Exchange.

    Shanghai codes: 6xxxxx (main/STAR), 9xxxxx, 5xxxxx (ETF/funds including
    51xxxx, 56xxxx cross-market ETFs that route via SH on quote APIs).
    """
    return symbol.startswith(("5", "6", "9"))


def market_prefix(symbol: str) -> str:
    """Return 'sh' or 'sz' based on A-share stock code convention."""
    return "sh" if _is_sh(symbol) else "sz"


def secid(symbol: str) -> str:
    """Return eastmoney secid like '1.603618' (1=SH, 0=SZ)."""
    return f"1.{symbol}" if _is_sh(symbol) else f"0.{symbol}"


def exchange_prefix(symbol: str) -> str:
    """Return 'SH' or 'SZ' for eastmoney web API code parameter."""
    return "SH" if _is_sh(symbol) else "SZ"


def parse_float(value: Any) -> float | None:
    """Parse a value to float, returning None for empty/invalid values."""
    if value is None or value == "":
        return None
    try:
        result = float(value)
        return result if result != 0 else None
    except (ValueError, TypeError):
        return None


def parse_int(value: Any) -> int | None:
    """Parse a value to int, returning None for empty/invalid values."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
