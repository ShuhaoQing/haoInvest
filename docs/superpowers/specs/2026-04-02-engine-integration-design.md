# Engine Integration Design: pandas-ta + QuantStats + PyPortfolioOpt

## Context

haoInvest's `analysis/` and `strategy/` modules currently use hand-rolled pure Python for all financial calculations (SMA, EMA, MACD, RSI, Bollinger, volatility, Sharpe, drawdown, correlation, portfolio optimization). This works but:

- **Reinvents the wheel**: Standard financial computations re-implemented from scratch
- **Missing features**: min_volatility ignores correlations (aliases to risk_parity), no Max Sharpe optimization, no Sortino ratio
- **Correctness risk**: Hand-rolled EMA/RSI/Bollinger may drift from industry-standard implementations

This design replaces the hand-rolled math with three established, actively-maintained libraries while preserving the existing CLI interface and Pydantic model contracts.

## Library Selection

| Domain | Library | Why this one |
|--------|---------|-------------|
| Technical indicators | **pandas-ta-classic** | 200+ indicators, pure Pandas extension, no C dependency, data-source agnostic |
| Risk/performance metrics | **QuantStats** | 60+ metrics, HTML reports, largest community (6.9k stars), data-source agnostic |
| Portfolio optimization | **PyPortfolioOpt** | Simplest API, best docs, Mean-Variance/HRP/Black-Litterman, sufficient for ≤10 holdings |
| Fundamental analysis | **Keep hand-written** | No library supports A-shares + fundamental data; existing code + AKShare is the best fit |

**Rejected alternatives**: FinanceToolkit (tied to FMP, no A-shares), Riskfolio-Lib (steep learning curve for personal project), TA-Lib (requires C library install), OpenBB (full platform, overkill).

## Architecture

### High-Level Data Flow

```
CLI Command
    ↓
analysis/*.py | strategy/*.py    ← Adapter layer (DB access + validation + delegation)
    ↓
engine/databridge.py             ← PriceBar list → pd.DataFrame conversion
    ↓
engine/*_engine.py               ← Pure computation (DataFrame in, Pydantic model out)
    ↓ calls
pandas-ta | QuantStats | PyPortfolioOpt
    ↓
Pydantic Model → CLI output
```

### Invariants (things that do NOT change)

- All Pydantic models in `models.py`
- CLI command signatures and output format
- `fundamental.py`, `volume.py`, `signals.py`, `report.py` (minimal changes)
- Price caching mechanism in `db.py`
- `rebalance.py` (pure arithmetic, no library needed)

## Module Design

### engine/databridge.py — Data Conversion

Converts between the DB layer (`list[PriceBar]`) and the library layer (`pd.DataFrame`/`pd.Series`).

```python
def pricebars_to_dataframe(bars: list[PriceBar]) -> pd.DataFrame:
    """PriceBar list → OHLCV DataFrame with DatetimeIndex.
    Columns: open, high, low, close, volume. Sorted by date asc.
    Drops rows where close is None."""

def closes_series(bars: list[PriceBar]) -> pd.Series:
    """Extract close prices as pd.Series with DatetimeIndex."""

def daily_returns(bars: list[PriceBar]) -> pd.Series:
    """Daily pct_change() returns, first NaN dropped."""

def multi_asset_prices(
    db: Database,
    symbols_with_market: list[tuple[str, MarketType]],
    start_date: date | None, end_date: date | None,
) -> pd.DataFrame:
    """Multi-asset close prices DataFrame (one column per symbol).
    Dates aligned via inner join (only trading days where ALL assets have data).
    Used by PyPortfolioOpt for covariance estimation."""

def safe_float(val) -> float | None:
    """Convert pandas scalar (including NaN/NaT) to float or None."""
```

### engine/technical_engine.py — Technical Indicators (pandas-ta)

Replaces `math_utils.py`. Pure computation: DataFrame in, `TechnicalIndicators` model out.

```python
def compute_technical(df: pd.DataFrame, verbose: bool = False) -> TechnicalIndicators:
    """Compute all technical indicators using pandas-ta.
    
    Computes: SMA(5/10/20/60), EMA(12/26), MACD(12,26,9), RSI(14), Bollinger(20,2).
    Generates Chinese assessments (trend, signal, zone, position).
    Returns None for indicators with insufficient data (pandas-ta returns NaN)."""
```

