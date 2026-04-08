"""Eastmoney web API data source for A-share market data.

Endpoints:
- emweb.securities.eastmoney.com — company info (F10 page backend)
- datacenter-web.eastmoney.com — financial reports and indicators
- data.eastmoney.com/dataapi/xuangu — stock screening
"""

import logging

import requests

from ...http_retry import api_retry
from ...models import BasicInfo
from ._common import exchange_prefix, parse_float

logger = logging.getLogger(__name__)

_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# Request all columns from RPT_LICO_FN_CPD (业绩报表)
_FIN_COLUMNS = "ALL"


@api_retry
def get_basic_info(symbol: str) -> BasicInfo:
    """Get basic company info from eastmoney emweb CompanySurvey API."""
    code = f"{exchange_prefix(symbol)}{symbol}"
    url = "https://emweb.securities.eastmoney.com/pc_hsf10/CompanySurvey/CompanySurveyAjax"
    r = requests.get(url, params={"code": code}, timeout=10)
    r.raise_for_status()
    data = r.json()
    jbzl = data.get("jbzl", {})

    return BasicInfo(
        name=jbzl.get("agjc", ""),
        sector=jbzl.get("sshy", ""),
        currency="CNY",
        market_type="a_share",
    )


def get_financial_indicators(symbol: str, periods: int = 1) -> list[dict]:
    """Fetch financial indicators from eastmoney datacenter API.

    Uses RPT_LICO_FN_CPD (业绩报表).
    Returns a list of dicts (one per reporting period) for BasicInfo enrichment
    or multi-period analysis. Callers use ``result[0]`` for the latest period.
    Gracefully returns empty list on any failure.
    """
    try:
        body = _fetch_financial_data(symbol, page_size=periods)

        if not body.get("success") or not body.get("result"):
            return []

        data = body["result"].get("data")
        if not data:
            return []

        return [_parse_financial_row(row) for row in data]
    except Exception as e:
        logger.debug("Eastmoney financial indicators failed for %s: %s", symbol, e)
        return []


def _parse_financial_row(row: dict) -> dict:
    """Parse a single row from RPT_LICO_FN_CPD into BasicInfo-compatible fields."""
    revenue = parse_float(row.get("TOTAL_OPERATE_INCOME"))
    net_profit = parse_float(row.get("PARENT_NETPROFIT"))

    result = {
        "roe": parse_float(row.get("WEIGHTAVG_ROE")),
        "gross_margin": parse_float(row.get("XSMLL")),
        "revenue_growth": parse_float(row.get("YSTZ")),
        "net_profit_growth": parse_float(row.get("SJLTZ")),
        "revenue_growth_qoq": parse_float(row.get("YSHZ")),
        "net_profit_growth_qoq": parse_float(row.get("SJLHZ")),
        "eps": parse_float(row.get("BASIC_EPS")),
        "book_value_per_share": parse_float(row.get("BPS")),
        "operating_cash_flow_per_share": parse_float(row.get("MGJYXJJE")),
        "dividend_yield": parse_float(row.get("ZXGXL")),
    }

    # Compute profit margin from net profit / revenue
    if revenue and net_profit:
        result["profit_margin"] = round(net_profit / revenue * 100, 2)

    # Report metadata
    report_date = row.get("REPORTDATE", "")
    if report_date:
        result["report_date"] = report_date[:10]
    datatype = row.get("DATATYPE")
    if datatype:
        result["report_type"] = datatype

    return {k: v for k, v in result.items() if v is not None}


