"""Tests for Pydantic models."""

from datetime import datetime
from haoinvest.models import (
    MarketType,
    Position,
    Transaction,
    TransactionAction,
    JournalEntry,
    DecisionType,
    Emotion,
)


def test_transaction_model():
    txn = Transaction(
        symbol="600519",
        market_type=MarketType.A_SHARE,
        action=TransactionAction.BUY,
        quantity=100,
        price=1680.0,
        fee=5.0,
        executed_at=datetime(2026, 3, 28, 10, 0),
    )
    assert txn.tax == 0.0
    assert txn.currency == "CNY"
    assert txn.exchange_rate == 1.0


def test_position_defaults():
    pos = Position(symbol="BTC_USDT", market_type=MarketType.CRYPTO)
    assert pos.cached_quantity == 0.0
    assert pos.cached_avg_cost == 0.0
    assert pos.currency == "CNY"


def test_journal_entry_with_all_fields():
    entry = JournalEntry(
        content="看好消费复苏趋势",
        decision_type=DecisionType.BUY,
        emotion=Emotion.RATIONAL,
        related_symbols=["600519", "000858"],
    )
    assert len(entry.related_symbols) == 2
    assert entry.retrospective is None


def test_market_type_enum_values():
    assert MarketType.A_SHARE.value == "a_share"
    assert MarketType.CRYPTO.value == "crypto"
    assert MarketType.HK.value == "hk"
    assert MarketType.US.value == "us"


def test_emotion_enum_has_all_values():
    emotions = {e.value for e in Emotion}
    assert emotions == {
        "rational",
        "greedy",
        "fearful",
        "fomo",
        "uncertain",
        "confident",
        "regretful",
    }
