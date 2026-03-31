"""US stock market data provider using yfinance."""

from datetime import date, timedelta

import yfinance as yf

from ..models import BasicInfo, MarketType, PriceBar
from .provider import MarketProvider


class USProvider(MarketProvider):
    """US stock data provider via Yahoo Finance."""

    def get_current_price(self, symbol: str) -> float:
        """Get latest USD price for a US stock.

        Args:
            symbol: Ticker symbol like "AAPL", "NVDA", "MSFT".
        """
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        price = fast.get("lastPrice") or fast.get("previousClose")
        if price is None:
            raise ValueError(f"Cannot fetch current price for {symbol}")
        return float(price)

    def get_price_history(
        self, symbol: str, start: date, end: date
    ) -> list[PriceBar]:
        """Get daily OHLCV bars for a US stock."""
        ticker = yf.Ticker(symbol)
        # yfinance end date is exclusive, so add one day
        df = ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat())
        if df.empty:
            return []

        bars = []
        for idx, row in df.iterrows():
            bars.append(PriceBar(
                symbol=symbol,
                market_type=MarketType.US,
                trade_date=idx.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            ))
        return bars

    def get_basic_info(self, symbol: str) -> BasicInfo:
        """Get basic info for a US stock."""
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return BasicInfo(
            name=info.get("shortName") or info.get("longName", ""),
            sector=info.get("sector", ""),
            currency=info.get("currency", "USD"),
            market_type="us",
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            pb_ratio=info.get("priceToBook"),
        )
