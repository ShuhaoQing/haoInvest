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
    industry: str = ""
    currency: str = "CNY"
    market_type: str = ""
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[int] = None
    total_market_cap: Optional[int] = None
    total_supply: Optional[float] = Field(
        default=None, description="Total token supply (crypto only)"
    )
    # Financial health metrics
    roe: Optional[float] = Field(default=None, description="Return on Equity (%)")
    roa: Optional[float] = Field(default=None, description="Return on Assets (%)")
    debt_to_equity: Optional[float] = Field(
        default=None, description="Debt-to-Equity ratio"
    )
    revenue_growth: Optional[float] = Field(
        default=None, description="YoY revenue growth (%)"
    )
    profit_margin: Optional[float] = Field(
        default=None, description="Net profit margin (%)"
    )
    gross_margin: Optional[float] = Field(
        default=None, description="Gross profit margin (%)"
    )
    operating_margin: Optional[float] = Field(
        default=None, description="Operating margin (%)"
    )
    current_ratio: Optional[float] = Field(
        default=None, description="Current ratio (liquidity)"
    )
    free_cash_flow: Optional[float] = Field(
        default=None, description="Free cash flow in local currency"
    )
    operating_cash_flow: Optional[float] = Field(
        default=None, description="Operating cash flow in local currency"
    )
    peg_ratio: Optional[float] = Field(
        default=None, description="Price/Earnings to Growth ratio"
    )


# --- Analysis models ---


class ValuationAssessment(BaseModel):
    """PE/PB-based valuation assessment with Chinese labels."""

    pe_assessment: str = "N/A"
    pb_assessment: str = "N/A"
    overall: str = "无法评估"


class FinancialHealthAssessment(BaseModel):
    """Multi-dimensional financial health assessment with Chinese labels."""

    profitability: str = "N/A"
    growth: str = "N/A"
    leverage: str = "N/A"
    cash_flow: str = "N/A"
    overall: str = "无法评估"


class FundamentalAnalysis(BaseModel):
    """Fundamental analysis result for a single stock."""

    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_type: str
    current_price: float
    currency: str = "CNY"
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    total_market_cap: Optional[int] = None
    valuation: ValuationAssessment = Field(default_factory=ValuationAssessment)
    # Enhanced financial metrics
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    peg_ratio: Optional[float] = None
    financial_health: FinancialHealthAssessment = Field(
        default_factory=FinancialHealthAssessment
    )


class RiskMetrics(BaseModel):
    """Risk metrics computed from price history (volatility, drawdown, Sharpe)."""

    annualized_volatility: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    total_return_pct: Optional[float] = None
    num_days: int = Field(
        default=0, description="Number of trading days in the analysis window"
    )
    message: Optional[str] = Field(
        default=None,
        description="Warning message when data is insufficient for calculation",
    )


class ChecklistItem(BaseModel):
    """A single buy-readiness checklist item."""

    dimension: str
    score: int = Field(description="1-5 scale")
    assessment: str


class BuyReadinessChecklist(BaseModel):
    """Aggregated buy-readiness scoring across multiple dimensions."""

    items: list[ChecklistItem] = Field(default_factory=list)
    total_score: int = 0
    max_score: int = 0
    recommendation: str = "无法评估"


class StockReport(BaseModel):
    """Combined fundamental analysis and risk metrics for a single stock."""

    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_type: str
    current_price: float
    currency: str = "CNY"
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    total_market_cap: Optional[int] = None
    valuation: ValuationAssessment = Field(default_factory=ValuationAssessment)
    risk_metrics: RiskMetrics = Field(default_factory=RiskMetrics)
    technical: Optional["TechnicalIndicators"] = None
    volume: Optional["VolumeAnalysis"] = None
    signals: Optional["SignalSummary"] = None
    # Enhanced fields (Phase 1+5)
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_to_equity: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    peg_ratio: Optional[float] = None
    financial_health: Optional[FinancialHealthAssessment] = None
    checklist: Optional[BuyReadinessChecklist] = None


# --- Technical analysis models ---


class MovingAverages(BaseModel):
    """Moving average values at the most recent data point."""

    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_60: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    trend: str = Field(
        default="无法判断", description="Trend assessment: 上升趋势/下降趋势/震荡"
    )
    explanation: Optional[str] = Field(
        default=None, description="Chinese explanation of trend logic (verbose mode)"
    )


class MACDResult(BaseModel):
    """MACD indicator values at the most recent data point."""

    macd_line: Optional[float] = None
    signal_line: Optional[float] = None
    histogram: Optional[float] = Field(
        default=None, description="MACD - signal; positive = bullish momentum"
    )
    signal: str = Field(default="无信号", description="金叉/死叉/无信号")
    explanation: Optional[str] = None


class RSIResult(BaseModel):
    """Relative Strength Index over the configured period."""

    rsi: Optional[float] = None
    period: int = 14
    assessment: str = Field(default="无法判断", description="超买/超卖/中性")
    explanation: Optional[str] = None


class BollingerBands(BaseModel):
    """Bollinger Bands at the most recent data point."""

    upper: Optional[float] = None
    middle: Optional[float] = None
    lower: Optional[float] = None
    bandwidth_pct: Optional[float] = Field(
        default=None, description="(upper - lower) / middle * 100"
    )
    position: str = Field(
        default="无法判断", description="价格位于上轨附近/中轨附近/下轨附近"
    )
    explanation: Optional[str] = None