**pandas-ta mapping**:

| Current (math_utils.py) | New (pandas-ta) |
|--------------------------|-----------------|
| `sma(values, period)` | `df.ta.sma(length=period)` |
| `ema(values, period)` | `df.ta.ema(length=period)` |
| `compute_macd(closes)` | `df.ta.macd(fast=12, slow=26, signal=9)` → columns `MACD_12_26_9`, `MACDh_12_26_9`, `MACDs_12_26_9` |
| `compute_rsi(closes, 14)` | `df.ta.rsi(length=14)` |
| `compute_bollinger(closes, 20, 2)` | `df.ta.bbands(length=20, std=2)` → columns `BBL_20_2.0`, `BBM_20_2.0`, `BBU_20_2.0` |

**Chinese assessment logic** stays in this module as private `_assess_*()` functions — the assessments are derived from indicator values and belong with the computation.

### engine/risk_engine.py — Risk Metrics (QuantStats)

Replaces the calculation logic in `risk.py`. Pure computation: returns Series in, `RiskMetrics` model out.

```python
def compute_risk_metrics(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
) -> RiskMetrics:
    """Compute risk metrics using QuantStats.
    
    Metrics: annualized_volatility, max_drawdown_pct, sharpe_ratio,
    sortino_ratio (NEW), total_return_pct."""

def compute_correlation_matrix(
    returns_df: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """Pearson correlation matrix from multi-column returns DataFrame.
    Uses pandas .corr() (no QuantStats needed for this)."""
```

**QuantStats mapping**:

| Current (risk.py) | New (QuantStats) |
|--------------------|------------------|
| Hand-rolled annualized vol | `qs.stats.volatility(returns, periods=252)` |
| Hand-rolled max drawdown | `qs.stats.max_drawdown(returns)` |
| Hand-rolled Sharpe | `qs.stats.sharpe(returns, rf=daily_rf, periods=252)` |
| Hand-rolled Pearson | `returns_df.corr()` (pandas built-in) |
| *(not available)* | `qs.stats.sortino(returns)` — **NEW** |

### engine/optimization_engine.py — Portfolio Optimization (PyPortfolioOpt)

Replaces `optimizer.py` logic. Pure computation: prices DataFrame in, weights dict out.

```python
def optimize_portfolio(
    prices_df: pd.DataFrame,
    method: str = "risk_parity",
    risk_free_rate: float = 0.02,
) -> dict[str, float]:
    """Optimize portfolio weights using PyPortfolioOpt.
    
    Methods:
    - equal_weight: 1/N allocation (no library needed)
    - risk_parity: HRPOpt — Hierarchical Risk Parity (uses correlations)
    - min_volatility: EfficientFrontier.min_volatility()
    - max_sharpe: EfficientFrontier.max_sharpe() — NEW
    
    Falls back to equal_weight on OptimizationError."""
```

**PyPortfolioOpt mapping**:

| Current method | New implementation |
|----------------|-------------------|
| `equal_weight` | Stays hand-rolled (trivial: 1/N) |
| `risk_parity` (inverse-vol, ignores correlations) | `HRPOpt(returns).optimize()` — proper hierarchical risk parity |
| `min_volatility` (aliased to risk_parity) | `EfficientFrontier(mu, S).min_volatility()` — real mean-variance optimization |
| *(not available)* | `EfficientFrontier(mu, S).max_sharpe()` — **NEW** |

## Adapter Layer Changes

The existing `analysis/` and `strategy/` files become thin adapters:

### analysis/technical.py
```python
def analyze_technical(db, symbol, market_type, start_date, end_date, verbose):
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    if not bars:
        return TechnicalIndicators(symbol=symbol, ..., message="No price data")
    df = pricebars_to_dataframe(bars)
    if len(df) < 14:
        return TechnicalIndicators(symbol=symbol, ..., message="Insufficient data")
    result = compute_technical(df, verbose)
    result.symbol = symbol
    result.market_type = market_type.value
    return result
```

