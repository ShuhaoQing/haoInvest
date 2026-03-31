"""Pydantic models for all entities."""

from datetime import datetime, date
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


# --- Market data models ---


class BasicInfo(BaseModel):
    name: str = ""
    sector: str = ""
    currency: str = "CNY"
    market_type: str = ""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[int] = None
    total_market_cap: Optional[int] = None
    total_supply: Optional[float] = None


# --- Analysis models ---


class ValuationAssessment(BaseModel):
    pe_assessment: str = "N/A"
    pb_assessment: str = "N/A"
    overall: str = "无法评估"


class FundamentalAnalysis(BaseModel):
    symbol: str
    name: str = ""
    sector: str = ""
    market_type: str
    current_price: float
    currency: str = "CNY"
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    total_market_cap: Optional[int] = None
    valuation: ValuationAssessment = Field(default_factory=ValuationAssessment)


class RiskMetrics(BaseModel):
    annualized_volatility: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    total_return_pct: Optional[float] = None
    num_days: int = 0
    message: Optional[str] = None


class StockReport(BaseModel):
    symbol: str
    name: str = ""
    sector: str = ""
    market_type: str
    current_price: float
    currency: str = "CNY"
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    total_market_cap: Optional[int] = None
    valuation: ValuationAssessment = Field(default_factory=ValuationAssessment)
    risk_metrics: RiskMetrics = Field(default_factory=RiskMetrics)


# --- Portfolio models ---


class UnrealizedPnL(BaseModel):
    quantity: float = 0
    avg_cost: float = 0
    current_price: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    total_fees: float = 0


class RealizedPnL(BaseModel):
    total_realized_pnl: float = 0
    total_dividends: float = 0
    num_sell_trades: int = 0


class HoldingSummary(BaseModel):
    symbol: str
    market_type: str
    quantity: float
    avg_cost: float
    current_price: float = 0
    market_value: float = 0
    cost_basis: float = 0
    position_cost: float = 0
    allocation_pct: float = 0
    currency: str = "CNY"
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0


class PortfolioSummary(BaseModel):
    total_market_value: float = 0
    total_cost_basis: float = 0
    total_unrealized_pnl: float = 0
    total_unrealized_pnl_pct: float = 0
    holdings: list[HoldingSummary] = Field(default_factory=list)


# --- Strategy models ---


class AllocationSuggestion(BaseModel):
    method: str
    weights: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class RebalanceTrade(BaseModel):
    symbol: str
    action: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    current_weight: float = 0
    target_weight: float = 0
    trade_value: float = 0
    note: Optional[str] = None
