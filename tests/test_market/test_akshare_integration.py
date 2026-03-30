"""Integration tests for AKShare provider — calls real APIs.

Run with: uv run pytest -m integration
"""

from datetime import date

import pytest

from haoinvest.market.akshare_provider import AKShareProvider


@pytest.mark.integration
class TestAKShareIntegration:
    def test_get_current_price_moutai(self):
        provider = AKShareProvider()
        price = provider.get_current_price("600519")
        assert price > 0

    def test_get_price_history_moutai(self):
        provider = AKShareProvider()
        bars = provider.get_price_history("600519", date(2026, 1, 2), date(2026, 1, 10))
        assert len(bars) > 0
        assert all("close" in b for b in bars)

    def test_get_basic_info_moutai(self):
        provider = AKShareProvider()
        info = provider.get_basic_info("600519")
        assert info["name"] != ""
        assert info["currency"] == "CNY"
