"""Tests for fundamental analysis — financial health assessment."""

from haoinvest.analysis.fundamental import (
    _assess_cash_flow,
    _assess_financial_health,
    _assess_growth,
    _assess_leverage,
    _assess_profitability,
)
from haoinvest.models import BasicInfo


class TestAssessProfitability:
    def test_excellent_roe(self):
        assert "优秀" in _assess_profitability(20.0, None)

    def test_good_roe(self):
        assert "良好" in _assess_profitability(12.0, None)

    def test_average_roe(self):
        assert "一般" in _assess_profitability(7.0, None)

    def test_weak_roe(self):
        assert "偏弱" in _assess_profitability(3.0, None)

    def test_fallback_to_profit_margin(self):
        result = _assess_profitability(None, 25.0)
        assert "优秀" in result
        assert "净利率" in result

    def test_none_returns_na(self):
        assert _assess_profitability(None, None) == "N/A"


class TestAssessGrowth:
    def test_high_growth(self):
        assert "高速增长" in _assess_growth(25.0)  # All values now in percentage

    def test_stable_growth(self):
        assert "稳定增长" in _assess_growth(15.0)

    def test_low_growth(self):
        assert "低增长" in _assess_growth(5.0)

    def test_negative_growth(self):
        assert "负增长" in _assess_growth(-10.0)

    def test_none_returns_na(self):
        assert _assess_growth(None) == "N/A"


class TestAssessLeverage:
    def test_conservative(self):
        assert "保守" in _assess_leverage(30.0, None)

    def test_moderate(self):
        assert "适中" in _assess_leverage(80.0, None)

    def test_high_leverage(self):
        assert "偏高" in _assess_leverage(150.0, None)

    def test_very_high_leverage(self):
        assert "高杠杆" in _assess_leverage(250.0, None)

    def test_current_ratio_sufficient(self):
        result = _assess_leverage(None, 2.5)
        assert "充足" in result

    def test_current_ratio_normal(self):
        result = _assess_leverage(None, 1.5)
        assert "正常" in result

    def test_current_ratio_tight(self):
        result = _assess_leverage(None, 0.8)
        assert "紧张" in result

    def test_combined(self):
        result = _assess_leverage(60.0, 1.8)
        assert "适中" in result
        assert "正常" in result

    def test_none_returns_na(self):
        assert _assess_leverage(None, None) == "N/A"


class TestAssessCashFlow:
    def test_positive_fcf(self):
        assert "充裕" in _assess_cash_flow(1_000_000, None)

    def test_negative_fcf(self):
        assert "紧张" in _assess_cash_flow(-500_000, None)

    def test_fallback_to_operating(self):
        result = _assess_cash_flow(None, 2_000_000)
        assert "正常" in result

    def test_negative_operating(self):
        result = _assess_cash_flow(None, -100_000)
        assert "紧张" in result

    def test_none_returns_na(self):
        assert _assess_cash_flow(None, None) == "N/A"


class TestAssessFinancialHealth:
    def test_healthy_stock(self):
        info = BasicInfo(
            roe=18.0,
            profit_margin=15.0,
            revenue_growth=20.0,
            debt_to_equity=40.0,
            current_ratio=2.0,
            free_cash_flow=1_000_000,
        )
        result = _assess_financial_health(info)
        assert result.overall == "财务健康"
        assert "优秀" in result.profitability

    def test_weak_stock(self):
        info = BasicInfo(
            roe=2.0,
            revenue_growth=-15.0,
            debt_to_equity=250.0,
            free_cash_flow=-500_000,
        )
        result = _assess_financial_health(info)
        assert result.overall == "财务风险较高"

    def test_all_none_returns_unknown(self):
        info = BasicInfo()
        result = _assess_financial_health(info)
        assert result.overall == "无法评估"

    def test_partial_data(self):
        info = BasicInfo(roe=12.0, revenue_growth=8.0)
        result = _assess_financial_health(info)
        assert result.profitability != "N/A"
        assert result.growth != "N/A"
        assert result.leverage == "N/A"
        assert result.cash_flow == "N/A"
