"""Tests for peer comparison analysis."""

from unittest.mock import patch

from typer.testing import CliRunner

from haoinvest.analysis.peer import find_peers
from haoinvest.cli import app
from haoinvest.models import FundamentalAnalysis, MarketType

runner = CliRunner()

MOCK_FUNDAMENTAL = FundamentalAnalysis(
    symbol="600519",
    name="贵州茅台",
    sector="白酒",
    market_type="a_share",
    current_price=1800.0,
)

MOCK_CONSTITUENTS = [
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
    {
        "code": "000568",
        "name": "泸州老窖",
        "price": 200.0,
        "change_pct": -0.5,
        "pe_ratio": 25.0,
        "pb_ratio": 7.0,
        "total_market_cap": 300000000000,
    },
]


class TestFindPeers:
    def test_a_share_peers(self):
        with (
            patch(
                "haoinvest.analysis.peer.analyze_stock", return_value=MOCK_FUNDAMENTAL
            ),
            patch(
                "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
                return_value=MOCK_CONSTITUENTS,
            ),
        ):
            rows = find_peers("600519", MarketType.A_SHARE, top_n=5)
            assert len(rows) == 3
            assert rows[0]["Symbol"] == "600519"
            assert rows[0]["is_target"] is True
            assert rows[1]["Symbol"] == "000858"

    def test_us_stock_unsupported(self):
        rows = find_peers("AAPL", MarketType.US)
        assert "message" in rows[0]
        assert "not yet supported" in rows[0]["message"]

    def test_no_sector_info(self):
        mock = FundamentalAnalysis(
            symbol="600519", sector="", market_type="a_share", current_price=1800.0
        )
        with patch("haoinvest.analysis.peer.analyze_stock", return_value=mock):
            rows = find_peers("600519", MarketType.A_SHARE)
            assert "message" in rows[0]

    def test_top_n_limit(self):
        with (
            patch(
                "haoinvest.analysis.peer.analyze_stock", return_value=MOCK_FUNDAMENTAL
            ),
            patch(
                "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
                return_value=MOCK_CONSTITUENTS,
            ),
        ):
            rows = find_peers("600519", MarketType.A_SHARE, top_n=2)
            assert len(rows) == 2


class TestPeerCLI:
    def test_peer_command(self):
        with (
            patch(
                "haoinvest.analysis.peer.analyze_stock", return_value=MOCK_FUNDAMENTAL
            ),
            patch(
                "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
                return_value=MOCK_CONSTITUENTS,
            ),
        ):
            result = runner.invoke(app, ["analyze", "peer", "600519"])
            assert result.exit_code == 0
            assert "600519" in result.output
            assert "贵州茅台" in result.output

    def test_peer_json(self):
        with (
            patch(
                "haoinvest.analysis.peer.analyze_stock", return_value=MOCK_FUNDAMENTAL
            ),
            patch(
                "haoinvest.market.ashare_provider.AShareProvider.get_sector_constituents",
                return_value=MOCK_CONSTITUENTS,
            ),
        ):
            result = runner.invoke(app, ["analyze", "peer", "600519", "--json"])
            assert result.exit_code == 0
            assert '"Symbol": "600519"' in result.output

    def test_peer_us_unsupported(self):
        result = runner.invoke(app, ["analyze", "peer", "AAPL"])
        assert result.exit_code == 0
        assert "not yet supported" in result.output
