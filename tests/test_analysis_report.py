"""Tests for full_stock_report cache key correctness and checklist scoring."""

from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from haoinvest.analysis.report import (
    _compute_checklist,
    _score_growth,
    _score_profitability,
    _score_risk,
    _score_technical,
    _score_valuation,
    full_stock_report,
)
from haoinvest.cli import app
from haoinvest.db import Database
from haoinvest.models import (
    BuyReadinessChecklist,
    ChecklistItem,
    FinancialHealthAssessment,
    FundamentalAnalysis,
    MarketType,
    RiskMetrics,
    SignalSummary,
    StockReport,
    ValuationAssessment,
)

runner = CliRunner()


def _make_fundamental(symbol: str = "AAPL") -> FundamentalAnalysis:
    return FundamentalAnalysis(
        symbol=symbol,
        market_type=MarketType.US,
        current_price=200.0,
        valuation=ValuationAssessment(),
    )


def _make_risk() -> RiskMetrics:
    return RiskMetrics(num_days=30, total_return_pct=5.0)


class TestFullStockReportCacheKey:
    def test_different_date_ranges_produce_independent_cache_entries(
        self, db: Database
    ):
        """Cache hit for symbol+date_range must not bleed into a different date range."""
        fundamental = _make_fundamental()
        risk_2024 = RiskMetrics(num_days=252, total_return_pct=20.0)
        risk_2023 = RiskMetrics(num_days=252, total_return_pct=-5.0)

        with (
            patch("haoinvest.analysis.report.analyze_stock", return_value=fundamental),
            patch(
                "haoinvest.analysis.report.calculate_risk_metrics",
                side_effect=[risk_2024, risk_2023],
            ),
        ):
            report_2024 = full_stock_report(
                db,
                "AAPL",
                MarketType.US,
                price_start=date(2024, 1, 1),
                price_end=date(2024, 12, 31),
            )
            report_2023 = full_stock_report(
                db,
                "AAPL",
                MarketType.US,
                price_start=date(2023, 1, 1),
                price_end=date(2023, 12, 31),
            )

        assert report_2024.risk_metrics.total_return_pct == 20.0
        assert report_2023.risk_metrics.total_return_pct == -5.0

    def test_same_date_range_returns_cached_result(self, db: Database):
        """Second call with same symbol+date_range must hit cache (no second API call)."""
        fundamental = _make_fundamental()
        risk = _make_risk()

        with (
            patch(
                "haoinvest.analysis.report.analyze_stock", return_value=fundamental
            ) as mock_fundamental,
            patch(
                "haoinvest.analysis.report.calculate_risk_metrics", return_value=risk
            ) as mock_risk,
        ):
            full_stock_report(
                db,
                "AAPL",
                MarketType.US,
                price_start=date(2024, 1, 1),
                price_end=date(2024, 12, 31),
            )
            full_stock_report(
                db,
                "AAPL",
                MarketType.US,
                price_start=date(2024, 1, 1),
                price_end=date(2024, 12, 31),
            )

        assert mock_fundamental.call_count == 1
        assert mock_risk.call_count == 1

    def test_no_date_range_uses_stable_cache_key(self, db: Database):
        """Calls without date range should still cache and not conflict."""
        fundamental = _make_fundamental()
        risk = _make_risk()

        with (
            patch(
                "haoinvest.analysis.report.analyze_stock", return_value=fundamental
            ) as mock_fundamental,
            patch(
                "haoinvest.analysis.report.calculate_risk_metrics", return_value=risk
            ),
        ):
            full_stock_report(db, "AAPL", MarketType.US)
            full_stock_report(db, "AAPL", MarketType.US)

        assert mock_fundamental.call_count == 1


# --- Checklist scoring tests ---


