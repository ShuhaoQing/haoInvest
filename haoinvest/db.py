"""SQLite database management and repository CRUD."""

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from .config import get_db_path
from .models import (
    DailySnapshot,
    JournalEntry,
    MarketType,
    Position,
    PriceBar,
    Transaction,
    TransactionAction,
)


def _parse_datetime(val: str | None) -> datetime | None:
    if val is None:
        return None
    return datetime.fromisoformat(str(val))


def _parse_date(val: str | None) -> date | None:
    if val is None:
        return None
    return date.fromisoformat(str(val))


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    market_type TEXT NOT NULL CHECK(market_type IN ('a_share', 'crypto', 'hk', 'us')),
    currency TEXT NOT NULL DEFAULT 'CNY',
    cached_quantity REAL NOT NULL DEFAULT 0,
    cached_avg_cost REAL NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, market_type)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    market_type TEXT NOT NULL CHECK(market_type IN ('a_share', 'crypto', 'hk', 'us')),
    action TEXT NOT NULL CHECK(action IN ('buy', 'sell', 'dividend', 'split', 'transfer_in', 'transfer_out')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL DEFAULT 0,
    tax REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'CNY',
    exchange_rate REAL DEFAULT 1.0,
    executed_at TIMESTAMP NOT NULL,
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_symbol ON transactions(symbol, market_type);
CREATE INDEX IF NOT EXISTS idx_transactions_executed_at ON transactions(executed_at);

CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    decision_type TEXT CHECK(decision_type IN ('buy', 'sell', 'hold', 'watch', 'reflection')),
    emotion TEXT CHECK(emotion IN ('rational', 'greedy', 'fearful', 'fomo', 'uncertain', 'confident', 'regretful')),
    retrospective TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS journal_symbol_tags (
    journal_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    PRIMARY KEY (journal_id, symbol)
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_date DATE NOT NULL UNIQUE,
    total_value_cny REAL NOT NULL,
    total_cost_cny REAL NOT NULL,
    cash_balance REAL NOT NULL DEFAULT 0,
    positions_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS price_history (
    symbol TEXT NOT NULL,
    market_type TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, market_type, trade_date)
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
"""


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Transactions ---

    def add_transaction(self, txn: Transaction) -> int:
        cursor = self.conn.execute(
            """INSERT INTO transactions
               (symbol, market_type, action, quantity, price, fee, tax,
                currency, exchange_rate, executed_at, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                txn.symbol,
                txn.market_type.value,
                txn.action.value,
                txn.quantity,
                txn.price,
                txn.fee,
                txn.tax,
                txn.currency,
                txn.exchange_rate,
                txn.executed_at.isoformat(),
                txn.note,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def get_transactions(
        self,
        symbol: Optional[str] = None,
        market_type: Optional[MarketType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Transaction]:
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if market_type:
            query += " AND market_type = ?"
            params.append(market_type.value)
        if start_date:
            query += " AND executed_at >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND executed_at <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY executed_at ASC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_transaction(r) for r in rows]

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            symbol=row["symbol"],
            market_type=MarketType(row["market_type"]),
            action=TransactionAction(row["action"]),
            quantity=row["quantity"],
            price=row["price"],
            fee=row["fee"],
            tax=row["tax"],
            currency=row["currency"],
            exchange_rate=row["exchange_rate"],
            executed_at=datetime.fromisoformat(str(row["executed_at"])),
            note=row["note"],
            created_at=_parse_datetime(row["created_at"]),
        )

    # --- Positions ---

    def upsert_position(self, pos: Position) -> None:
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO portfolio_positions
               (symbol, market_type, currency, cached_quantity, cached_avg_cost,
                last_synced_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol, market_type) DO UPDATE SET
                 cached_quantity = excluded.cached_quantity,
                 cached_avg_cost = excluded.cached_avg_cost,
                 last_synced_at = excluded.last_synced_at,
                 updated_at = ?""",
            (
                pos.symbol,
                pos.market_type.value,
                pos.currency,
                pos.cached_quantity,
                pos.cached_avg_cost,
                now,
                now,
                now,
                now,
            ),
        )
        self.conn.commit()

    def get_positions(self, include_zero: bool = False) -> list[Position]:
        query = "SELECT * FROM portfolio_positions"
        if not include_zero:
            query += " WHERE ABS(cached_quantity) > 1e-10"
        rows = self.conn.execute(query).fetchall()
        return [self._row_to_position(r) for r in rows]

    def get_position(self, symbol: str, market_type: MarketType) -> Optional[Position]:
        row = self.conn.execute(
            "SELECT * FROM portfolio_positions WHERE symbol = ? AND market_type = ?",
            (symbol, market_type.value),
        ).fetchone()
        return self._row_to_position(row) if row else None

    def _row_to_position(self, row: sqlite3.Row) -> Position:
        return Position(
            id=row["id"],
            symbol=row["symbol"],
            market_type=MarketType(row["market_type"]),
            currency=row["currency"],
            cached_quantity=row["cached_quantity"],
            cached_avg_cost=row["cached_avg_cost"],
            last_synced_at=_parse_datetime(row["last_synced_at"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    # --- Journal ---

    def add_journal_entry(self, entry: JournalEntry) -> int:
        cursor = self.conn.execute(
            """INSERT INTO journal_entries (content, decision_type, emotion, retrospective)
               VALUES (?, ?, ?, ?)""",
            (
                entry.content,
                entry.decision_type.value if entry.decision_type else None,
                entry.emotion.value if entry.emotion else None,
                entry.retrospective,
            ),
        )
        entry_id = cursor.lastrowid
        for symbol in entry.related_symbols:
            self.conn.execute(
                "INSERT INTO journal_symbol_tags (journal_id, symbol) VALUES (?, ?)",
                (entry_id, symbol),
            )
        self.conn.commit()
        return entry_id  # type: ignore[return-value]

    def get_journal_entries(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> list[JournalEntry]:
        if symbol:
            query = """
                SELECT je.* FROM journal_entries je
                JOIN journal_symbol_tags jst ON je.id = jst.journal_id
                WHERE jst.symbol = ?
                ORDER BY je.created_at DESC LIMIT ?
            """
            rows = self.conn.execute(query, (symbol, limit)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM journal_entries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        entries = []
        for row in rows:
            symbols = [
                r["symbol"]
                for r in self.conn.execute(
                    "SELECT symbol FROM journal_symbol_tags WHERE journal_id = ?",
                    (row["id"],),
                ).fetchall()
            ]
            entries.append(
                JournalEntry(
                    id=row["id"],
                    content=row["content"],
                    decision_type=row["decision_type"],
                    emotion=row["emotion"],
                    related_symbols=symbols,
                    retrospective=row["retrospective"],
                    created_at=_parse_datetime(row["created_at"]),
                    updated_at=_parse_datetime(row["updated_at"]),
                )
            )
        return entries

    def update_journal_retrospective(self, entry_id: int, retrospective: str) -> None:
        self.conn.execute(
            "UPDATE journal_entries SET retrospective = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (retrospective, entry_id),
        )
        self.conn.commit()

    # --- Daily Snapshots ---

    def save_snapshot(self, snapshot: DailySnapshot) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO daily_snapshots
               (snapshot_date, total_value_cny, total_cost_cny, cash_balance, positions_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                snapshot.snapshot_date.isoformat(),
                snapshot.total_value_cny,
                snapshot.total_cost_cny,
                snapshot.cash_balance,
                snapshot.positions_json,
            ),
        )
        self.conn.commit()

    def get_snapshots(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> list[DailySnapshot]:
        query = "SELECT * FROM daily_snapshots WHERE 1=1"
        params: list = []
        if start_date:
            query += " AND snapshot_date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND snapshot_date <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY snapshot_date ASC"

        rows = self.conn.execute(query, params).fetchall()
        return [
            DailySnapshot(
                id=row["id"],
                snapshot_date=date.fromisoformat(str(row["snapshot_date"])),
                total_value_cny=row["total_value_cny"],
                total_cost_cny=row["total_cost_cny"],
                cash_balance=row["cash_balance"],
                positions_json=row["positions_json"],
                created_at=_parse_datetime(row["created_at"]),
            )
            for row in rows
        ]

    # --- Price History ---

    def save_prices(self, bars: list[PriceBar]) -> None:
        self.conn.executemany(
            """INSERT OR REPLACE INTO price_history
               (symbol, market_type, trade_date, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    b.symbol,
                    b.market_type.value,
                    b.trade_date.isoformat(),
                    b.open,
                    b.high,
                    b.low,
                    b.close,
                    b.volume,
                )
                for b in bars
            ],
        )
        self.conn.commit()

    def get_prices(
        self,
        symbol: str,
        market_type: MarketType,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[PriceBar]:
        query = "SELECT * FROM price_history WHERE symbol = ? AND market_type = ?"
        params: list = [symbol, market_type.value]
        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date.isoformat())
        query += " ORDER BY trade_date ASC"

        rows = self.conn.execute(query, params).fetchall()
        return [
            PriceBar(
                symbol=row["symbol"],
                market_type=MarketType(row["market_type"]),
                trade_date=date.fromisoformat(str(row["trade_date"])),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

    # --- Analysis Cache ---

    def get_cached_analysis(self, symbol: str, analysis_type: str) -> Optional[dict]:
        row = self.conn.execute(
            """SELECT result_json FROM analysis_cache
               WHERE symbol = ? AND analysis_type = ?
               AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
               ORDER BY created_at DESC LIMIT 1""",
            (symbol, analysis_type),
        ).fetchone()
        return json.loads(row["result_json"]) if row else None

    def save_analysis(
        self, symbol: str, analysis_type: str, result: dict, ttl_seconds: int = 14400
    ) -> None:
        self.conn.execute(
            """INSERT INTO analysis_cache (symbol, analysis_type, result_json, expires_at)
               VALUES (?, ?, ?, datetime('now', '+' || ? || ' seconds'))""",
            (
                symbol,
                analysis_type,
                json.dumps(result, ensure_ascii=False, default=str),
                ttl_seconds,
            ),
        )
        self.conn.commit()
