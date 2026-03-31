"""Crypto market data provider using CoinGecko free API as fallback."""

from datetime import date, datetime

import httpx

from ..models import BasicInfo, MarketType, PriceBar
from .provider import MarketProvider

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Map common trading pair symbols to CoinGecko IDs
_SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "XRP": "ripple",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
}


def _normalize_symbol(symbol: str) -> str:
    """Extract base asset from trading pair. E.g. 'BTC_USDT' -> 'BTC'."""
    return symbol.upper().split("_")[0].split("/")[0]


def _to_coingecko_id(symbol: str) -> str:
    base = _normalize_symbol(symbol)
    if base in _SYMBOL_TO_ID:
        return _SYMBOL_TO_ID[base]
    return base.lower()


class CryptoProvider(MarketProvider):
    """Crypto data provider using CoinGecko free API."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=10.0)
        return self._client

    def get_current_price(self, symbol: str) -> float:
        """Get latest USD price for a crypto asset.

        Args:
            symbol: Trading pair like "BTC_USDT" or just "BTC".
        """
        coin_id = _to_coingecko_id(symbol)
        resp = self.client.get(
            f"{COINGECKO_BASE}/simple/price",
            params={"ids": coin_id, "vs_currencies": "usd"},
        )
        resp.raise_for_status()
        data = resp.json()
        if coin_id not in data:
            raise ValueError(f"Crypto asset {symbol} (id={coin_id}) not found")
        return float(data[coin_id]["usd"])

    def get_price_history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Get daily OHLC data for a crypto asset (close prices only from CoinGecko free tier)."""
        coin_id = _to_coingecko_id(symbol)
        start_ts = int(datetime.combine(start, datetime.min.time()).timestamp())
        end_ts = int(datetime.combine(end, datetime.max.time()).timestamp())

        resp = self.client.get(
            f"{COINGECKO_BASE}/coins/{coin_id}/market_chart/range",
            params={"vs_currency": "usd", "from": start_ts, "to": end_ts},
        )
        resp.raise_for_status()
        data = resp.json()

        bars = []
        for ts_ms, price in data.get("prices", []):
            bar_date = datetime.fromtimestamp(ts_ms / 1000).date()
            bars.append(
                PriceBar(
                    symbol=symbol,
                    market_type=MarketType.CRYPTO,
                    trade_date=bar_date,
                    close=float(price),
                )
            )
        return bars

    def get_basic_info(self, symbol: str) -> BasicInfo:
        """Get basic info for a crypto asset."""
        coin_id = _to_coingecko_id(symbol)
        resp = self.client.get(f"{COINGECKO_BASE}/coins/{coin_id}")
        resp.raise_for_status()
        data = resp.json()
        return BasicInfo(
            name=data.get("name", ""),
            sector="crypto",
            currency="USD",
            market_type="crypto",
            market_cap=data.get("market_data", {}).get("market_cap", {}).get("usd"),
            total_supply=data.get("market_data", {}).get("total_supply"),
        )
