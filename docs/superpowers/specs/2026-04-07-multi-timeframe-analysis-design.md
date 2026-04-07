# Multi-Timeframe Technical Analysis

## Context

The current `analyze technical` command only operates on daily data, limiting the user's ability to perceive medium-to-long-term trends. Weekly and monthly timeframe indicators provide essential context for understanding whether a stock is in an uptrend, downtrend, or consolidation at a macro level. This feature adds weekly/monthly technical indicator output to complement the existing daily analysis — the CLI provides data only; qualitative interpretation is left to the agent.

## Design Principle

**CLI = data provider, Agent = interpreter.** The CLI outputs numerical indicator values for each timeframe without making qualitative judgments (no "bullish"/"bearish" labels). The Claude skill layer interprets the data.

## Approach: Computation-Layer Aggregation

Aggregate existing daily price bars into weekly/monthly bars at computation time. No changes to `PriceBar` model, database schema, or market providers.

**Why not API-based weekly/monthly data?**
- Aggregated results are mathematically identical for complete periods
- CoinGecko doesn't support weekly/monthly K-lines, requiring a fallback anyway
- Zero additional API calls; all markets handled uniformly

## Data Aggregation

### New file: `haoinvest/engine/aggregation.py`

Two public functions:

```python
def aggregate_to_weekly(daily_bars: list[PriceBar]) -> list[PriceBar]
def aggregate_to_monthly(daily_bars: list[PriceBar]) -> list[PriceBar]
```

**Aggregation rules per period (week/month):**

| Field | Rule |
|-------|------|
| `open` | First trading day's open |
| `high` | max(all highs) |
| `low` | min(all lows) |
| `close` | Last trading day's close |
| `volume` | sum(all volumes) |
| `trade_date` | Last trading day's date |
| `symbol` | Inherited from source bars |
| `market_type` | Inherited from source bars |

**Week boundary:** ISO week (Monday–Sunday).
**Month boundary:** Calendar month.

**Handling incomplete periods:** The current (most recent) week/month may be incomplete. Include it as-is — the agent can account for this.

### Data period requirement

To compute monthly MA20 + MACD(26), need ~26 months of monthly data → ~2 years of daily data. The `analyze technical` default fetch period expands from 1 year to 2 years.

## Technical Indicator Calculation

Reuse existing `compute_technical()` from `haoinvest/engine/technical_engine.py`. It accepts a DataFrame and is timeframe-agnostic.

**Indicators computed per timeframe (weekly & monthly):**
- MA: SMA(5, 10, 20), EMA(12, 26)
- MACD: DIF, DEA, histogram (fast=12, slow=26, signal=9)
- RSI(14)

Bollinger Bands are excluded from weekly/monthly to keep output concise.

**Call flow:**
1. Fetch 2 years of daily bars
2. `aggregate_to_weekly(bars)` → weekly bars → `pricebars_to_dataframe()` → `compute_technical()` → weekly indicators
3. `aggregate_to_monthly(bars)` → monthly bars → `pricebars_to_dataframe()` → `compute_technical()` → monthly indicators
4. Daily bars → existing flow unchanged

## Output Structure

### Text output (default)

Layered from macro to micro:

```
📊 月线技术指标 (Monthly)
  MA: MA5=xx.xx  MA10=xx.xx  MA20=xx.xx | EMA12=xx.xx  EMA26=xx.xx
  MACD: DIF=xx.xx  DEA=xx.xx  MACD=xx.xx
  RSI(14): xx.xx

📊 周线技术指标 (Weekly)
  MA: MA5=xx.xx  MA10=xx.xx  MA20=xx.xx | EMA12=xx.xx  EMA26=xx.xx
  MACD: DIF=xx.xx  DEA=xx.xx  MACD=xx.xx
  RSI(14): xx.xx

📊 日线技术指标 (Daily)
  [existing output unchanged]
```

### JSON output (`--format json`)

Add `weekly` and `monthly` keys at the same level as the existing daily indicators:

```json
{
  "monthly": { "ma": {...}, "macd": {...}, "rsi": ... },
  "weekly": { "ma": {...}, "macd": {...}, "rsi": ... },
  "daily": { ... }
}
```

## Files to Modify

| File | Change |
|------|--------|
| `haoinvest/engine/aggregation.py` | **New** — weekly/monthly aggregation functions |
| `haoinvest/analysis/technical.py` | Add multi-timeframe analysis entry point |
| `haoinvest/cli/analyze.py` | Expand `technical` command to output weekly/monthly layers |
| `haoinvest/cli/formatters.py` | Format weekly/monthly indicator output |
| `haoinvest/models.py` | Add `timeframe` field to `TechnicalIndicators` (optional) |
| `tests/test_aggregation.py` | **New** — unit tests for aggregation logic |
| `tests/test_technical.py` | Add multi-timeframe analysis tests |

## Verification

1. **Unit tests:** Test aggregation with known daily data → verify weekly/monthly OHLCV values
2. **Integration test:** Run `haoinvest analyze technical 600519` → verify monthly/weekly/daily sections all appear
3. **JSON output:** Run with `--format json` → verify `monthly` and `weekly` keys present with correct structure
4. **Edge cases:** Test with < 1 month of data (monthly section should gracefully show what's available or indicate insufficient data)
