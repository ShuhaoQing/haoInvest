"""Pydantic models for all entities."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MarketType(str, Enum):
    A_SHARE = "a_share"
    CRYPTO = "crypto"
    HK = "hk"
    US = "us"


class TransactionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    SPLIT = "split"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class DecisionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"
    REFLECTION = "reflection"


class Emotion(str, Enum):
    RATIONAL = "rational"
    GREEDY = "greedy"
    FEARFUL = "fearful"
    FOMO = "fomo"
    UNCERTAIN = "uncertain"
    CONFIDENT = "confident"
    REGRETFUL = "regretful"


class Position(BaseModel):
    id: Optional[int] = None
    symbol: str
    market_type: MarketType
    currency: str = "CNY"
    cached_quantity: float = 0.0
    cached_avg_cost: float = 0.0
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Transaction(BaseModel):
    id: Optional[int] = None
    symbol: str
    market_type: MarketType
    action: TransactionAction
    quantity: float
    price: float
    fee: float = 0.0
    tax: float = 0.0
    currency: str = "CNY"
    exchange_rate: float = 1.0
    executed_at: datetime
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class JournalEntry(BaseModel):
    id: Optional[int] = None
    content: str
    decision_type: Optional[DecisionType] = None
    emotion: Optional[Emotion] = None
    related_symbols: list[str] = Field(default_factory=list)
    retrospective: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DailySnapshot(BaseModel):
    id: Optional[int] = None
    snapshot_date: date
    total_value_cny: float
    total_cost_cny: float
    cash_balance: float = 0.0
    positions_json: str = "{}"
    created_at: Optional[datetime] = None


class PriceBar(BaseModel):
    symbol: str
    market_type: MarketType
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
