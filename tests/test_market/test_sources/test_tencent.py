"""Tests for Tencent Finance data source."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from haoinvest.market.sources.tencent import (
    get_current_price,
    get_price_history,
    get_valuation,
)


class TestGetCurrentPrice:
    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_success(self, mock_get):
        # Tencent format: fields separated by ~, price at index 3
        fields = [""] * 50
        fields[3] = "1682.50"
        mock_resp = MagicMock()
        mock_resp.text = "~".join(fields)
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        price = get_current_price("600519")
        assert price == 1682.50

    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "~~"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found"):
            get_current_price("999999")


class TestGetPriceHistory:
    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "sh600519": {
                    "qfqday": [
                        # [date, open, close, high, low, volume]
                        [
                            "2026-03-25",
                            "1670.00",
                            "1680.00",
                            "1685.00",
                            "1665.00",
                            "10000",
                        ],
                        [
                            "2026-03-26",
                            "1675.00",
                            "1685.00",
                            "1690.00",
                            "1670.00",
                            "12000",
                        ],
                    ]
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        bars = get_price_history("600519", date(2026, 3, 25), date(2026, 3, 27))
        assert len(bars) == 2
        assert bars[0].trade_date == date(2026, 3, 25)
        assert bars[0].open == 1670.0
        assert bars[0].close == 1680.0
        assert bars[0].high == 1685.0
        assert bars[0].low == 1665.0
        assert bars[0].volume == 10000.0

    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_filters_out_of_range_dates(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "sh600519": {
                    "qfqday": [
                        ["2026-03-24", "1660", "1665", "1670", "1655", "9000"],
                        ["2026-03-25", "1670", "1680", "1685", "1665", "10000"],
                    ]
                }
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        bars = get_price_history("600519", date(2026, 3, 25), date(2026, 3, 27))
        assert len(bars) == 1
        assert bars[0].trade_date == date(2026, 3, 25)


class TestGetValuation:
    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_success(self, mock_get):
        # Build Tencent quote response with PE at index 39, cap at 45, PB at 46
        fields = [""] * 50
        fields[39] = "30.5"  # PE TTM
        fields[45] = "21000"  # total market cap in 亿元
        fields[46] = "10.2"  # PB
        mock_resp = MagicMock()
        mock_resp.text = "~".join(fields)
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        val = get_valuation("600519")
        assert val["pe_ratio"] == 30.5
        assert val["pb_ratio"] == 10.2
        assert val["total_market_cap"] == 21000 * 1_0000_0000

    @patch("haoinvest.market.sources.tencent.requests.get")
    def test_failure_returns_defaults(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        val = get_valuation("600519")
        assert val["pe_ratio"] is None
        assert val["pb_ratio"] is None
        assert val["total_market_cap"] is None
