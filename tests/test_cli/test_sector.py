"""Tests for haoinvest market sector CLI commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from haoinvest.cli import app

runner = CliRunner()

MOCK_SECTOR_LIST = [
    {
        "name": "白酒",
        "change_pct": 2.15,
        "total_market_cap": 5000000000000,
        "turnover_rate": 1.23,
        "rise_count": 15,
        "fall_count": 3,
    },
    {
        "name": "银行",
        "change_pct": -0.32,
        "total_market_cap": 8000000000000,
        "turnover_rate": 0.45,
        "rise_count": 10,
        "fall_count": 20,
    },
]

MOCK_SECTOR_CONSTITUENTS = [
    {
        "code": "600519",
        "name": "贵州茅台",
        "price": 1800.0,
        "change_pct": 1.5,
        "pe_ratio": 35.2,
        "pb_ratio": 12.1,
        "total_market_cap": 2100000000000,
    },
    {
        "code": "000858",
        "name": "五粮液",
        "price": 150.0,
        "change_pct": 0.8,
        "pe_ratio": 22.5,
        "pb_ratio": 5.3,
        "total_market_cap": 580000000000,
    },
]


class TestSectorList:
    def test_sector_list_tsv(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_list",
            return_value=MOCK_SECTOR_LIST,
        ):
            result = runner.invoke(app, ["market", "sector-list"])
            assert result.exit_code == 0
            assert "白酒" in result.output
            assert "银行" in result.output

    def test_sector_list_json(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_list",
            return_value=MOCK_SECTOR_LIST,
        ):
            result = runner.invoke(app, ["market", "sector-list", "--json"])
            assert result.exit_code == 0
            assert '"name": "白酒"' in result.output

    def test_sector_list_error(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_list",
            side_effect=RuntimeError("API failed"),
        ):
            result = runner.invoke(app, ["market", "sector-list"])
            assert result.exit_code == 1


class TestSector:
    def test_sector_constituents_tsv(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
            return_value=MOCK_SECTOR_CONSTITUENTS,
        ):
            result = runner.invoke(app, ["market", "sector", "白酒"])
            assert result.exit_code == 0
            assert "600519" in result.output
            assert "贵州茅台" in result.output
            assert "000858" in result.output

    def test_sector_constituents_json(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
            return_value=MOCK_SECTOR_CONSTITUENTS,
        ):
            result = runner.invoke(app, ["market", "sector", "白酒", "--json"])
            assert result.exit_code == 0
            assert '"code": "600519"' in result.output

    def test_sector_not_found(self):
        with patch(
            "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
            side_effect=RuntimeError("Sector not found"),
        ):
            result = runner.invoke(app, ["market", "sector", "不存在的板块"])
            assert result.exit_code == 1