class TechnicalIndicators(BaseModel):
    """Aggregated technical indicator results for a single stock."""

    symbol: str
    market_type: str
    latest_close: Optional[float] = None
    latest_date: Optional[date] = None
    moving_averages: MovingAverages = Field(default_factory=MovingAverages)
    macd: MACDResult = Field(default_factory=MACDResult)
    rsi: RSIResult = Field(default_factory=RSIResult)
    bollinger: BollingerBands = Field(default_factory=BollingerBands)
    timeframe: str = Field(default="daily", description="daily/weekly/monthly")
    message: Optional[str] = Field(
        default=None, description="Warning if insufficient data"
    )


class MultiTimeframeTechnical(BaseModel):
    """Multi-timeframe technical analysis result."""

    symbol: str
    market_type: str
    daily: TechnicalIndicators
    weekly: Optional[TechnicalIndicators] = None
    monthly: Optional[TechnicalIndicators] = None


class VolumeAnalysis(BaseModel):
    """Volume anomaly and turnover analysis."""

    symbol: str
    market_type: str
    latest_volume: Optional[float] = None
    avg_volume_20d: Optional[float] = None
    volume_ratio: Optional[float] = Field(
        default=None, description="latest_volume / avg_volume_20d"
    )
    is_anomaly: bool = Field(default=False, description="True if volume_ratio > 2.0")
    assessment: str = Field(default="正常", description="放量/缩量/正常")
    explanation: Optional[str] = None
    message: Optional[str] = None


class SignalSummary(BaseModel):
    """Aggregated signal from all technical indicators via vote counting."""

    symbol: str
    market_type: str
    overall_signal: str = Field(default="中性", description="偏多/偏空/中性")
    confidence: str = Field(
        default="低", description="高/中/低 based on indicator agreement"
    )
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    details: list[str] = Field(
        default_factory=list, description="Per-indicator signal descriptions"
    )
    explanation: Optional[str] = None


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


# --- Guardrails models ---


class Severity(str, Enum):
    """Severity level for guardrail rule violations."""

    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of position threshold alerts."""

    GAIN_REVIEW = "gain_review"
    LOSS_REVIEW = "loss_review"
    RAPID_CHANGE = "rapid_change"


class GuardrailsConfig(BaseModel):
    """User-configurable investment guardrail rules with conservative defaults."""

    max_single_position_pct: float = Field(
        default=15.0, description="Max % of portfolio in a single stock"
    )
    max_sector_pct: float = Field(
        default=35.0, description="Max % of portfolio in a single sector"
    )
    max_total_positions: int = Field(default=8, description="Max number of positions")
    min_cash_reserve_pct: float = Field(
        default=10.0, description="Min cash reserve as % of total portfolio"
    )
    gain_review_threshold: float = Field(
        default=30.0, description="Review when unrealized gain exceeds +X%"
    )
    loss_review_threshold: float = Field(
        default=-10.0, description="Review when unrealized loss exceeds -X%"
    )
    rapid_change_threshold: float = Field(
        default=10.0, description="Alert on +/-X% change in 1 week"
    )


class RuleViolation(BaseModel):
    """A single guardrail rule violation."""

    rule_name: str
    severity: Severity
    current_value: float
    limit_value: float
    message: str
    affected_symbols: list[str] = Field(default_factory=list)


class HealthCheckResult(BaseModel):
    """Result of portfolio health check against guardrail rules."""

    violations: list[RuleViolation] = Field(default_factory=list)
    passed: bool = True
    summary: str = "所有规则通过"


class PositionAlert(BaseModel):
    """An alert triggered by a position exceeding P&L thresholds."""

    symbol: str
    alert_type: AlertType
    current_pnl_pct: float
    threshold_pct: float
    holding_days: Optional[int] = None
    original_thesis: Optional[str] = None
    message: str


class RecentPriceChange(BaseModel):
    """Recent price movement for chasing/panic detection."""

    one_week_pct: Optional[float] = None
    one_month_pct: Optional[float] = None


class EmotionTradeStats(BaseModel):
    """Historical trade outcome statistics for a specific emotion."""

    emotion: str
    total_trades: int = 0
    profitable_pct: float = 0.0


class PortfolioContext(BaseModel):
    """Portfolio-level context for agent decision-making."""

    total_positions: int
    total_market_value: float
    sector_allocations: dict[str, float] = Field(default_factory=dict)
    cash_balance: Optional[float] = None


class CurrentPositionInfo(BaseModel):
    """Current position details for a specific symbol in pre-trade-data."""

    symbol: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl_pct: float
    allocation_pct: float
    holding_days: Optional[int] = None


class PreTradeData(BaseModel):
    """Aggregated data for agent pre-trade review — all 5 dimensions in one response."""

    symbol: str
    action: str
    quantity: float
    price: Optional[float] = None
    simulated_violations: list[RuleViolation] = Field(default_factory=list)
    portfolio_context: Optional[PortfolioContext] = None
    current_position: Optional[CurrentPositionInfo] = None
    current_alerts: list[PositionAlert] = Field(default_factory=list)
    recent_price_change: RecentPriceChange = Field(default_factory=RecentPriceChange)
    emotion_stats: dict[str, EmotionTradeStats] = Field(default_factory=dict)
    original_thesis: Optional[str] = None


# Resolve forward references for StockReport
StockReport.model_rebuild()
