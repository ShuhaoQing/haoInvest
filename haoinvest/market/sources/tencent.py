"""Tencent Finance API data source for A-share market data.

Endpoints:
- qt.gtimg.cn — real-time quotes and valuation
- web.ifzq.gtimg.cn — historical kline data (forward-adjusted)
"""

import logging
from datetime import date

import requests

from ...http_retry import api_retry
from ...models import MarketType, PriceBar
from ._common import market_prefix, parse_float

logger = logging.getLogger(__name__)

# Tencent quote field indices (format: v_sh600519="1~name~code~price~...")
_PE_TTM = 39
_TOTAL_CAP_YI = 45  # total market cap in 亿元
_PB = 46


@api_retry
def get_current_price(symbol: str) -> float:
    """Get current price from Tencent Finance quote API."""
    prefix = market_prefix(symbol)
    r = requests.get(
        f"https://qt.gtimg.cn/q={prefix}{symbol}",
        timeout=10,
    )
    r.raise_for_status()
    fields = r.text.strip().split("~")
    if len(fields) < 4 or not fields[3]:
        raise ValueError(f"Symbol {symbol} not found in A-share market")
    price = float(fields[3])
    if price <= 0:
        raise RuntimeError(f"Invalid price for {symbol} from Tencent API")
    return price


@api_retry
def get_price_history(symbol: str, start: date, end: date) -> list[PriceBar]:
    """Get forward-adjusted daily klines from Tencent Finance API."""
    prefix = market_prefix(symbol)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    days = (end - start).days + 50
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    r = requests.get(
        url,
        params={"param": f"{prefix}{symbol},day,{start_str},{end_str},{days},qfq"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    stock_data = data.get("data", {}).get(f"{prefix}{symbol}", {})
    klines = stock_data.get("qfqday") or stock_data.get("day", [])

    bars = []
    for k in klines:
        # Tencent kline format: [date, open, close, high, low, volume]
        if len(k) < 6:
            continue
        bar_date = date.fromisoformat(k[0])
        if bar_date < start or bar_date > end:
            continue
        bars.append(
            PriceBar(
                symbol=symbol,
                market_type=MarketType.A_SHARE,
                trade_date=bar_date,
                open=float(k[1]),
                high=float(k[3]),
                low=float(k[4]),
                close=float(k[2]),
                volume=float(k[5]),
            )
        )
    return bars


def get_valuation(symbol: str) -> dict:
    """Fetch PE/PB/market cap from Tencent quote API.

    Returns dict with keys: pe_ratio, pb_ratio, total_market_cap.
    Values are typed (float/int) or None if unavailable.
    """
    result: dict[str, float | int | None] = {
        "pe_ratio": None,
        "pb_ratio": None,
        "total_market_cap": None,
    }
    try:
        fields = _fetch_quote_fields(symbol)
        if len(fields) <= _PB:
            logger.debug(
                "Tencent response too short for %s: %d fields", symbol, len(fields)
            )
            return result

        result["pe_ratio"] = parse_float(fields[_PE_TTM])
        result["pb_ratio"] = parse_float(fields[_PB])

        cap_yi = fields[_TOTAL_CAP_YI]
        if cap_yi:
            cap_val = parse_float(cap_yi)
            if cap_val is not None:
                result["total_market_cap"] = int(cap_val * 1_0000_0000)
    except Exception as e:
        logger.debug("Tencent valuation failed for %s: %s", symbol, e)

    return result


@api_retry
def _fetch_quote_fields(symbol: str) -> list[str]:
    """Fetch and parse quote fields from Tencent API (with retry)."""
    prefix = market_prefix(symbol)
    r = requests.get(
        f"https://qt.gtimg.cn/q={prefix}{symbol}",
        timeout=10,
    )
    r.raise_for_status()
    return r.text.strip().split("~")
