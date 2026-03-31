"""Contract tests: all providers must satisfy the MarketProvider interface."""

from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from haoinvest.market.akshare_provider import AKShareProvider
from haoinvest.market.crypto_provider import CryptoProvider, _normalize_symbol, _to_coingecko_id


class TestAKShareProviderContract:
    """Test AKShareProvider with mocked AKShare responses."""

    def test_get_current_price(self):
        mock_df = pd.DataFrame({
            "代码": ["600519", "000001"],
            "最新价": [1680.0, 12.5],
        })
        mock_ak = MagicMock()
        mock_ak.stock_zh_a_spot_em.return_value = mock_df
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            provider = AKShareProvider()
            price = provider.get_current_price("600519")
            assert price == 1680.0

    def test_get_current_price_not_found(self):
        mock_df = pd.DataFrame({"代码": ["000001"], "最新价": [12.5]})
        mock_ak = MagicMock()
        mock_ak.stock_zh_a_spot_em.return_value = mock_df
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            provider = AKShareProvider()
            with pytest.raises(ValueError, match="not found"):
                provider.get_current_price("999999")

    def test_get_price_history(self):
        mock_df = pd.DataFrame({
            "日期": ["2026-03-25", "2026-03-26", "2026-03-27"],
            "开盘": [1670.0, 1675.0, 1680.0],
            "最高": [1685.0, 1690.0, 1695.0],
            "最低": [1665.0, 1670.0, 1675.0],
            "收盘": [1680.0, 1685.0, 1690.0],
            "成交量": [10000, 12000, 11000],
        })
        mock_ak = MagicMock()
        mock_ak.stock_zh_a_hist.return_value = mock_df
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            provider = AKShareProvider()
            bars = provider.get_price_history("600519", date(2026, 3, 25), date(2026, 3, 27))
            assert len(bars) == 3
            assert bars[0].close == 1680.0
            assert bars[0].trade_date == date(2026, 3, 25)

    def test_get_basic_info(self):
        mock_df = pd.DataFrame({
            "item": ["股票简称", "行业", "总市值", "市盈率(动态)", "市净率"],
            "value": ["贵州茅台", "白酒", "2100000000000", "30.5", "10.2"],
        })
        mock_ak = MagicMock()
        mock_ak.stock_individual_info_em.return_value = mock_df
        with patch.dict("sys.modules", {"akshare": mock_ak}):
            provider = AKShareProvider()
            info = provider.get_basic_info("600519")
            assert info.name == "贵州茅台"
            assert info.currency == "CNY"
            assert info.pe_ratio == 30.5
            assert info.pb_ratio == 10.2
            assert info.total_market_cap == 2100000000000


class TestCryptoProviderHelpers:
    def test_normalize_symbol(self):
        assert _normalize_symbol("BTC_USDT") == "BTC"
        assert _normalize_symbol("ETH/USDT") == "ETH"
        assert _normalize_symbol("BTC") == "BTC"

    def test_to_coingecko_id(self):
        assert _to_coingecko_id("BTC_USDT") == "bitcoin"
        assert _to_coingecko_id("ETH") == "ethereum"
        assert _to_coingecko_id("SOME_UNKNOWN") == "some"


class TestCryptoProviderContract:
    """Test CryptoProvider with mocked HTTP responses."""

    def _make_provider_with_mock_client(self) -> tuple[CryptoProvider, MagicMock]:
        provider = CryptoProvider()
        mock_client = MagicMock()
        provider._client = mock_client
        return provider, mock_client

    def test_get_current_price(self):
        provider, mock_client = self._make_provider_with_mock_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"bitcoin": {"usd": 87000.0}}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        price = provider.get_current_price("BTC_USDT")
        assert price == 87000.0

    def test_get_current_price_not_found(self):
        provider, mock_client = self._make_provider_with_mock_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        with pytest.raises(ValueError, match="not found"):
            provider.get_current_price("NONEXIST")

    def test_get_basic_info(self):
        provider, mock_client = self._make_provider_with_mock_client()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "name": "Bitcoin",
            "market_data": {
                "market_cap": {"usd": 1700000000000},
                "total_supply": 21000000,
            },
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_resp

        info = provider.get_basic_info("BTC")
        assert info.name == "Bitcoin"
        assert info.sector == "crypto"
        assert info.currency == "USD"
