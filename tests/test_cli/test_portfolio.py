"""Tests for haoinvest portfolio CLI commands."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from haoinvest.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for all portfolio tests."""
    monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))


class TestPortfolioList:

    def test_empty_portfolio(self):
        result = runner.invoke(app, ["portfolio", "list"])
        assert result.exit_code == 0
        assert "(no holdings)" in result.output

    def test_list_after_trade(self):
        # Add a trade first
        runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--market-type", "a_share",
        ])
        result = runner.invoke(app, ["portfolio", "list"])
        assert result.exit_code == 0
        assert "600519" in result.output
        assert "100" in result.output

    def test_list_json(self):
        runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--market-type", "a_share",
        ])
        result = runner.invoke(app, ["portfolio", "list", "--json"])
        assert result.exit_code == 0
        assert '"symbol": "600519"' in result.output


class TestPortfolioAddTrade:

    def test_add_buy(self):
        result = runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--fee", "5", "--market-type", "a_share",
        ])
        assert result.exit_code == 0
        assert "transaction_id" in result.output

    def test_add_sell(self):
        runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--market-type", "a_share",
        ])
        result = runner.invoke(app, [
            "portfolio", "add-trade", "600519", "sell", "50", "1900",
            "--market-type", "a_share",
        ])
        assert result.exit_code == 0
        assert "sell" in result.output

    def test_invalid_action(self):
        result = runner.invoke(app, [
            "portfolio", "add-trade", "600519", "invalid_action", "100", "1800",
        ])
        assert result.exit_code == 1

    def test_add_crypto_trade(self):
        result = runner.invoke(app, [
            "portfolio", "add-trade", "BTC_USDT", "buy", "0.5", "87000",
            "--market-type", "crypto", "--currency", "USD",
        ])
        assert result.exit_code == 0
        assert "BTC_USDT" in result.output

    def test_auto_detect_market_type(self):
        result = runner.invoke(app, [
            "portfolio", "add-trade", "000001", "buy", "200", "12.5",
        ])
        assert result.exit_code == 0


class TestPortfolioReturns:

    def test_returns_empty(self):
        result = runner.invoke(app, ["portfolio", "returns"])
        assert result.exit_code == 0
        assert "(no holdings)" in result.output

    def test_returns_single_symbol(self):
        # Add a trade, then check returns with mocked price
        runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--market-type", "a_share",
        ])
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 1900.0
        with patch("haoinvest.cli.portfolio.get_provider", return_value=mock_provider):
            result = runner.invoke(app, ["portfolio", "returns", "--symbol", "600519"])
            assert result.exit_code == 0
            assert "unrealized_pnl" in result.output


class TestPortfolioIntegration:

    @pytest.mark.integration
    def test_add_trade_and_list(self):
        result = runner.invoke(app, [
            "portfolio", "add-trade", "600519", "buy", "100", "1800",
            "--market-type", "a_share",
        ])
        assert result.exit_code == 0

        result = runner.invoke(app, ["portfolio", "list"])
        assert result.exit_code == 0
        assert "600519" in result.output
