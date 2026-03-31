"""Tests for haoinvest journal CLI commands."""

import pytest
from typer.testing import CliRunner

from haoinvest.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("HAOINVEST_DATA_DIR", str(tmp_path))


class TestJournalAdd:
    def test_add_entry(self):
        result = runner.invoke(
            app,
            [
                "journal",
                "add",
                "看好茅台长期",
                "--decision",
                "buy",
                "--emotion",
                "rational",
                "--symbols",
                "600519",
            ],
        )
        assert result.exit_code == 0
        assert "entry_id" in result.output

    def test_add_entry_minimal(self):
        result = runner.invoke(app, ["journal", "add", "市场观察"])
        assert result.exit_code == 0
        assert "entry_id" in result.output

    def test_add_entry_json(self):
        result = runner.invoke(
            app,
            [
                "journal",
                "add",
                "测试内容",
                "--json",
            ],
        )
        assert result.exit_code == 0
        assert '"entry_id"' in result.output


class TestJournalList:
    def test_list_empty(self):
        result = runner.invoke(app, ["journal", "list"])
        assert result.exit_code == 0
        assert "(no entries)" in result.output

    def test_list_after_add(self):
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "测试日记",
                "--decision",
                "hold",
                "--symbols",
                "600519",
            ],
        )
        result = runner.invoke(app, ["journal", "list"])
        assert result.exit_code == 0
        assert "测试日记" in result.output
        assert "600519" in result.output

    def test_list_filter_by_symbol(self):
        runner.invoke(app, ["journal", "add", "茅台相关", "--symbols", "600519"])
        runner.invoke(app, ["journal", "add", "银行相关", "--symbols", "000001"])
        result = runner.invoke(app, ["journal", "list", "--symbol", "600519"])
        assert result.exit_code == 0
        assert "茅台相关" in result.output


class TestJournalReview:
    def test_review_empty(self):
        result = runner.invoke(app, ["journal", "review"])
        assert result.exit_code == 0
        assert "TotalEntries: 0" in result.output

    def test_review_with_entries(self):
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "买入茅台",
                "--decision",
                "buy",
                "--emotion",
                "rational",
            ],
        )
        runner.invoke(
            app,
            [
                "journal",
                "add",
                "恐慌抛售",
                "--decision",
                "sell",
                "--emotion",
                "fearful",
            ],
        )
        result = runner.invoke(app, ["journal", "review"])
        assert result.exit_code == 0
        assert "TotalEntries: 2" in result.output

    def test_review_entry_not_found(self):
        result = runner.invoke(app, ["journal", "review", "--entry-id", "999"])
        assert result.exit_code == 1
