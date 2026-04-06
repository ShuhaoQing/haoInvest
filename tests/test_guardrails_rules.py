"""Tests for guardrails rules engine."""

from datetime import datetime
from unittest.mock import patch

import pytest

from haoinvest.db import Database
from haoinvest.guardrails.rules import health_check, load_config, validate_trade
from haoinvest.models import MarketType, Position, Severity


def _add_position(db: Database, symbol: str, qty: float, avg_cost: float, mt: MarketType = MarketType.A_SHARE) -> None:
    """Helper to insert a position directly."""
    db.upsert_position(
        Position(symbol=symbol, market_type=mt, cached_quantity=qty, cached_avg_cost=avg_cost)
    )


class TestLoadConfig:
    def test_defaults(self, db: Database) -> None:
        config = load_config(db)
        assert config.max_single_position_pct == 15.0
        assert config.max_total_positions == 8
        assert config.loss_review_threshold == -10.0

    def test_custom_overrides(self, db: Database) -> None:
        db.set_guardrails_config("max_single_position_pct", "25.0")
        db.set_guardrails_config("max_total_positions", "12")
        config = load_config(db)
        assert config.max_single_position_pct == 25.0
        assert config.max_total_positions == 12
        # Others remain default
        assert config.max_sector_pct == 35.0


class TestHealthCheck:
    def test_empty_portfolio(self, db: Database) -> None:
        result = health_check(db, {})
        assert result.passed is True
        assert result.summary == "暂无持仓"

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_all_pass(self, _mock_sector, db: Database) -> None:
        # 5 equally-sized positions — each 20%, under the 50% limit
        db.set_guardrails_config("max_single_position_pct", "50")
        for i in range(5):
            _add_position(db, f"60000{i}", 100, 100)
        prices = {(f"60000{i}", MarketType.A_SHARE): 100.0 for i in range(5)}
        result = health_check(db, prices)
        assert result.passed is True

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_single_position_violation(self, _mock_sector, db: Database) -> None:
        _add_position(db, "600519", 100, 1800)
        _add_position(db, "000858", 50, 200)
        prices = {
            ("600519", MarketType.A_SHARE): 1800.0,
            ("000858", MarketType.A_SHARE): 200.0,
        }
        # 600519: 180000 / 190000 = 94.7% >> 15%
        result = health_check(db, prices)
        assert result.passed is False
        assert any(v.rule_name == "max_single_position_pct" for v in result.violations)

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol")
    def test_sector_concentration(self, mock_sector, db: Database) -> None:
        mock_sector.side_effect = lambda _db, sym, _mt: "白酒" if sym.startswith("6") else "银行"
        _add_position(db, "600519", 100, 1000)
        _add_position(db, "600809", 100, 500)
        _add_position(db, "000001", 100, 200)
        prices = {
            ("600519", MarketType.A_SHARE): 1000.0,
            ("600809", MarketType.A_SHARE): 500.0,
            ("000001", MarketType.A_SHARE): 200.0,
        }
        # Set high single position limit to avoid that violation
        db.set_guardrails_config("max_single_position_pct", "80")
        # 白酒: 150000 / 170000 = 88% >> 35%
        result = health_check(db, prices)
        assert any(v.rule_name == "max_sector_pct" for v in result.violations)

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_too_many_positions(self, _mock_sector, db: Database) -> None:
        db.set_guardrails_config("max_single_position_pct", "90")
        db.set_guardrails_config("max_total_positions", "3")
        for i in range(5):
            _add_position(db, f"60000{i}", 100, 10)
        prices = {(f"60000{i}", MarketType.A_SHARE): 10.0 for i in range(5)}
        result = health_check(db, prices)
        assert any(v.rule_name == "max_total_positions" for v in result.violations)

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_low_cash_reserve(self, _mock_sector, db: Database) -> None:
        db.set_guardrails_config("max_single_position_pct", "90")
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1000.0}
        # Cash: 5000, portfolio: 100000, cash_pct = 5000/105000 = 4.8% < 10%
        result = health_check(db, prices, cash_balance=5000.0)
        assert any(v.rule_name == "min_cash_reserve_pct" for v in result.violations)

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_cash_check_skipped_when_zero(self, _mock_sector, db: Database) -> None:
        db.set_guardrails_config("max_single_position_pct", "90")
        _add_position(db, "600519", 100, 1000)
        prices = {("600519", MarketType.A_SHARE): 1000.0}
        result = health_check(db, prices, cash_balance=0.0)
        assert not any(v.rule_name == "min_cash_reserve_pct" for v in result.violations)


class TestValidateTrade:
    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_warns_on_violation(self, _mock_sector, db: Database) -> None:
        _add_position(db, "600519", 100, 1800)
        prices = {("600519", MarketType.A_SHARE): 1800.0}
        # Buy 1000 more shares — way over 15% (already 100%)
        violations = validate_trade(
            db, "600519", MarketType.A_SHARE, "buy", 1000, 1800.0, prices
        )
        # This position was already over limit, so no NEW violation
        # But let's test with a second position
        _add_position(db, "000858", 1000, 180)
        prices[("000858", MarketType.A_SHARE)] = 180.0
        # Now: 600519=180000, 000858=180000, total=360000
        # After buying 500 more 600519: 600519=1080000, 000858=180000
        violations = validate_trade(
            db, "600519", MarketType.A_SHARE, "buy", 500, 1800.0, prices
        )
        assert any(v.rule_name == "max_single_position_pct" for v in violations)

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_clean_trade(self, _mock_sector, db: Database) -> None:
        db.set_guardrails_config("max_single_position_pct", "60")
        _add_position(db, "600519", 100, 100)
        _add_position(db, "000858", 100, 100)
        prices = {
            ("600519", MarketType.A_SHARE): 100.0,
            ("000858", MarketType.A_SHARE): 100.0,
        }
        # Buy 10 more: 600519 = 11000/21000 = 52.4% < 60%
        violations = validate_trade(
            db, "600519", MarketType.A_SHARE, "buy", 10, 100.0, prices
        )
        assert violations == []

    @patch("haoinvest.guardrails.rules._get_sector_for_symbol", return_value=None)
    def test_new_position_increases_count(self, _mock_sector, db: Database) -> None:
        db.set_guardrails_config("max_total_positions", "2")
        db.set_guardrails_config("max_single_position_pct", "90")
        _add_position(db, "600519", 100, 100)
        _add_position(db, "000858", 100, 100)
        prices = {
            ("600519", MarketType.A_SHARE): 100.0,
            ("000858", MarketType.A_SHARE): 100.0,
        }
        violations = validate_trade(
            db, "600036", MarketType.A_SHARE, "buy", 10, 50.0, prices
        )
        assert any(v.rule_name == "max_total_positions" for v in violations)