### analysis/risk.py
```python
def calculate_risk_metrics(db, symbol, market_type, start_date, end_date, risk_free_rate=0.02):
    bars = db.get_prices(symbol, market_type, start_date, end_date)
    if len(bars) < 2:
        return RiskMetrics(num_days=len(bars), message="Insufficient data")
    returns = daily_returns(bars)
    result = compute_risk_metrics(returns, risk_free_rate)
    result.num_days = len(bars)
    return result
```

### strategy/optimizer.py
```python
def suggest_allocation(db, symbols_with_market, method, start_date, end_date):
    prices_df = multi_asset_prices(db, symbols_with_market, start_date, end_date)
    weights = optimize_portfolio(prices_df, method)
    return AllocationSuggestion(method=method, weights=weights, explanation=EXPLANATIONS[method])
```

## File Changes Summary

| File | Action |
|------|--------|
| `haoinvest/engine/__init__.py` | **CREATE** |
| `haoinvest/engine/databridge.py` | **CREATE** |
| `haoinvest/engine/technical_engine.py` | **CREATE** |
| `haoinvest/engine/risk_engine.py` | **CREATE** |
| `haoinvest/engine/optimization_engine.py` | **CREATE** |
| `haoinvest/analysis/math_utils.py` | **DELETE** |
| `haoinvest/analysis/technical.py` | **MODIFY** → thin adapter |
| `haoinvest/analysis/risk.py` | **MODIFY** → thin adapter |
| `haoinvest/strategy/optimizer.py` | **MODIFY** → thin adapter, add max_sharpe |
| `haoinvest/cli/strategy.py` | **MODIFY** → add max_sharpe to method choices |
| `haoinvest/models.py` | **MODIFY** → add `sortino_ratio` field to RiskMetrics |
| `pyproject.toml` | **MODIFY** → add 3 new dependencies |
| `tests/test_engine/` | **CREATE** — unit tests for engine modules |
| Existing test files | **MODIFY** — update imports, adjust tolerances |

## New Capabilities

**Immediately available (included in this work)**:
- **Max Sharpe optimization** — new CLI option `--method max_sharpe`
- **Sortino ratio** — added to RiskMetrics output
- **Proper risk parity** — HRP uses correlation structure, not just inverse-vol
- **Proper min-volatility** — uses covariance matrix, considers cross-asset correlations

**Unlocked for future work (not in scope)**:
- QuantStats HTML tear sheets (`qs.reports.html()`)
- Efficient frontier visualization
- 130+ additional technical indicators from pandas-ta
- Portfolio-level risk metrics (Sharpe/drawdown for the whole portfolio)
- Benchmark comparison

## Error Handling

- **Insufficient data**: Validate data length BEFORE calling libraries. Return early with message model (same as current behavior).
- **NaN from libraries**: pandas-ta returns NaN when data is insufficient for a given indicator. `safe_float()` converts NaN → None, matching current Pydantic model defaults.
- **Optimization failure**: PyPortfolioOpt may raise `OptimizationError` (singular covariance matrix, infeasible constraints). Catch and fall back to equal_weight with explanatory note.

## Implementation Phases

1. **Dependencies + databridge**: Add libs to `pyproject.toml`, create `engine/databridge.py` with tests
2. **Technical engine**: Create `engine/technical_engine.py`, modify `analysis/technical.py`, delete `math_utils.py`
3. **Risk engine**: Create `engine/risk_engine.py`, modify `analysis/risk.py`, add sortino to model
4. **Optimization engine**: Create `engine/optimization_engine.py`, modify `strategy/optimizer.py` + CLI
5. **Cleanup + integration tests**: Remove dead code, run full test suite, verify CLI output

## Verification

After each phase:
```bash
pytest                          # All tests pass
pytest -m "not integration"     # Unit tests pass without network
uv run ruff check .             # No lint errors
uv run ruff format --check .    # Format clean
```

End-to-end CLI verification:
```bash
uv run haoinvest analyze technical 600519 --verbose
uv run haoinvest analyze risk 600519
uv run haoinvest analyze correlation 600519,000858
uv run haoinvest strategy optimize --method max_sharpe
uv run haoinvest strategy optimize --method min_volatility
```
