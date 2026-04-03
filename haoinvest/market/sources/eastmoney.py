"""Eastmoney web API data source for A-share market data.

Endpoints:
- emweb.securities.eastmoney.com — company info (F10 page backend)
- datacenter-web.eastmoney.com — financial reports and indicators
"""

import logging

import requests

from ...models import BasicInfo
from ._common import exchange_prefix, parse_float, parse_int

logger = logging.getLogger(__name__)


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
