"""Tests for haoinvest strategy CLI commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from haoinvest.cli import app
from haoinvest.models import AllocationSuggestion, RebalanceTrade

runner = CliRunner()


class TestStrategyOptimize:
    def test_optimize_no_holdings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        result = runner.invoke(app, ["strategy", "optimize"])
        assert result.exit_code == 0
        assert "(no holdings)" in result.output

    def test_optimize_with_symbols(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_result = AllocationSuggestion(
            method="equal_weight",
            weights={"600519": 0.5, "000001": 0.5},
            explanation="等权配置",
        )
        with patch("haoinvest.cli.strategy.ensure_prices_cached"):
            with patch(
                "haoinvest.cli.strategy.suggest_allocation", return_value=mock_result
            ):
                result = runner.invoke(
                    app,
                    [
                        "strategy",
                        "optimize",
                        "--symbols",
                        "600519,000001",
                        "--method",
                        "equal_weight",
                    ],
                )
                assert result.exit_code == 0
                assert "600519" in result.output
                assert "50.0" in result.output

    def test_optimize_invalid_method(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with patch("haoinvest.cli.strategy.ensure_prices_cached"):
            with patch(
                "haoinvest.cli.strategy.suggest_allocation",
                side_effect=ValueError("Unknown method"),
            ):
                result = runner.invoke(
                    app,
                    [
                        "strategy",
                        "optimize",
                        "--symbols",
                        "600519",
                        "--method",
                        "bad_method",
                    ],
                )
                assert result.exit_code == 1


class TestStrategyRebalance:
    def test_rebalance_missing_target(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        result = runner.invoke(app, ["strategy", "rebalance"])
        assert result.exit_code == 1

    def test_rebalance_invalid_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        result = runner.invoke(app, ["strategy", "rebalance", "--target", "not-json"])
        assert result.exit_code == 1

    def test_rebalance_with_trades(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_trades = [
            RebalanceTrade(
                symbol="600519",
                action="buy",
                quantity=10,
                price=1800.0,
                current_weight=30.0,
                target_weight=50.0,
                trade_value=36000.0,
            ),
        ]
        mock_provider = MagicMock()
        mock_provider.get_current_price.return_value = 1800.0
        with patch("haoinvest.cli.strategy.get_provider", return_value=mock_provider):
            with patch(
                "haoinvest.cli.strategy.calculate_rebalance", return_value=mock_trades
            ):
                result = runner.invoke(
                    app,
                    [
                        "strategy",
                        "rebalance",
                        "--target",
                        '{"600519": 0.5}',
                    ],
                )
                assert result.exit_code == 0
                assert "600519" in result.output
                assert "buy" in result.output
