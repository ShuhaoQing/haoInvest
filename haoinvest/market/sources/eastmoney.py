"""Eastmoney web API data source for A-share market data.

Endpoints:
- emweb.securities.eastmoney.com — company info (F10 page backend)
- datacenter-web.eastmoney.com — financial reports and indicators
"""

import logging

import requests

from ...models import BasicInfo
from ._common import exchange_prefix, parse_float

logger = logging.getLogger(__name__)

_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# Columns we request from RPT_LICO_FN_CPD (业绩报表)
_FIN_COLUMNS = (
    "SECURITY_CODE,REPORTDATE,WEIGHTAVG_ROE,XSMLL,"
    "TOTAL_OPERATE_INCOME,PARENT_NETPROFIT"
)


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


def get_financial_indicators(symbol: str) -> dict:
    """Fetch financial indicators from eastmoney datacenter API.

    Uses RPT_LICO_FN_CPD (业绩报表) for the most recent reporting period.
    Returns a dict of optional fields for BasicInfo enrichment.
    Gracefully returns empty dict on any failure.
    """
    try:
        r = requests.get(
            _DATACENTER_URL,
            params={
                "reportName": "RPT_LICO_FN_CPD",
                "columns": _FIN_COLUMNS,
                "filter": f'(SECURITY_CODE="{symbol}")',
                "pageNumber": "1",
                "pageSize": "1",
                "sortColumns": "NOTICE_DATE",
                "sortTypes": "-1",
            },
            timeout=10,
        )
        r.raise_for_status()
        body = r.json()

        if not body.get("success") or not body.get("result"):
            return {}

        data = body["result"].get("data")
        if not data:
            return {}

        latest = data[0]
        result = {
            "roe": parse_float(latest.get("WEIGHTAVG_ROE")),
            "gross_margin": parse_float(latest.get("XSMLL")),
        }

        # Compute profit margin from net profit / revenue
        revenue = parse_float(latest.get("TOTAL_OPERATE_INCOME"))
        net_profit = parse_float(latest.get("PARENT_NETPROFIT"))
        if revenue and net_profit:
            result["profit_margin"] = round(net_profit / revenue * 100, 2)

        return {k: v for k, v in result.items() if v is not None}
    except Exception as e:
        logger.debug("Eastmoney financial indicators failed for %s: %s", symbol, e)
        return {}
