"""Tests for haoinvest.analysis.cache — price caching logic."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from haoinvest.analysis.cache import ensure_prices_cached
from haoinvest.models import MarketType, PriceBar


def _make_bar(d: date) -> PriceBar:
    return PriceBar(
        symbol="600519",
        market_type=MarketType.A_SHARE,
        trade_date=d,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=10000.0,
    )


class TestEnsurePricesCached:
    def test_fetches_when_no_data(self, db):
        """Should fetch full range when no cached data exists."""
        start = date(2024, 1, 1)
        end = date(2024, 6, 1)
        mock_bars = [_make_bar(start + timedelta(days=i)) for i in range(5)]
        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = mock_bars

        with patch("haoinvest.analysis.cache.get_provider", return_value=mock_provider):
            ensure_prices_cached(db, "600519", MarketType.A_SHARE, start, end)

        mock_provider.get_price_history.assert_called_once_with("600519", start, end)

    def test_skips_when_sufficient_data(self, db):
        """Should not fetch when >10 bars exist and cover start date."""
        start = date(2024, 1, 1)
        end = date(2024, 6, 1)
        # Pre-populate with 15 bars starting from start date
        bars = [_make_bar(start + timedelta(days=i)) for i in range(15)]
        db.save_prices(bars)

        mock_provider = MagicMock()
        with patch("haoinvest.analysis.cache.get_provider", return_value=mock_provider):
            ensure_prices_cached(db, "600519", MarketType.A_SHARE, start, end)

        mock_provider.get_price_history.assert_not_called()

    def test_gap_fills_earlier_data(self, db):
        """Should fetch missing earlier portion when cached data starts too late."""
        start = date(2024, 1, 1)
        end = date(2024, 6, 1)
        # Cached data starts 30 days after requested start
        cached_start = start + timedelta(days=30)
        bars = [_make_bar(cached_start + timedelta(days=i)) for i in range(15)]
        db.save_prices(bars)

        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = []
        with patch("haoinvest.analysis.cache.get_provider", return_value=mock_provider):
            ensure_prices_cached(db, "600519", MarketType.A_SHARE, start, end)

        mock_provider.get_price_history.assert_called_once_with(
            "600519", start, cached_start
        )
