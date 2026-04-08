"""Eastmoney web API data source for A-share market data.

Endpoints:
- emweb.securities.eastmoney.com — company info (F10 page backend)
- datacenter-web.eastmoney.com — financial reports and indicators
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


def get_financial_indicators(symbol: str, periods: int = 1) -> dict | list[dict]:
    """Fetch financial indicators from eastmoney datacenter API.

    Uses RPT_LICO_FN_CPD (业绩报表).
    Returns a dict of optional fields for BasicInfo enrichment (periods=1),
    or a list of dicts for multi-period analysis (periods>1).
    Gracefully returns empty dict/list on any failure.
    """
    try:
        body = _fetch_financial_data(symbol, page_size=periods)

        if not body.get("success") or not body.get("result"):
            return [] if periods > 1 else {}

        data = body["result"].get("data")
        if not data:
            return [] if periods > 1 else {}

        results = [_parse_financial_row(row) for row in data]

        if periods > 1:
            return results
        return results[0] if results else {}
    except Exception as e:
        logger.debug("Eastmoney financial indicators failed for %s: %s", symbol, e)
        return [] if periods > 1 else {}


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