@api_retry
def _fetch_financial_data(symbol: str, page_size: int = 1) -> dict:
    """Fetch financial report data from eastmoney datacenter (with retry)."""
    r = requests.get(
        _DATACENTER_URL,
        params={
            "reportName": "RPT_LICO_FN_CPD",
            "columns": _FIN_COLUMNS,
            "filter": f'(SECURITY_CODE="{symbol}")',
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": "NOTICE_DATE",
            "sortTypes": "-1",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# --- Stock Screening ---

_SCREEN_URL = "https://data.eastmoney.com/dataapi/xuangu/list"

_SCREEN_COLUMNS = (
    "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,NEW_PRICE,"
    "CHANGE_RATE,PE9,PB_MRQ,ROE_WEIGHT,TOTAL_MARKET_CAP,ZXGXL"
)


@api_retry
def screen_stocks(
    *,
    pe_min: float | None = None,
    pe_max: float | None = None,
    pb_min: float | None = None,
    pb_max: float | None = None,
    roe_min: float | None = None,
    cap_min: float | None = None,
    cap_max: float | None = None,
    dividend_yield_min: float | None = None,
    sort_by: str = "ROE_WEIGHT",
    sort_asc: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Screen A-share stocks using eastmoney xuangu API.

    Returns dict with 'total' count and 'data' list of matching stocks.
    Each stock has: symbol, name, price, change_pct, pe, pb, roe, market_cap,
    dividend_yield.

    Note: loss-making companies (PE < 0) are only excluded automatically when
    pe_max is set without pe_min. Other filter combinations may still include them.
    """
    # Build filter string: each condition is (FIELD>VALUE) or (FIELD<VALUE)
    filters = []
    if pe_min is not None:
        filters.append(f"(PE9>{pe_min})")
    if pe_max is not None:
        filters.append(f"(PE9<{pe_max})")
    if pb_min is not None:
        filters.append(f"(PB_MRQ>{pb_min})")
    if pb_max is not None:
        filters.append(f"(PB_MRQ<{pb_max})")
    if roe_min is not None:
        filters.append(f"(ROE_WEIGHT>{roe_min})")
    if cap_min is not None:
        filters.append(f"(TOTAL_MARKET_CAP>{cap_min})")
    if cap_max is not None:
        filters.append(f"(TOTAL_MARKET_CAP<{cap_max})")
    if dividend_yield_min is not None:
        filters.append(f"(ZXGXL>{dividend_yield_min})")

    # Require positive PE by default to exclude loss-making companies
    if pe_min is None and pe_max is not None:
        filters.append("(PE9>0)")

    params = {
        "sty": _SCREEN_COLUMNS,
        "filter": "".join(filters) if filters else "",
        "p": str(page),
        "ps": str(page_size),
        "st": sort_by,
        "sr": "1" if sort_asc else "-1",
    }

    r = requests.get(_SCREEN_URL, params=params, timeout=15)
    r.raise_for_status()
    body = r.json()

    if not body.get("success"):
        return {"total": 0, "data": []}

    result = body.get("result", {})
    total = result.get("count", 0)
    rows = result.get("data", []) or []

    data = []
    for row in rows:
        data.append(
            {
                "symbol": row.get("SECURITY_CODE", ""),
                "name": row.get("SECURITY_NAME_ABBR", ""),
                "price": parse_float(row.get("NEW_PRICE")),
                "change_pct": parse_float(row.get("CHANGE_RATE")),
                "pe": parse_float(row.get("PE9")),
                "pb": parse_float(row.get("PB_MRQ")),
                "roe": parse_float(row.get("ROE_WEIGHT")),
                "market_cap": parse_float(row.get("TOTAL_MARKET_CAP")),
                "dividend_yield": parse_float(row.get("ZXGXL")),
            }
        )

    return {"total": total, "data": data}


# --- Sector Capital Flow (push2 endpoint, beta) ---

_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"


def get_sector_flow(board_type: str = "industry", limit: int = 20) -> list[dict]:
    """Fetch sector capital flow data from push2 endpoint.

    Args:
        board_type: "industry" (行业板块) or "concept" (概念板块)
        limit: Number of sectors to return

    Returns list of dicts sorted by net main inflow (descending).
    NOTE: push2 endpoint has known stability issues (connection resets,
    IP blocking). Callers should handle failures gracefully.
    """
    fs_map = {"industry": "m:90+t:2", "concept": "m:90+t:3"}
    fs = fs_map.get(board_type, "m:90+t:2")

    try:
        r = requests.get(
            _PUSH2_URL,
            params={
                "fid": "f62",
                "po": "1",
                "pz": str(limit),
                "pn": "1",
                "np": "1",
                "fs": fs,
                "fields": "f12,f14,f62,f184,f66,f69,f72,f75",
            },
            headers={
                "Referer": "https://data.eastmoney.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                ),
            },
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        logger.warning("push2 sector flow request failed: %s", e)
        return []

    if body.get("rc") != 0 or not body.get("data"):
        return []

    results = []
    for item in body["data"].get("diff", []):
        net_inflow = item.get("f62")
        results.append(
            {
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "net_inflow": net_inflow,
                "net_inflow_yi": (
                    f"{net_inflow / 1e8:.2f}亿" if net_inflow is not None else "N/A"
                ),
                "net_inflow_pct": item.get("f184"),
                "super_large_inflow": item.get("f66"),
                "super_large_pct": item.get("f69"),
                "large_inflow": item.get("f72"),
                "large_pct": item.get("f75"),
            }
        )

    return results
