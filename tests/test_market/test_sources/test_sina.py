"""Tests for Sina Finance data source."""

from unittest.mock import MagicMock, patch

import pytest

from haoinvest.market.sources.sina import (
    get_current_price,
    get_sector_constituents,
    get_sector_list,
)


class TestGetCurrentPrice:
    @patch("haoinvest.market.sources.sina.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = 'var hq_str_sh600519="贵州茅台,1680.00,1675.00,1682.50,1690.00,1670.00,...";'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        price = get_current_price("600519")
        assert price == 1682.50

    @patch("haoinvest.market.sources.sina.requests.get")
    def test_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = 'var hq_str_sh999999="";'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found"):
            get_current_price("999999")

    @patch("haoinvest.market.sources.sina.requests.get")
    def test_sz_prefix(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = (
            'var hq_str_sz000858="五粮液,150.00,148.00,151.20,153.00,149.00,...";'
        )
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        price = get_current_price("000858")
        assert price == 151.20
        # Verify sz prefix used
        call_url = mock_get.call_args[0][0]
        assert "sz000858" in call_url


class TestGetSectorList:
    @patch("haoinvest.market.sources.sina._fetch_sector_data")
    def test_success(self, mock_fetch):
        mock_fetch.return_value = {
            "new_blhy": "code1,白酒,10,100,2.5,3.15,1000,500,600519,0.5,1680,10,茅台".split(
                ","
            ),
            "new_yh": "code2,银行,20,50,1.0,-0.32,2000,800,601398,0.3,5.5,0.1,工行".split(
                ","
            ),
        }
        rows = get_sector_list()
        assert len(rows) == 2
        # Sorted by change_pct descending
        assert rows[0]["name"] == "白酒"
        assert rows[0]["change_pct"] == 3.15
        assert rows[1]["name"] == "银行"
        assert rows[1]["change_pct"] == -0.32


class TestGetSectorConstituents:
    @patch("haoinvest.market.sources.sina.requests.get")
    @patch("haoinvest.market.sources.sina._fetch_sector_data")
    def test_success(self, mock_fetch, mock_get):
        mock_fetch.return_value = {
            "new_blhy": "code1,白酒,10,100,2.5,3.15".split(","),
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1680.00",
                "changepercent": "1.5",
                "per": "35.2",
                "pb": "12.1",
                "mktcap": 210000,
            },
        ]
        mock_resp.encoding = "gbk"
        mock_get.return_value = mock_resp

        rows = get_sector_constituents("白酒")
        assert len(rows) == 1
        assert rows[0]["code"] == "600519"
        assert rows[0]["price"] == 1680.0
        assert rows[0]["total_market_cap"] == 2100000000

    @patch("haoinvest.market.sources.sina._fetch_sector_data")
    def test_sector_not_found(self, mock_fetch):
        mock_fetch.return_value = {
            "new_blhy": "code1,白酒,10,100,2.5,3.15".split(","),
        }
        with pytest.raises(ValueError, match="not found"):
            get_sector_constituents("不存在的板块")
