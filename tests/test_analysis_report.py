"""Tests for full_stock_report cache key correctness."""

from datetime import date
from unittest.mock import patch

from haoinvest.analysis.report import full_stock_report
from haoinvest.db import Database
from haoinvest.models import (
    FundamentalAnalysis,
    MarketType,
    RiskMetrics,
    ValuationAssessment,
)


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
