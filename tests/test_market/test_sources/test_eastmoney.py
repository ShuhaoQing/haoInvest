"""Tests for eastmoney data source."""

from unittest.mock import MagicMock, patch

from haoinvest.market.sources.eastmoney import get_basic_info, get_financial_indicators


class TestGetFinancialIndicators:
    """Test get_financial_indicators with mocked datacenter API."""

    def _mock_response(self, json_data, status_code=200):
        mock_resp = MagicMock()
        mock_resp.json.return_value = json_data
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = status_code
        return mock_resp

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_successful_response(self, mock_get):
        mock_get.return_value = self._mock_response(
            {
                "success": True,
                "code": 0,
                "result": {
                    "data": [
                        {
                            "SECURITY_CODE": "600519",
                            "REPORTDATE": "2025-09-30 00:00:00",
                            "WEIGHTAVG_ROE": 24.64,
                            "XSMLL": 91.29,
                            "TOTAL_OPERATE_INCOME": 130903889634.88,
                            "PARENT_NETPROFIT": 64626746712.18,
                        }
                    ],
                    "count": 100,
                },
            }
        )

        result = get_financial_indicators("600519")

        assert result["roe"] == 24.64
        assert result["gross_margin"] == 91.29
        assert (
            result["profit_margin"] == 49.37
        )  # 64626746712.18 / 130903889634.88 * 100
        mock_get.assert_called_once()

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_api_failure_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        result = get_financial_indicators("600519")
        assert result == {}

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_empty_result_returns_empty(self, mock_get):
        mock_get.return_value = self._mock_response(
            {"success": True, "result": {"data": [], "count": 0}}
        )
        result = get_financial_indicators("600519")
        assert result == {}

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_unsuccessful_response(self, mock_get):
        mock_get.return_value = self._mock_response(
            {"success": False, "result": None, "code": 9501}
        )
        result = get_financial_indicators("600519")
        assert result == {}

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_missing_revenue_skips_profit_margin(self, mock_get):
        mock_get.return_value = self._mock_response(
            {
                "success": True,
                "result": {
                    "data": [
                        {
                            "WEIGHTAVG_ROE": 15.0,
                            "XSMLL": 60.0,
                            "TOTAL_OPERATE_INCOME": None,
                            "PARENT_NETPROFIT": 1000000,
                        }
                    ],
                },
            }
        )
        result = get_financial_indicators("600519")
        assert result["roe"] == 15.0
        assert result["gross_margin"] == 60.0
        assert "profit_margin" not in result


class TestGetBasicInfo:
    """Test get_basic_info with mocked CompanySurvey API."""

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "jbzl": {
                "agjc": "贵州茅台",
                "sshy": "白酒",
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        info = get_basic_info("600519")
        assert info.name == "贵州茅台"
        assert info.sector == "白酒"
        assert info.currency == "CNY"
        assert info.market_type == "a_share"
        # Verify SH prefix used
        call_params = mock_get.call_args[1]["params"]
        assert call_params["code"] == "SH600519"

    @patch("haoinvest.market.sources.eastmoney.requests.get")
    def test_sz_prefix(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"jbzl": {"agjc": "五粮液", "sshy": "白酒"}}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        get_basic_info("000858")
        call_params = mock_get.call_args[1]["params"]
        assert call_params["code"] == "SZ000858"
