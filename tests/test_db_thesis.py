"""Tests for thesis CRUD in db.py."""

from datetime import date

from haoinvest.db import Database
from haoinvest.models import InvestmentThesis, ThesisStatus


class TestThesisCRUD:
    def test_add_and_get_thesis(self, db: Database) -> None:
        thesis = InvestmentThesis(
            symbol="600519",
            entry_date=date(2026, 1, 1),
            entry_price=1500.0,
            thesis_summary="消费升级长期受益",
            key_assumptions=["ROE > 20%", "毛利率稳定"],
        )
        thesis_id = db.add_thesis(thesis)
        assert thesis_id > 0

        result = db.get_thesis(thesis_id)
        assert result is not None
        assert result.symbol == "600519"
        assert result.entry_price == 1500.0
        assert result.thesis_summary == "消费升级长期受益"
        assert result.key_assumptions == ["ROE > 20%", "毛利率稳定"]
        assert result.status == ThesisStatus.ACTIVE

    def test_get_theses_filter_by_symbol(self, db: Database) -> None:
        db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="thesis A",
            )
        )
        db.add_thesis(
            InvestmentThesis(
                symbol="000858",
                entry_date=date(2026, 1, 1),
                entry_price=200.0,
                thesis_summary="thesis B",
            )
        )
        results = db.get_theses(symbol="600519")
        assert len(results) == 1
        assert results[0].symbol == "600519"

    def test_get_theses_filter_by_status(self, db: Database) -> None:
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="thesis A",
            )
        )
        db.update_thesis_status(tid, ThesisStatus.INVALIDATED, reason="ROE dropped")

        active = db.get_theses(status=ThesisStatus.ACTIVE)
        assert len(active) == 0

        invalidated = db.get_theses(status=ThesisStatus.INVALIDATED)
        assert len(invalidated) == 1
        assert invalidated[0].invalidation_reason == "ROE dropped"

    def test_update_thesis_status(self, db: Database) -> None:
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="test",
            )
        )
        db.update_thesis_status(tid, ThesisStatus.REALIZED, reason="达到目标价")

        result = db.get_thesis(tid)
        assert result is not None
        assert result.status == ThesisStatus.REALIZED
        assert result.invalidation_reason == "达到目标价"

    def test_mark_thesis_reviewed(self, db: Database) -> None:
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="test",
            )
        )
        result_before = db.get_thesis(tid)
        assert result_before is not None
        assert result_before.last_reviewed_at is None

        db.mark_thesis_reviewed(tid)

        result_after = db.get_thesis(tid)
        assert result_after is not None
        assert result_after.last_reviewed_at is not None

    def test_get_nonexistent_thesis(self, db: Database) -> None:
        assert db.get_thesis(9999) is None

    def test_key_assumptions_empty_list(self, db: Database) -> None:
        tid = db.add_thesis(
            InvestmentThesis(
                symbol="600519",
                entry_date=date(2026, 1, 1),
                entry_price=1500.0,
                thesis_summary="test",
                key_assumptions=[],
            )
        )
        result = db.get_thesis(tid)
        assert result is not None
        assert result.key_assumptions == []
