"""Tests for the composable `analyze run` CLI command."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from haoinvest.cli import app
from haoinvest.models import (
    BollingerBands,
    FundamentalAnalysis,
    MACDResult,
    MovingAverages,
    MultiTimeframeTechnical,
    RiskMetrics,
    RSIResult,
    SignalSummary,
    TechnicalIndicators,
    ValuationAssessment,
    VolumeAnalysis,
)

runner = CliRunner()

# Patch targets: the underlying analysis functions that registry runners call
_P_FUND = "haoinvest.analysis.fundamental.analyze_stock"
_P_TECH = "haoinvest.analysis.technical.analyze_technical_multi"
_P_RISK = "haoinvest.analysis.risk.calculate_risk_metrics"
_P_VOL = "haoinvest.analysis.volume.analyze_volume"
_P_SIG = "haoinvest.analysis.signals.aggregate_signals"
_P_PEER = "haoinvest.analysis.peer.find_peers"
_P_CACHE = "haoinvest.cli.analyze.ensure_prices_cached"


def _mock_fundamental():
    return FundamentalAnalysis(
        symbol="600519",
        name="贵州茅台",
        sector="白酒",
        market_type="a_share",
        current_price=1800.0,
        currency="CNY",
        pe_ratio=35.2,
        pb_ratio=12.1,
        roe=25.0,
        revenue_growth=15.0,
        profit_margin=40.0,
        valuation=ValuationAssessment(
            pe_assessment="偏高",
            pb_assessment="高估",
            overall="偏高估",
        ),
    )


def _mock_risk():
    return RiskMetrics(
        annualized_volatility=25.5,
        max_drawdown_pct=-15.3,
        sharpe_ratio=0.85,
        total_return_pct=12.0,
        num_days=252,
    )


def _mock_signals():
    return SignalSummary(
        symbol="600519",
        market_type="a_share",
        overall_signal="偏多",
        confidence="中",
        bullish_count=3,
        bearish_count=1,
        neutral_count=0,
        details=["MA: 偏多", "MACD: 偏多"],
    )


def _mock_technical():
    daily = TechnicalIndicators(
        symbol="600519",
        market_type="a_share",
        timeframe="daily",
        latest_close=1800.0,
        moving_averages=MovingAverages(
            sma_5=1790.0, sma_10=1780.0, sma_20=1770.0, trend="上升趋势"
        ),
        macd=MACDResult(macd_line=5.0, signal_line=3.0, histogram=2.0, signal="金叉"),
        rsi=RSIResult(rsi=55.0, assessment="中性"),
        bollinger=BollingerBands(position="中轨附近"),
    )
    return MultiTimeframeTechnical(
        symbol="600519", market_type="a_share", daily=daily
    )


def _mock_volume():
    return VolumeAnalysis(
        symbol="600519",
        market_type="a_share",
        latest_volume=50000.0,
        avg_volume_20d=40000.0,
        volume_ratio=1.25,
        is_anomaly=False,
        assessment="正常",
    )


def _mock_peer():
    return [
        {"Symbol": "600519", "Name": "贵州茅台", "Price": 1800, "PE": 35.2},
        {"Symbol": "000858", "Name": "五粮液", "Price": 160, "PE": 22.3},
    ]


class TestAnalyzeRunModuleSelection:
    def test_invalid_module_name(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        result = runner.invoke(app, ["analyze", "run", "600519", "--modules", "fake"])
        assert result.exit_code == 1

    def test_single_module_fundamental(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with patch(_P_FUND, return_value=_mock_fundamental()):
            result = runner.invoke(
                app, ["analyze", "run", "600519", "--modules", "fundamental"]
            )
            assert result.exit_code == 0
            assert "=== fundamental ===" in result.output
            assert "贵州茅台" in result.output
            assert "=== risk ===" not in result.output

    def test_two_modules(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with (
            patch(_P_FUND, return_value=_mock_fundamental()),
            patch(_P_RISK, return_value=_mock_risk()),
            patch(_P_CACHE),
        ):
            result = runner.invoke(
                app, ["analyze", "run", "600519", "--modules", "fundamental,risk"]
            )
            assert result.exit_code == 0
            assert "=== fundamental ===" in result.output
            assert "=== risk ===" in result.output
            assert "25.5" in result.output

    def test_peer_module(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with patch(_P_PEER, return_value=_mock_peer()):
            result = runner.invoke(
                app, ["analyze", "run", "600519", "--modules", "peer"]
            )
            assert result.exit_code == 0
            assert "=== peer ===" in result.output
            assert "五粮液" in result.output


class TestAnalyzeRunJsonOutput:
    def test_json_single_symbol(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with (
            patch(_P_FUND, return_value=_mock_fundamental()),
            patch(_P_RISK, return_value=_mock_risk()),
            patch(_P_CACHE),
        ):
            result = runner.invoke(
                app,
                [
                    "analyze",
                    "run",
                    "600519",
                    "--modules",
                    "fundamental,risk",
                    "--json",
                ],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "fundamental" in data
            assert "risk" in data
            assert data["fundamental"]["symbol"] == "600519"

    def test_json_batch(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_a = _mock_fundamental()
        mock_b = FundamentalAnalysis(
            symbol="000858",
            name="五粮液",
            sector="白酒",
            market_type="a_share",
            current_price=160.0,
            currency="CNY",
            pe_ratio=22.3,
            pb_ratio=6.8,
            valuation=ValuationAssessment(
                pe_assessment="合理",
                pb_assessment="偏高",
                overall="估值合理",
            ),
        )
        calls = iter([mock_a, mock_b])
        with patch(_P_FUND, side_effect=lambda *a, **k: next(calls)):
            result = runner.invoke(
                app,
                [
                    "analyze",
                    "run",
                    "600519,000858",
                    "--modules",
                    "fundamental",
                    "--json",
                ],
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "600519" in data
            assert "000858" in data


class TestAnalyzeRunBatch:
    def test_batch_fundamental_text(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_a = _mock_fundamental()
        mock_b = FundamentalAnalysis(
            symbol="000858",
            name="五粮液",
            sector="白酒",
            market_type="a_share",
            current_price=160.0,
            currency="CNY",
            pe_ratio=22.3,
            pb_ratio=6.8,
            valuation=ValuationAssessment(
                pe_assessment="合理",
                pb_assessment="偏高",
                overall="估值合理",
            ),
        )
        calls = iter([mock_a, mock_b])
        with patch(_P_FUND, side_effect=lambda *a, **k: next(calls)):
            result = runner.invoke(
                app,
                ["analyze", "run", "600519,000858", "--modules", "fundamental"],
            )
            assert result.exit_code == 0
            assert "=== fundamental: 600519 ===" in result.output
            assert "=== fundamental: 000858 ===" in result.output
            assert "贵州茅台" in result.output
            assert "五粮液" in result.output


class TestAnalyzeRunChecklist:
    def test_checklist_with_dependencies(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with (
            patch(_P_FUND, return_value=_mock_fundamental()),
            patch(_P_RISK, return_value=_mock_risk()),
            patch(_P_SIG, return_value=_mock_signals()),
            patch(_P_CACHE),
        ):
            result = runner.invoke(
                app,
                [
                    "analyze",
                    "run",
                    "600519",
                    "--modules",
                    "fundamental,risk,signals,checklist",
                ],
            )
            assert result.exit_code == 0
            assert "=== checklist ===" in result.output
            assert "Recommendation" in result.output

    def test_checklist_without_deps_shows_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with patch(_P_FUND, return_value=_mock_fundamental()):
            result = runner.invoke(
                app,
                [
                    "analyze",
                    "run",
                    "600519",
                    "--modules",
                    "fundamental,checklist",
                ],
            )
            assert result.exit_code == 0
            assert "checklist requires fundamental + risk" in result.output


class TestAnalyzeRunTechnical:
    def test_technical_module(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        with (
            patch(_P_TECH, return_value=_mock_technical()),
            patch(_P_CACHE),
        ):
            result = runner.invoke(
                app, ["analyze", "run", "600519", "--modules", "technical"]
            )
            assert result.exit_code == 0
            assert "=== technical ===" in result.output
            assert "上升趋势" in result.output