class TestScoreValuation:
    def test_undervalued(self):
        assert _score_valuation("偏低") == 5

    def test_fair(self):
        assert _score_valuation("中等") == 4

    def test_overvalued(self):
        assert _score_valuation("偏高") == 2

    def test_unknown(self):
        assert _score_valuation("无法评估") == 3


class TestScoreProfitability:
    def test_excellent_roe(self):
        assert _score_profitability(20.0, None) == 5

    def test_fallback_margin(self):
        assert _score_profitability(None, 25.0) == 5

    def test_no_data(self):
        assert _score_profitability(None, None) == 3


class TestScoreGrowth:
    def test_high(self):
        assert _score_growth(25.0) == 5

    def test_negative(self):
        assert _score_growth(-10.0) == 2

    def test_none(self):
        assert _score_growth(None) == 3


class TestScoreRisk:
    def test_low_drawdown_high_sharpe(self):
        assert _score_risk(-8.0, 1.5) == 5

    def test_no_data(self):
        assert _score_risk(None, None) == 3


class TestScoreTechnical:
    def test_bullish(self):
        assert _score_technical("偏多", "高") == 5

    def test_bearish(self):
        assert _score_technical("偏空", "中") == 2


class TestComputeChecklist:
    def test_healthy_stock(self):
        report = StockReport(
            symbol="600519",
            market_type="a_share",
            current_price=1800.0,
            valuation=ValuationAssessment(overall="偏低"),
            risk_metrics=RiskMetrics(max_drawdown_pct=-8.0, sharpe_ratio=1.5),
            roe=20.0,
            revenue_growth=25.0,
            financial_health=FinancialHealthAssessment(
                profitability="优秀", growth="高速增长"
            ),
            signals=SignalSummary(
                symbol="600519",
                market_type="a_share",
                overall_signal="偏多",
                confidence="高",
            ),
        )
        checklist = _compute_checklist(report)
        assert checklist.total_score >= 20
        assert checklist.recommendation == "建议关注"

    def test_weak_stock(self):
        report = StockReport(
            symbol="999999",
            market_type="a_share",
            current_price=5.0,
            valuation=ValuationAssessment(overall="高"),
            risk_metrics=RiskMetrics(max_drawdown_pct=-45.0, sharpe_ratio=-0.5),
            roe=2.0,
            revenue_growth=-20.0,
            financial_health=FinancialHealthAssessment(
                profitability="偏弱", growth="负增长"
            ),
            signals=SignalSummary(
                symbol="999999",
                market_type="a_share",
                overall_signal="偏空",
                confidence="高",
            ),
        )
        checklist = _compute_checklist(report)
        assert checklist.recommendation == "建议回避"


class TestReportCLI:
    def test_report_command(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))
        mock_report = StockReport(
            symbol="600519",
            name="贵州茅台",
            sector="白酒",
            market_type="a_share",
            current_price=1800.0,
            valuation=ValuationAssessment(
                pe_assessment="偏高", pb_assessment="高估", overall="偏高"
            ),
            risk_metrics=RiskMetrics(
                annualized_volatility=25.0,
                max_drawdown_pct=-15.0,
                sharpe_ratio=0.85,
            ),
            roe=18.0,
            financial_health=FinancialHealthAssessment(
                profitability="优秀", overall="财务健康"
            ),
            checklist=BuyReadinessChecklist(
                items=[
                    ChecklistItem(dimension="估值", score=4, assessment="偏高"),
                    ChecklistItem(dimension="盈利能力", score=5, assessment="优秀"),
                ],
                total_score=9,
                max_score=10,
                recommendation="建议关注",
            ),
        )
        with (
            patch("haoinvest.cli.analyze.ensure_prices_cached"),
            patch(
                "haoinvest.analysis.report.full_stock_report",
                return_value=mock_report,
            ),
        ):
            result = runner.invoke(app, ["analyze", "report", "600519"])
            assert result.exit_code == 0
            assert "基本信息" in result.output
            assert "估值分析" in result.output
            assert "买入准备度" in result.output
