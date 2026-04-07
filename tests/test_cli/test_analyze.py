"""Tests for haoinvest analyze CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from haoinvest.cli import app
from haoinvest.models import FundamentalAnalysis, RiskMetrics, ValuationAssessment

runner = CliRunner()


class TestAnalyzeFundamental:
    def test_fundamental_a_share(self):
        mock_result = FundamentalAnalysis(
            symbol="600519",
            name="贵州茅台",
            sector="白酒",
            market_type="a_share",
            current_price=1800.0,
            currency="CNY",
            pe_ratio=35.2,
            pb_ratio=12.1,
            total_market_cap=2100000000000,
            valuation=ValuationAssessment(
                pe_assessment="偏高 (25 ≤ PE < 40)",
                pb_assessment="高估 (PB ≥ 6)",
                overall="偏高估",
            ),
        )
        with patch("haoinvest.cli.analyze.analyze_stock", return_value=mock_result):
            result = runner.invoke(app, ["analyze", "fundamental", "600519"])
            assert result.exit_code == 0
            assert "贵州茅台" in result.output
            assert "偏高估" in result.output

    def test_fundamental_sz_stock(self):
        mock_result = FundamentalAnalysis(
            symbol="000001",
            name="平安银行",
            sector="银行",
            market_type="a_share",
            current_price=12.5,
            currency="CNY",
            pe_ratio=5.3,
            pb_ratio=0.6,
            total_market_cap=240000000000,
            valuation=ValuationAssessment(
                pe_assessment="低估 (PE < 15)",
                pb_assessment="低估 (PB < 1)",
                overall="偏低估",
            ),
        )
        with patch("haoinvest.cli.analyze.analyze_stock", return_value=mock_result):
            result = runner.invoke(app, ["analyze", "fundamental", "000001"])
            assert result.exit_code == 0
            assert "平安银行" in result.output

    def test_fundamental_not_found(self):
        with patch(
            "haoinvest.cli.analyze.analyze_stock", side_effect=ValueError("not found")
        ):
            result = runner.invoke(app, ["analyze", "fundamental", "999999"])
            assert result.exit_code == 1

    def test_fundamental_json(self):
        mock_result = FundamentalAnalysis(
            symbol="600519",
            name="贵州茅台",
            sector="白酒",
            market_type="a_share",
            current_price=1800.0,
            currency="CNY",
            pe_ratio=35.2,
            pb_ratio=12.1,
            valuation=ValuationAssessment(
                pe_assessment="偏高", pb_assessment="高估", overall="偏高估"
            ),
        )
        with patch("haoinvest.cli.analyze.analyze_stock", return_value=mock_result):
            result = runner.invoke(app, ["analyze", "fundamental", "600519", "--json"])
            assert result.exit_code == 0
            assert '"symbol": "600519"' in result.output


class TestAnalyzeFundamentalBatch:
    """Unit tests for batch 'haoinvest analyze fundamental A,B'."""

    def test_fundamental_batch_two_symbols(self):
        mock_results = [
            FundamentalAnalysis(
                symbol="600519",
                name="贵州茅台",
                sector="白酒",
                market_type="a_share",
                current_price=1800.0,
                currency="CNY",
                pe_ratio=35.2,
                pb_ratio=12.1,
                valuation=ValuationAssessment(overall="偏高估"),
                roe=25.0,
                revenue_growth=15.0,
                profit_margin=50.0,
                debt_to_equity=30.0,
            ),
            FundamentalAnalysis(
                symbol="000001",
                name="平安银行",
                sector="银行",
                market_type="a_share",
                current_price=12.5,
                currency="CNY",
                pe_ratio=5.3,
                pb_ratio=0.6,
                valuation=ValuationAssessment(overall="偏低估"),
                roe=10.0,
                revenue_growth=8.0,
                profit_margin=30.0,
                debt_to_equity=200.0,
            ),
        ]
        with patch("haoinvest.cli.analyze.analyze_stock", side_effect=mock_results):
            result = runner.invoke(app, ["analyze", "fundamental", "600519,000001"])
            assert result.exit_code == 0
            assert "贵州茅台" in result.output
            assert "平安银行" in result.output
            assert "偏高估" in result.output
            assert "偏低估" in result.output

    def test_fundamental_batch_one_error(self):
        mock_result = FundamentalAnalysis(
            symbol="600519",
            name="贵州茅台",
            sector="白酒",
            market_type="a_share",
            current_price=1800.0,
            currency="CNY",
            valuation=ValuationAssessment(overall="偏高估"),
        )
        with patch(
            "haoinvest.cli.analyze.analyze_stock",
            side_effect=[mock_result, ValueError("not found")],
        ):
            result = runner.invoke(app, ["analyze", "fundamental", "600519,999999"])
            assert result.exit_code == 0
            assert "贵州茅台" in result.output
            assert "ERROR" in result.output


class TestAnalyzeTechnicalBatch:
    """Unit tests for batch 'haoinvest analyze technical A,B'."""

    def test_technical_batch_two_symbols(self, tmp_path, monkeypatch):
        from haoinvest.models import (
            BollingerBands,
            MACDResult,
            MovingAverages,
            RSIResult,
            TechnicalIndicators,
        )

        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_results = [
            TechnicalIndicators(
                symbol="600519",
                market_type="a_share",
                latest_close=1800.0,
                moving_averages=MovingAverages(trend="上升趋势"),
                macd=MACDResult(signal="金叉"),
                rsi=RSIResult(rsi=55.0, assessment="中性"),
                bollinger=BollingerBands(position="中轨附近"),
            ),
            TechnicalIndicators(
                symbol="000001",
                market_type="a_share",
                latest_close=12.5,
                moving_averages=MovingAverages(trend="下降趋势"),
                macd=MACDResult(signal="死叉"),
                rsi=RSIResult(rsi=30.0, assessment="超卖"),
                bollinger=BollingerBands(position="下轨附近"),
            ),
        ]
        with patch("haoinvest.cli.analyze.ensure_prices_cached"):
            with patch(
                "haoinvest.cli.analyze.analyze_technical", side_effect=mock_results
            ):
                result = runner.invoke(app, ["analyze", "technical", "600519,000001"])
                assert result.exit_code == 0
                assert "上升趋势" in result.output
                assert "下降趋势" in result.output
                assert "金叉" in result.output
                assert "死叉" in result.output


class TestAnalyzeRisk:
    def test_risk_no_holdings(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        result = runner.invoke(app, ["analyze", "risk"])
        assert result.exit_code == 0
        assert "(no holdings)" in result.output

    def test_risk_single_symbol(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_metrics = RiskMetrics(
            annualized_volatility=25.5,
            max_drawdown_pct=15.3,
            sharpe_ratio=0.85,
            total_return_pct=12.0,
            num_days=252,
        )
        with patch("haoinvest.cli.analyze.ensure_prices_cached"):
            with patch(
                "haoinvest.cli.analyze.calculate_risk_metrics",
                return_value=mock_metrics,
            ):
                result = runner.invoke(app, ["analyze", "risk", "--symbol", "600519"])
                assert result.exit_code == 0
                assert "25.5" in result.output


class TestAnalyzeIntegration:
    @pytest.mark.integration
    def test_fundamental_600519_real(self):
        result = runner.invoke(app, ["analyze", "fundamental", "600519"])
        assert result.exit_code == 0
        assert "贵州茅台" in result.output
        assert "Overall_Valuation:" in result.output

    @pytest.mark.integration
    def test_fundamental_000001_real(self):
        result = runner.invoke(app, ["analyze", "fundamental", "000001"])
        assert result.exit_code == 0
        assert "Price:" in result.output
