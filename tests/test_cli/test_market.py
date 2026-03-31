"""Tests for haoinvest market CLI commands."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from haoinvest.cli import app

runner = CliRunner()


class TestMarketQuote:
    """Unit tests for 'haoinvest market quote'."""

    def test_quote_a_share(self):
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 1800.0
        mock_provider.get_basic_info.return_value = {
            "name": "贵州茅台",
            "currency": "CNY",
            "sector": "白酒",
            "pe_ratio": 35.2,
            "pb_ratio": 12.1,
            "total_market_cap": 2100000000000,
        }
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "quote", "600519"])
            assert result.exit_code == 0
            assert "贵州茅台" in result.output
            assert "1800.0" in result.output

    def test_quote_sz_stock(self):
        """Test Shenzhen stock (000001 Ping An Bank)."""
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 12.5
        mock_provider.get_basic_info.return_value = {
            "name": "平安银行",
            "currency": "CNY",
            "sector": "银行",
            "pe_ratio": 5.3,
            "pb_ratio": 0.6,
            "total_market_cap": 240000000000,
        }
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "quote", "000001"])
            assert result.exit_code == 0
            assert "平安银行" in result.output

    def test_quote_json_output(self):
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 1800.0
        mock_provider.get_basic_info.return_value = {
            "name": "贵州茅台", "currency": "CNY", "sector": "白酒",
            "pe_ratio": 35.2, "pb_ratio": 12.1, "total_market_cap": None,
        }
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "quote", "600519", "--json"])
            assert result.exit_code == 0
            assert '"Name": "贵州茅台"' in result.output

    def test_quote_not_found(self):
        mock_provider = MagicMock()
        mock_provider.get_current_price.side_effect = ValueError("Symbol 999999 not found")
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "quote", "999999"])
            assert result.exit_code == 1

    def test_quote_with_market_type_override(self):
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 170.0
        mock_provider.get_basic_info.return_value = {
            "name": "Apple", "currency": "USD", "sector": "Tech",
            "pe_ratio": 28.0, "pb_ratio": 45.0, "total_market_cap": None,
        }
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "quote", "AAPL", "--market-type", "us"])
            assert result.exit_code == 0
            assert "Apple" in result.output


class TestMarketHistory:
    """Unit tests for 'haoinvest market history'."""

    def test_history_a_share(self):
        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = [
            {"date": date(2026, 3, 25), "open": 1670.0, "high": 1685.0, "low": 1665.0, "close": 1680.0, "volume": 10000},
            {"date": date(2026, 3, 26), "open": 1675.0, "high": 1690.0, "low": 1670.0, "close": 1685.0, "volume": 12000},
        ]
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "history", "600519", "--start", "2026-03-25", "--end", "2026-03-26"])
            assert result.exit_code == 0
            assert "1680.0" in result.output
            assert "2026-03-25" in result.output

    def test_history_empty(self):
        mock_provider = MagicMock()
        mock_provider.get_price_history.return_value = []
        with patch("haoinvest.cli.market.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["market", "history", "600519"])
            assert result.exit_code == 0
            assert "(empty)" in result.output


class TestMarketIntegration:
    """Integration tests — real API calls."""

    @pytest.mark.integration
    def test_quote_600519_real(self):
        result = runner.invoke(app, ["market", "quote", "600519"])
        assert result.exit_code == 0
        assert "贵州茅台" in result.output
        assert "Price:" in result.output

    @pytest.mark.integration
    def test_quote_000001_real(self):
        result = runner.invoke(app, ["market", "quote", "000001"])
        assert result.exit_code == 0
        assert "Price:" in result.output

    @pytest.mark.integration
    def test_history_600519_real(self):
        result = runner.invoke(app, ["market", "history", "600519", "--start", "2026-03-01", "--end", "2026-03-15"])
        assert result.exit_code == 0
        assert "2026-03" in result.output

    @pytest.mark.integration
    def test_quote_json_real(self):
        result = runner.invoke(app, ["market", "quote", "600519", "--json"])
        assert result.exit_code == 0
        assert '"Symbol": "600519"' in result.output
