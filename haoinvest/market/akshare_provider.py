"""A-share market data provider using AKShare."""

from datetime import date

import akshare as ak

from .provider import MarketProvider


class AKShareProvider(MarketProvider):
    """Provider for Chinese A-share market data via AKShare.

    AKShare APIs change frequently. This provider wraps calls with
    error handling and clear messages when interfaces break.
    """

    def get_current_price(self, symbol: str) -> float:
        """Get latest price for an A-share stock.

        Args:
            symbol: 6-digit stock code, e.g. "600519" for Kweichow Moutai.
        """
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol]
            if row.empty:
                raise ValueError(f"Symbol {symbol} not found in A-share market")
            return float(row.iloc[0]["最新价"])
        except Exception as e:
            if "not found" in str(e):
                raise
            raise RuntimeError(
                f"Failed to fetch price for {symbol}. "
                f"AKShare API may have changed: {e}"
            ) from e

    def get_price_history(
        self, symbol: str, start: date, end: date
    ) -> list[dict]:
        """Get daily OHLCV bars for an A-share stock.

        Args:
            symbol: 6-digit stock code.
            start: Start date (inclusive).
            end: End date (inclusive).
        """
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",  # forward-adjusted
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
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch history for {symbol}. "
                f"AKShare API may have changed: {e}"
            ) from e

    def get_basic_info(self, symbol: str) -> dict:
        """Get basic info for an A-share stock."""
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            info = {}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]
            return {
                "name": info.get("股票简称", ""),
                "sector": info.get("行业", ""),
                "currency": "CNY",
                "market_type": "a_share",
                "total_market_cap": info.get("总市值", ""),
                "pe_ratio": info.get("市盈率(动态)", ""),
                "pb_ratio": info.get("市净率", ""),
            }
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch info for {symbol}. "
                f"AKShare API may have changed: {e}"
            ) from e
