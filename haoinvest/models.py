"""Pydantic models for all entities."""

from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MarketType(str, Enum):
    """Supported market types for position tracking and data providers."""

    A_SHARE = "a_share"
    CRYPTO = "crypto"
    HK = "hk"
    US = "us"


class TransactionAction(str, Enum):
    """Trade action types. BUY/SELL are market trades; DIVIDEND/SPLIT are corporate events."""

    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    SPLIT = "split"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class DecisionType(str, Enum):
    """Investment decision categories for journal entries."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"
    REFLECTION = "reflection"


class Emotion(str, Enum):
    """Self-reported emotional state when making investment decisions."""

    RATIONAL = "rational"
    GREEDY = "greedy"
    FEARFUL = "fearful"
    FOMO = "fomo"
    UNCERTAIN = "uncertain"
    CONFIDENT = "confident"
    REGRETFUL = "regretful"


class Position(BaseModel):
    """A tracked investment position. Cached fields are derived from transactions."""

    id: Optional[int] = None
    symbol: str
    market_type: MarketType
    currency: str = "CNY"
    cached_quantity: float = Field(
        default=0.0, description="Derived from transactions; not the source of truth"
    )
    cached_avg_cost: float = Field(
        default=0.0,
        description="Weighted average cost per share, recalculated from transactions",
    )
    last_synced_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last position recalculation from transactions",
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Transaction(BaseModel):
    """A single trade or corporate event. Source of truth for position accounting."""

    id: Optional[int] = None
    symbol: str
    market_type: MarketType
    action: TransactionAction
    quantity: float
    price: float
    fee: float = Field(default=0.0, description="Broker commission fee")
    tax: float = Field(
        default=0.0, description="Stamp duty or other tax (e.g., A-share sell tax)"
    )
    currency: str = "CNY"
    exchange_rate: float = Field(
        default=1.0,
        description="Conversion rate to base currency (CNY); 1.0 for A-shares",
    )
    executed_at: datetime
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class JournalEntry(BaseModel):
    """An investment journal entry for decision tracking and emotional awareness."""

    id: Optional[int] = None
    content: str
    decision_type: Optional[DecisionType] = None
    emotion: Optional[Emotion] = None
    related_symbols: list[str] = Field(default_factory=list)
    retrospective: Optional[str] = Field(
        default=None,
        description="Post-hoc reflection added after the outcome is known",
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DailySnapshot(BaseModel):
    """A daily point-in-time record of portfolio value for performance tracking."""

    id: Optional[int] = None
    snapshot_date: date
    total_value_cny: float = Field(
        description="Total portfolio market value in CNY at snapshot date"
    )
    total_cost_cny: float
    cash_balance: float = 0.0
    positions_json: str = Field(
        default="{}",
        description="JSON-serialized dict of {symbol: {quantity, value}} at snapshot time",
    )
    created_at: Optional[datetime] = None


class PriceBar(BaseModel):
    """OHLCV price data for a single trading day, cached from market providers."""

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
    """Asset metadata from market data providers (name, sector, valuation ratios)."""

    name: str = ""
    sector: str = ""
    currency: str = "CNY"
    market_type: str = ""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[int] = None
    total_market_cap: Optional[int] = None
    total_supply: Optional[float] = Field(
        default=None, description="Total token supply (crypto only)"
    )


# --- Analysis models ---


class ValuationAssessment(BaseModel):
    """PE/PB-based valuation assessment with Chinese labels."""

    pe_assessment: str = "N/A"
    pb_assessment: str = "N/A"
    overall: str = "无法评估"


class FundamentalAnalysis(BaseModel):
    """Fundamental analysis result for a single stock (PE/PB, valuation)."""

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
    """Risk metrics computed from price history (volatility, drawdown, Sharpe)."""

    annualized_volatility: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    total_return_pct: Optional[float] = None
    num_days: int = Field(
        default=0, description="Number of trading days in the analysis window"
    )
    message: Optional[str] = Field(
        default=None,
        description="Warning message when data is insufficient for calculation",
    )


class StockReport(BaseModel):
    """Combined fundamental analysis and risk metrics for a single stock."""

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
    """Mark-to-market unrealized profit/loss for a single position."""

    quantity: float = 0
    avg_cost: float = 0
    current_price: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    total_fees: float = 0


class RealizedPnL(BaseModel):
    """Realized profit/loss from completed sell transactions."""

    total_realized_pnl: float = 0
    total_dividends: float = 0
    num_sell_trades: int = 0


class HoldingSummary(BaseModel):
    """Per-holding breakdown within a portfolio summary."""

    symbol: str
    market_type: str
    quantity: float
    avg_cost: float
    current_price: float = 0
    market_value: float = 0
    cost_basis: float = 0
    position_cost: float = Field(
        default=0, description="quantity * avg_cost; total cost basis for this holding"
    )
    allocation_pct: float = Field(
        default=0, description="Percentage of total portfolio market value"
    )
    currency: str = "CNY"
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0


class PortfolioSummary(BaseModel):
    """Aggregated portfolio view with per-holding breakdowns and total PnL."""

    total_market_value: float = 0
    total_cost_basis: float = 0
    total_unrealized_pnl: float = 0
    total_unrealized_pnl_pct: float = 0
    holdings: list[HoldingSummary] = Field(default_factory=list)


# --- Strategy models ---


class AllocationSuggestion(BaseModel):
    """Suggested portfolio allocation from the optimizer."""

    method: str = Field(
        description="Strategy name, e.g., 'equal_weight' or 'risk_parity'"
    )
    weights: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class RebalanceTrade(BaseModel):
    """A single rebalance trade needed to reach target allocation."""

    symbol: str
    action: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    current_weight: float = 0
    target_weight: float = 0
    trade_value: float = Field(
        default=0, description="Signed value of the trade in local currency"
    )
    note: Optional[str] = None
