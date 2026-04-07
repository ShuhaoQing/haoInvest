"""Tests for haoinvest.analysis.registry — module registry logic."""

import pytest

from haoinvest.analysis.registry import (
    MODULES,
    any_needs_prices,
    max_lookback_days,
    parse_modules,
)


class TestParseModules:
    def test_all_expands_to_all_modules(self):
        result = parse_modules("all")
        assert result == list(MODULES.keys())

    def test_all_case_insensitive(self):
        assert parse_modules("ALL") == list(MODULES.keys())
        assert parse_modules("  All  ") == list(MODULES.keys())

    def test_single_module(self):
        assert parse_modules("fundamental") == ["fundamental"]

    def test_multiple_modules(self):
        assert parse_modules("fundamental,risk,peer") == [
            "fundamental",
            "risk",
            "peer",
        ]

    def test_strips_whitespace(self):
        assert parse_modules(" fundamental , risk ") == ["fundamental", "risk"]

    def test_unknown_module_raises(self):
        with pytest.raises(ValueError, match="Unknown module"):
            parse_modules("fundamental,nonexistent")

    def test_empty_after_strip_ignored(self):
        assert parse_modules("fundamental,,risk") == ["fundamental", "risk"]


class TestMaxLookbackDays:
    def test_technical_dominates(self):
        assert max_lookback_days(["fundamental", "technical", "risk"]) == 1095

    def test_risk_only(self):
        assert max_lookback_days(["risk"]) == 365

    def test_fundamental_only(self):
        assert max_lookback_days(["fundamental"]) == 0


class TestAnyNeedsPrices:
    def test_fundamental_no_prices(self):
        assert any_needs_prices(["fundamental"]) is False

    def test_risk_needs_prices(self):
        assert any_needs_prices(["risk"]) is True

    def test_mixed(self):
        assert any_needs_prices(["fundamental", "peer"]) is False
        assert any_needs_prices(["fundamental", "risk"]) is True


class TestModuleRegistry:
    def test_all_modules_have_required_fields(self):
        for name, mod in MODULES.items():
            assert mod.name == name
            assert callable(mod.runner)
            assert callable(mod.formatter)
            assert isinstance(mod.needs_prices, bool)
            assert isinstance(mod.default_lookback_days, int)

    def test_module_count(self):
        assert len(MODULES) == 7

    def test_module_names(self):
        expected = {
            "fundamental",
            "technical",
            "risk",
            "volume",
            "signals",
            "peer",
            "checklist",
        }
        assert set(MODULES.keys()) == expected
