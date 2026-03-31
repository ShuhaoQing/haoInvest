"""Tests for database schema and CRUD operations."""

from datetime import datetime, date

from haoinvest.db import Database
from haoinvest.models import (
    DailySnapshot,
    DecisionType,
    Emotion,
    JournalEntry,
    MarketType,
    Position,
    PriceBar,
    Transaction,
    TransactionAction,
)


class TestSchema:
    def test_schema_creates_all_tables(self, db: Database):
        tables = [
            r[0]
            for r in db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        assert "portfolio_positions" in tables
        assert "transactions" in tables
        assert "journal_entries" in tables
        assert "journal_symbol_tags" in tables
        assert "daily_snapshots" in tables
        assert "price_history" in tables
        assert "analysis_cache" in tables

    def test_unique_constraint_on_positions(self, db: Database):
        pos = Position(
            symbol="600519", market_type=MarketType.A_SHARE, cached_quantity=100
        )
        db.upsert_position(pos)
        # Second upsert should update, not duplicate
        pos.cached_quantity = 200
        db.upsert_position(pos)
        positions = db.get_positions(include_zero=True)
        assert len(positions) == 1
        assert positions[0].cached_quantity == 200

    def test_foreign_key_cascade(self, db: Database):
        entry = JournalEntry(content="test", related_symbols=["600519"])
        entry_id = db.add_journal_entry(entry)
        # Delete journal entry
        db.conn.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))
        db.conn.commit()
        # Symbol tags should be cascade deleted
        tags = db.conn.execute(
            "SELECT * FROM journal_symbol_tags WHERE journal_id = ?", (entry_id,)
        ).fetchall()
        assert len(tags) == 0


class TestTransactions:
    def test_add_and_get_transaction(self, db: Database):
        txn = Transaction(
            symbol="600519",
            market_type=MarketType.A_SHARE,
            action=TransactionAction.BUY,
            quantity=100,
            price=1680.0,
            fee=5.0,
            tax=0,
            executed_at=datetime(2026, 3, 28, 10, 0),
            note="买入茅台",
        )
        txn_id = db.add_transaction(txn)
        assert txn_id > 0

        txns = db.get_transactions(symbol="600519")
        assert len(txns) == 1
        assert txns[0].symbol == "600519"
        assert txns[0].quantity == 100
        assert txns[0].price == 1680.0
        assert txns[0].note == "买入茅台"

    def test_filter_by_market_type(self, db: Database):
        for sym, mt in [
            ("600519", MarketType.A_SHARE),
            ("BTC_USDT", MarketType.CRYPTO),
        ]:
            db.add_transaction(
                Transaction(
                    symbol=sym,
                    market_type=mt,
                    action=TransactionAction.BUY,
                    quantity=1,
                    price=100,
                    executed_at=datetime(2026, 3, 28),
                )
            )
        a_shares = db.get_transactions(market_type=MarketType.A_SHARE)
        assert len(a_shares) == 1
        assert a_shares[0].symbol == "600519"

    def test_filter_by_date_range(self, db: Database):
        for day in [1, 15, 28]:
            db.add_transaction(
                Transaction(
                    symbol="600519",
                    market_type=MarketType.A_SHARE,
                    action=TransactionAction.BUY,
                    quantity=100,
                    price=100,
                    executed_at=datetime(2026, 3, day),
                )
            )
        txns = db.get_transactions(
            start_date=datetime(2026, 3, 10),
            end_date=datetime(2026, 3, 20),
        )
        assert len(txns) == 1


class TestPositions:
    def test_upsert_and_get(self, db: Database):
        pos = Position(
            symbol="600519",
            market_type=MarketType.A_SHARE,
            cached_quantity=100,
            cached_avg_cost=1680.0,
        )
        db.upsert_position(pos)
        result = db.get_position("600519", MarketType.A_SHARE)
        assert result is not None
        assert result.cached_quantity == 100
        assert result.cached_avg_cost == 1680.0

    def test_exclude_zero_positions(self, db: Database):
        db.upsert_position(
            Position(
                symbol="600519", market_type=MarketType.A_SHARE, cached_quantity=100
            )
        )
        db.upsert_position(
            Position(symbol="000001", market_type=MarketType.A_SHARE, cached_quantity=0)
        )
        positions = db.get_positions(include_zero=False)
        assert len(positions) == 1
        assert positions[0].symbol == "600519"


class TestJournal:
    def test_add_entry_with_symbols(self, db: Database):
        entry = JournalEntry(
            content="看好消费复苏",
            decision_type=DecisionType.BUY,
            emotion=Emotion.RATIONAL,
            related_symbols=["600519", "000858"],
        )
        db.add_journal_entry(entry)
        entries = db.get_journal_entries()
        assert len(entries) == 1
        assert set(entries[0].related_symbols) == {"600519", "000858"}

    def test_query_by_symbol(self, db: Database):
        db.add_journal_entry(JournalEntry(content="entry1", related_symbols=["600519"]))
        db.add_journal_entry(JournalEntry(content="entry2", related_symbols=["000858"]))
        entries = db.get_journal_entries(symbol="600519")
        assert len(entries) == 1
        assert entries[0].content == "entry1"

    def test_update_retrospective(self, db: Database):
        entry_id = db.add_journal_entry(JournalEntry(content="test"))
        db.update_journal_retrospective(entry_id, "回头看这个决策是对的")
        entries = db.get_journal_entries()
        assert entries[0].retrospective == "回头看这个决策是对的"


class TestSnapshots:
    def test_save_and_get(self, db: Database):
        snapshot = DailySnapshot(
            snapshot_date=date(2026, 3, 28),
            total_value_cny=100000.0,
            total_cost_cny=90000.0,
        )
        db.save_snapshot(snapshot)
        snapshots = db.get_snapshots()
        assert len(snapshots) == 1
        assert snapshots[0].total_value_cny == 100000.0


class TestPriceHistory:
    def test_save_and_get(self, db: Database):
        bars = [
            PriceBar(
                symbol="600519",
                market_type=MarketType.A_SHARE,
                trade_date=date(2026, 3, d),
                close=1680.0 + d,
            )
            for d in range(25, 29)
        ]
        db.save_prices(bars)
        result = db.get_prices("600519", MarketType.A_SHARE)
        assert len(result) == 4
        assert result[0].close == 1705.0


class TestAnalysisCache:
    def test_save_and_get(self, db: Database):
        db.save_analysis("600519", "fundamental", {"pe": 30, "pb": 10})
        result = db.get_cached_analysis("600519", "fundamental")
        assert result is not None
        assert result["pe"] == 30

    def test_expired_cache_returns_none(self, db: Database):
        db.save_analysis("600519", "fundamental", {"pe": 30}, ttl_seconds=0)
        # The cache expires immediately (ttl=0), but there might be a slight delay.
        # Force expiry by backdating.
        db.conn.execute(
            "UPDATE analysis_cache SET expires_at = datetime('now', '-1 hour')"
        )
        db.conn.commit()
        result = db.get_cached_analysis("600519", "fundamental")
        assert result is None
