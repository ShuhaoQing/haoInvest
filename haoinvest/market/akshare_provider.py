"""A-share market data provider using AKShare with direct-API fallbacks.

AKShare relies on eastmoney push2 endpoints which are frequently unreachable
(IP bans, proxy conflicts, CDN issues). When AKShare fails, we fall back to
Sina/Tencent/eastmoney-emweb APIs that use different, more stable endpoints.
"""

import logging
import os
from contextlib import contextmanager
from datetime import date
from typing import Any, Callable

import requests

from .provider import MarketProvider

logger = logging.getLogger(__name__)

_PROXY_VARS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")

# Tencent quote field indices (format: v_sh600519="1~name~code~price~...")
_TENCENT_PE_TTM = 39
_TENCENT_TOTAL_CAP_YI = 45  # total market cap in 亿元
_TENCENT_PB = 46


@contextmanager
def _bypass_proxy():
    """Temporarily remove proxy env vars so requests to domestic APIs go direct."""
    saved = {}
    for var in _PROXY_VARS:
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        yield
    finally:
        os.environ.update(saved)


def _market_prefix(symbol: str) -> str:
    """Return 'sh' or 'sz' based on A-share stock code convention."""
    if symbol.startswith(("6", "9")):
        return "sh"
    return "sz"


def _secid(symbol: str) -> str:
    """Return eastmoney secid like '1.603618' (1=SH, 0=SZ)."""
    return f"1.{symbol}" if symbol.startswith(("6", "9")) else f"0.{symbol}"


def _with_fallback(primary_fn: Callable, fallback_fn: Callable, label: str) -> Any:
    """Try primary function, fall back on any failure.

    Args:
        primary_fn: Callable that returns the result (typically uses akshare).
        fallback_fn: Callable to use when primary fails.
        label: Description for logging (e.g. "get_current_price(600519)").
    """
    with _bypass_proxy():
        try:
            return primary_fn()
        except ValueError:
            raise
        except Exception as e:
            logger.debug("AKShare failed for %s: %s, using fallback", label, e)
        return fallback_fn()


class AKShareProvider(MarketProvider):
    """Provider for Chinese A-share market data.

    Tries AKShare first, falls back to direct Sina/Tencent/eastmoney APIs
    when push2 endpoints are unreachable.
    """

    def get_current_price(self, symbol: str) -> float:
        """Get latest price for an A-share stock."""
        return _with_fallback(
            primary_fn=lambda: self._akshare_current_price(symbol),
            fallback_fn=lambda: self._sina_current_price(symbol),
            label=f"get_current_price({symbol})",
        )

    def get_price_history(self, symbol: str, start: date, end: date) -> list[dict]:
        """Get daily OHLCV bars for an A-share stock."""
        return _with_fallback(
            primary_fn=lambda: self._akshare_price_history(symbol, start, end),
            fallback_fn=lambda: self._tencent_price_history(symbol, start, end),
            label=f"get_price_history({symbol})",
        )

    def get_basic_info(self, symbol: str) -> dict:
        """Get basic info for an A-share stock."""
        return _with_fallback(
            primary_fn=lambda: self._akshare_basic_info(symbol),
            fallback_fn=lambda: self._emweb_basic_info(symbol),
            label=f"get_basic_info({symbol})",
        )

    # -- AKShare primary methods --

    @staticmethod
    def _akshare_current_price(symbol: str) -> float:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            raise ValueError(f"Symbol {symbol} not found in A-share market")
        return float(row.iloc[0]["最新价"])

    @staticmethod
    def _akshare_price_history(symbol: str, start: date, end: date) -> list[dict]:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        bars = []
        for _, row in df.iterrows():
            bars.append({
                "date": date.fromisoformat(str(row["日期"])[:10]),
                "open": float(row["开盘"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "close": float(row["收盘"]),
                "volume": float(row["成交量"]),
            })
        return bars

    @staticmethod
    def _akshare_basic_info(symbol: str) -> dict:
        import akshare as ak
        df = ak.stock_individual_info_em(symbol=symbol)
        info = {}
        for _, row in df.iterrows():
            info[row["item"]] = row["value"]

        pe_raw = info.get("市盈率(动态)", "")
        pb_raw = info.get("市净率", "")
        cap_raw = info.get("总市值", "")

        return {
            "name": info.get("股票简称", ""),
            "sector": info.get("行业", ""),
            "currency": "CNY",
            "market_type": "a_share",
            "total_market_cap": _parse_int(cap_raw),
            "pe_ratio": _parse_float(pe_raw),
            "pb_ratio": _parse_float(pb_raw),
        }

    # -- Fallback methods --

    @staticmethod
    def _sina_current_price(symbol: str) -> float:
        """Get current price from Sina Finance API."""
        prefix = _market_prefix(symbol)
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

    @staticmethod
    def _tencent_price_history(symbol: str, start: date, end: date) -> list[dict]:
        """Get forward-adjusted daily klines from Tencent Finance API."""
        prefix = _market_prefix(symbol)
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
            bars.append({
                "date": bar_date,
                "open": float(k[1]),
                "high": float(k[3]),
                "low": float(k[4]),
                "close": float(k[2]),
                "volume": float(k[5]),
            })
        return bars

    def _emweb_basic_info(self, symbol: str) -> dict:
        """Get basic info from eastmoney emweb + Tencent valuation APIs."""
        code = f"{'SH' if symbol.startswith(('6', '9')) else 'SZ'}{symbol}"
        url = "https://emweb.securities.eastmoney.com/pc_hsf10/CompanySurvey/CompanySurveyAjax"
        r = requests.get(url, params={"code": code}, timeout=10)
        r.raise_for_status()
        data = r.json()
        jbzl = data.get("jbzl", {})

        valuation = self._tencent_valuation(symbol)

        return {
            "name": jbzl.get("agjc", ""),
            "sector": jbzl.get("sshy", ""),
            "currency": "CNY",
            "market_type": "a_share",
            "total_market_cap": valuation.get("total_market_cap"),
            "pe_ratio": valuation.get("pe_ratio"),
            "pb_ratio": valuation.get("pb_ratio"),
        }

    @staticmethod
    def _tencent_valuation(symbol: str) -> dict:
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
            prefix = _market_prefix(symbol)
            tr = requests.get(
                f"https://qt.gtimg.cn/q={prefix}{symbol}",
                timeout=10,
            )
            tr.raise_for_status()
            tfields = tr.text.strip().split("~")
            if len(tfields) <= _TENCENT_PB:
                logger.debug("Tencent response too short for %s: %d fields", symbol, len(tfields))
                return result

            result["pe_ratio"] = _parse_float(tfields[_TENCENT_PE_TTM])
            result["pb_ratio"] = _parse_float(tfields[_TENCENT_PB])

            cap_yi = tfields[_TENCENT_TOTAL_CAP_YI]
            if cap_yi:
                cap_val = _parse_float(cap_yi)
                if cap_val is not None:
                    result["total_market_cap"] = int(cap_val * 1_0000_0000)
        except Exception as e:
            logger.debug("Tencent valuation failed for %s: %s", symbol, e)

        return result


def _parse_float(value: Any) -> float | None:
    """Parse a value to float, returning None for empty/invalid values."""
    if value is None or value == "":
        return None
    try:
        result = float(value)
        return result if result != 0 else None
    except (ValueError, TypeError):
        return None


def _parse_int(value: Any) -> int | None:
    """Parse a value to int, returning None for empty/invalid values."""
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None
