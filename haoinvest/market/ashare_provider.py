"""A-share market data provider using direct Sina/Tencent/eastmoney APIs.

Each data source is isolated in its own module under market/sources/.
The provider orchestrates source selection and fallback logic.
"""

import logging
from datetime import date
from typing import Any, Callable

from ..models import BasicInfo, PriceBar
from .provider import MarketProvider
from .sources import eastmoney, sina, tencent
from .sources._common import bypass_proxy

logger = logging.getLogger(__name__)


def _with_fallback(primary_fn: Callable, fallback_fn: Callable, label: str) -> Any:
    """Try primary function, fall back on any failure.

    Args:
        primary_fn: Callable that returns the result.
        fallback_fn: Callable to use when primary fails.
        label: Description for logging.
    """
    with bypass_proxy():
        try:
            return primary_fn()
        except ValueError:
            raise
        except Exception as e:
            logger.debug("Primary failed for %s: %s, using fallback", label, e)
        return fallback_fn()


class AShareProvider(MarketProvider):
    """Provider for Chinese A-share market data.

    Uses Sina, Tencent, and eastmoney web APIs directly.
    """

    def get_current_price(self, symbol: str) -> float:
        """Get latest price for an A-share stock."""
        return _with_fallback(
            primary_fn=lambda: sina.get_current_price(symbol),
            fallback_fn=lambda: tencent.get_current_price(symbol),
            label=f"get_current_price({symbol})",
        )

    def get_price_history(self, symbol: str, start: date, end: date) -> list[PriceBar]:
        """Get daily OHLCV bars for an A-share stock."""
        with bypass_proxy():
            return tencent.get_price_history(symbol, start, end)

    def get_basic_info(self, symbol: str) -> BasicInfo:
        """Get basic info for an A-share stock."""
        with bypass_proxy():
            info = eastmoney.get_basic_info(symbol)
            valuation = tencent.get_valuation(symbol)
            fin = eastmoney.get_financial_indicators(symbol)

        return BasicInfo(
            name=info.name,
            sector=info.sector,
            currency=info.currency,
            market_type=info.market_type,
            total_market_cap=valuation.get("total_market_cap"),
            pe_ratio=valuation.get("pe_ratio"),
            pb_ratio=valuation.get("pb_ratio"),
            **fin,
        )

    # -- Sector/Industry methods (A-share specific) --

    @staticmethod
    def get_sector_list() -> list[dict]:
        """List all A-share industry boards with performance ranking."""
        with bypass_proxy():
            return sina.get_sector_list()

    @staticmethod
    def get_sector_constituents(sector_name: str) -> list[dict]:
        """Get stocks in a specific industry board."""
        with bypass_proxy():
            return sina.get_sector_constituents(sector_name)

    @staticmethod
    def screen_stocks(**kwargs) -> dict:
        """Screen A-share stocks by financial criteria.

        Supported filters: pe_min, pe_max, pb_min, pb_max, roe_min,
        cap_min, cap_max, dividend_yield_min, sort_by, sort_asc,
        page, page_size.

        Returns dict with 'total' count and 'data' list.
        """
        with bypass_proxy():
            return eastmoney.screen_stocks(**kwargs)

    @staticmethod
    def get_sector_flow(board_type: str = "industry", limit: int = 20) -> list[dict]:
        """Fetch sector capital flow from push2 endpoint (beta).

        Args:
            board_type: "industry" or "concept"
            limit: Number of sectors to return

        Returns list of dicts with net main inflow data.
        Push2 endpoint has known stability issues — returns empty list on failure.
        """
        with bypass_proxy():
            return eastmoney.get_sector_flow(board_type=board_type, limit=limit)
