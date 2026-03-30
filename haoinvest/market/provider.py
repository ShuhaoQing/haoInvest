"""Abstract market data provider interface."""

from abc import ABC, abstractmethod
from datetime import date


class MarketProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return the latest price in the asset's local currency."""

    @abstractmethod
    def get_price_history(
        self, symbol: str, start: date, end: date
    ) -> list[dict]:
        """Return daily OHLCV bars as a list of dicts.

        Each dict has keys: date, open, high, low, close, volume.
        """

    @abstractmethod
    def get_basic_info(self, symbol: str) -> dict:
        """Return basic info about the asset.

        Expected keys: name, sector (if applicable), currency.
        """
