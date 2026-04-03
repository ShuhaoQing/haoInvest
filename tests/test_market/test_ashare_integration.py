"""Integration tests for A-share provider — calls real APIs.

Run with: uv run pytest -m integration
"""

from datetime import date

import pytest

from haoinvest.market.ashare_provider import AShareProvider
from haoinvest.market.sources import eastmoney, sina


@pytest.mark.integration
class TestAShareIntegration:
    def test_get_current_price_moutai(self):
        provider = AShareProvider()
        price = provider.get_current_price("600519")
        assert price > 0

    def test_get_price_history_moutai(self):
        provider = AShareProvider()
        bars = provider.get_price_history("600519", date(2026, 1, 2), date(2026, 1, 10))
        assert len(bars) > 0
        assert bars[0].close > 0

    def test_get_basic_info_moutai(self):
        provider = AShareProvider()
        info = provider.get_basic_info("600519")
        assert info.name != ""
        assert info.currency == "CNY"

    def test_financial_indicators_moutai(self):
        result = eastmoney.get_financial_indicators("600519")
        assert result.get("roe") is not None
        assert result["roe"] > 0
        assert result.get("gross_margin") is not None

    def test_sector_list(self):
        rows = sina.get_sector_list()
        assert len(rows) > 0
        assert rows[0]["name"] != ""

    def test_sector_constituents(self):
        # Sina uses "酿酒行业" (not eastmoney's "白酒")
        rows = sina.get_sector_constituents("酿酒行业")
        assert len(rows) > 0
        codes = [r["code"] for r in rows]
        assert "600519" in codes
