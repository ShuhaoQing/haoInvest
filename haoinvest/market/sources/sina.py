"""Sina Finance API data source for A-share market data.

Endpoints:
- hq.sinajs.cn — real-time quotes
- vip.stock.finance.sina.com.cn — sector/industry data
"""

import json
import re

import requests

from ...http_retry import api_retry
from ._common import market_prefix, parse_float


@api_retry
def get_current_price(symbol: str) -> float:
    """Get current price from Sina Finance API."""
    prefix = market_prefix(symbol)
    url = f"https://hq.sinajs.cn/list={prefix}{symbol}"
    r = requests.get(
        url,
        headers={"Referer": "https://finance.sina.com.cn"},
        timeout=10,
    )
    r.raise_for_status()
    # Format: var hq_str_sh603618="name,open,prev_close,current,high,low,...";
    text = r.text.strip()
    if '=""' in text or not text:
        raise ValueError(f"Symbol {symbol} not found in A-share market")
    fields = text.split('"')[1].split(",")
    if len(fields) < 4:
        raise RuntimeError(f"Unexpected Sina response format for {symbol}")
    price = float(fields[3])  # current price
    if price <= 0:
        raise RuntimeError(f"Invalid price for {symbol} from Sina API")
    return price


def get_sector_list() -> list[dict]:
    """List all A-share industry boards with performance ranking.

    Returns list of dicts with keys: name, change_pct, total_market_cap,
    turnover_rate, rise_count, fall_count.
    """
    data = _fetch_sector_data()
    rows = []
    for fields in data.values():
        if len(fields) < 6:
            continue
        rows.append(
            {
                "name": fields[1],
                "change_pct": parse_float(fields[5]),
                "total_market_cap": None,
                "turnover_rate": None,
                "rise_count": None,
                "fall_count": None,
            }
        )
    # Sort by change_pct descending (match eastmoney default sort)
    rows.sort(key=lambda r: r["change_pct"] or 0, reverse=True)
    return rows


def get_sector_constituents(sector_name: str) -> list[dict]:
    """Get stocks in a specific industry board.

    Returns list of dicts with keys: code, name, price, change_pct,
    pe_ratio, pb_ratio, total_market_cap.
    """
    # Find the Sina node code matching the sector name
    data = _fetch_sector_data()
    node_code = None
    for code, fields in data.items():
        if len(fields) >= 2 and fields[1] == sector_name:
            node_code = code
            break
    if node_code is None:
        raise ValueError(
            f"Sector '{sector_name}' not found. "
            "Use 'market sector-list' to see available sectors."
        )

    r = _fetch_sector_constituents(node_code)
    stocks = r.json()

    rows = []
    for s in stocks:
        rows.append(
            {
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "price": parse_float(s.get("trade")),
                "change_pct": parse_float(s.get("changepercent")),
                "pe_ratio": parse_float(s.get("per")),
                "pb_ratio": parse_float(s.get("pb")),
                "total_market_cap": (
                    int(s["mktcap"] * 10000) if s.get("mktcap") else None
                ),
            }
        )
    return rows


@api_retry
def _fetch_sector_constituents(node_code: str) -> requests.Response:
    """Fetch sector constituent data from Sina API (with retry)."""
    r = requests.get(
        "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
        "/Market_Center.getHQNodeData",
        params={
            "page": 1,
            "num": 200,
            "sort": "changepercent",
            "asc": 0,
            "node": node_code,
        },
        headers={"Referer": "https://finance.sina.com.cn"},
        timeout=10,
    )
    r.encoding = "gbk"
    return r


@api_retry
def _fetch_sector_data() -> dict[str, list[str]]:
    """Fetch Sina industry board data. Returns {node_code: [fields...]}."""
    r = requests.get(
        "https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php",
        headers={"Referer": "https://finance.sina.com.cn"},
        timeout=10,
    )
    r.encoding = "gbk"
    m = re.search(r"=\s*(\{.*\})", r.text)
    if not m:
        raise RuntimeError("Failed to parse Sina sector response")
    data = json.loads(m.group(1))
    return {k: v.split(",") for k, v in data.items()}
