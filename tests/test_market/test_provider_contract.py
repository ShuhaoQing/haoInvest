"""Contract tests: all providers must satisfy the MarketProvider interface."""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from haoinvest.market.ashare_provider import AShareProvider
from haoinvest.market.crypto_provider import (
    CryptoProvider,
    _normalize_symbol,
    _to_coingecko_id,
)
from haoinvest.models import BasicInfo, MarketType, PriceBar


class TestAShareProviderContract:
    """Test AShareProvider with mocked source modules."""

    @patch("haoinvest.market.ashare_provider.sina.get_current_price")
    def test_get_current_price(self, mock_sina_price):
        mock_sina_price.return_value = 1680.0
        provider = AShareProvider()
        price = provider.get_current_price("600519")
        assert price == 1680.0
        mock_sina_price.assert_called_once_with("600519")

    @patch("haoinvest.market.ashare_provider.tencent.get_current_price")
    @patch("haoinvest.market.ashare_provider.sina.get_current_price")
    def test_get_current_price_fallback_to_tencent(self, mock_sina, mock_tencent):
        mock_sina.side_effect = RuntimeError("Sina unavailable")
        mock_tencent.return_value = 1679.0
        provider = AShareProvider()
        price = provider.get_current_price("600519")
        assert price == 1679.0

    @patch("haoinvest.market.ashare_provider.sina.get_current_price")
    def test_get_current_price_not_found(self, mock_sina_price):
        mock_sina_price.side_effect = ValueError(
            "Symbol 999999 not found in A-share market"
        )
        provider = AShareProvider()
        with pytest.raises(ValueError, match="not found"):
            provider.get_current_price("999999")

    @patch("haoinvest.market.ashare_provider.tencent.get_price_history")
    def test_get_price_history(self, mock_tencent_history):
        mock_tencent_history.return_value = [
            PriceBar(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 3, 25),
                open=1670.0,
                high=1685.0,
                low=1665.0,
                close=1680.0,
                volume=10000,
            ),
            PriceBar(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 3, 26),
                open=1675.0,
                high=1690.0,
                low=1670.0,
                close=1685.0,
                volume=12000,
            ),
        ]
        provider = AShareProvider()
        bars = provider.get_price_history(
            "600519", date(2026, 3, 25), date(2026, 3, 27)
        )
        assert len(bars) == 2
        assert bars[0].close == 1680.0
        assert bars[0].trade_date == date(2026, 3, 25)

    @patch("haoinvest.market.ashare_provider.eastmoney.get_financial_indicators")
    @patch("haoinvest.market.ashare_provider.tencent.get_valuation")
    @patch("haoinvest.market.ashare_provider.eastmoney.get_basic_info")
    def test_get_basic_info(self, mock_em_info, mock_tencent_val, mock_em_fin):
        mock_em_info.return_value = BasicInfo(
            name="贵州茅台",
            sector="白酒",
            currency="CNY",
            market_type="a_share",
        )
        mock_tencent_val.return_value = {
            "pe_ratio": 30.5,
            "pb_ratio": 10.2,
            "total_market_cap": 2100000000000,
        }
        mock_em_fin.return_value = {"roe": 24.64, "gross_margin": 91.29}

        provider = AShareProvider()
        info = provider.get_basic_info("600519")
        assert info.name == "贵州茅台"
        assert info.currency == "CNY"
        assert info.pe_ratio == 30.5
        assert info.pb_ratio == 10.2
        assert info.total_market_cap == 2100000000000
        assert info.roe == 24.64
        assert info.gross_margin == 91.29


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
