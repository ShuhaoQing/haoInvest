"""Abstract market data provider interface."""

from abc import ABC, abstractmethod
from datetime import date

from ..models import BasicInfo, PriceBar


class MarketProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return the latest price in the asset's local currency."""

    @abstractmethod
    def get_price_history(
        self, symbol: str, start: date, end: date
    ) -> list[PriceBar]:
        """Return daily OHLCV bars as PriceBar models."""

    @abstractmethod
    def get_basic_info(self, symbol: str) -> BasicInfo:
        """Return basic info about the asset."""
