# haoInvest — Personal Investment Portfolio Management System

## Context

A beginner investor in China (currently trading A-shares and crypto, ≤5 holdings) wants a system to:
1. **Track and manage** their portfolio with accurate returns calculation
2. **Get traceable, reasonable advice** backed by data and clear reasoning
3. **Form a mature investment mindset** through structured journaling and AI-powered decision review

The system is built as **Claude Code skills + Python core library**, leveraging the existing Claude Code environment and Crypto.com MCP server.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Claude Code Skills (Interaction Layer)  │
│  /portfolio  /market  /analyze  /strategy /journal│
└──────────────────┬──────────────────────────────┘
                   │ calls
┌──────────────────▼──────────────────────────────┐
│           haoinvest Python Core Library           │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐      │
│  │ portfolio │ │ analysis  │ │ strategy  │      │
│  │ management│ │ & reports │ │ & rebalance│     │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘      │
│  ┌─────▼─────────────▼─────────────▼─────┐       │
│  │     market/ (data source abstraction)  │       │
│  │  AKShare(A-share) | Crypto.com MCP     │       │
│  │  yfinance(US/HK - reserved)            │       │
│  └─────┬─────────────────────────────────┘       │
│  ┌─────▼─────────────────────────────────┐       │
│  │  storage (SQLite) + config + fx        │       │
│  └───────────────────────────────────────┘       │
└─────────────────────────────────────────────────┘
```

Three layers:
1. **Skills (interaction)** — 5 Claude Code skills for natural language interaction
2. **Python core library** — portfolio, analysis, strategy modules
3. **Data + storage** — multi-source data aggregation + SQLite persistence

Key principle: **Python library works independently** (Notebook/CLI). Skills are the conversational frontend.

---

## Skills Design

### `/portfolio` — Portfolio Management
**Usage frequency: 2-3x/week**

- **View holdings**: current positions, cost basis, P&L, allocation %
- **Add trade**: record buy/sell with symbol, quantity, price, date, fees
- **Import trades**: bulk import from CSV
- **Returns tracking**: realized/unrealized gains, TWR, dividend income
- **Periodic review**: summarize returns + trades + linked journal entries for a period

### `/market` — Market Data
**Usage frequency: daily**

- **Quick quote**: current price, change %, volume for any symbol
- **Sector overview**: A-share sector heatmap, industry performance
- **Crypto quotes**: via Crypto.com MCP (fallback: CoinGecko API)
- Auto-detect market type: A-share codes → AKShare, crypto pairs → MCP

### `/analyze` — Deep Analysis
**Usage frequency: 1-2x/week**

- **Stock analysis**: fundamentals (PE/PB/ROE), industry comparison, valuation rating, **includes current price** (no need to call /market first)
- **Portfolio overview**: risk metrics (volatility, max drawdown, Sharpe), correlation matrix
- **Comparison**: side-by-side analysis of multiple symbols
- All results saved to analysis_cache for traceability

### `/strategy` — Strategy & Rebalance
**Usage frequency: 1-2x/month**

- **Optimization suggestions**: risk parity, equal weight, min volatility (simple calculations first, PyPortfolioOpt later when holdings > 10)
- **Rebalance plan**: compare current vs target allocation, generate specific trade instructions
- **Scenario analysis**: "what if market drops 20%?"
- Every suggestion includes reasoning and data backing
- After user confirmation, auto-record trades to portfolio

### `/journal` — Investment Journal
**Usage frequency: 1-2x/week**

- **Record thoughts**: structured entries with decision_type, related symbols, emotion tag
- **Review decisions**: look up past buy/sell reasons
- **AI retrospective**: analyze decision patterns, detect behavioral biases (chasing highs, panic selling)
- Structured data (emotion/decision_type) enables meaningful AI analysis

---

## Python Core Library Structure

```
haoinvest/
├── __init__.py
├── config.py              # Centralized config (~/.haoinvest/config.toml + env vars)
├── models.py              # Pydantic/dataclass models
├── db.py                  # SQLite database management, repository CRUD
├── fx.py                  # Currency conversion (CNY/USD/USDT)
├── portfolio/
│   ├── __init__.py
│   ├── manager.py         # Holdings management, trade recording
│   └── returns.py         # Returns calculation (TWR, realized/unrealized)
├── market/
│   ├── __init__.py        # Provider registry/factory by market_type
│   ├── provider.py        # Abstract provider interface (3 methods only)
│   ├── akshare_provider.py    # A-share data (pinned version)
│   └── crypto_provider.py     # Crypto data (MCP + CoinGecko fallback)
├── analysis/
│   ├── __init__.py
│   ├── fundamental.py     # Fundamental analysis (PE/PB/ROE)
│   ├── risk.py            # Risk metrics (volatility, drawdown, Sharpe)
│   └── report.py          # Analysis report assembly
├── strategy/
│   ├── __init__.py
│   ├── optimizer.py       # Simple optimization (risk parity, equal weight)
│   └── rebalance.py       # Rebalance calculation
└── journal.py             # Journal management (flat file, not a package)
```

### Market Provider Interface (minimal)

```python
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

class MarketProvider(ABC):
    @abstractmethod
    def get_current_price(self, symbol: str) -> Decimal:
        """Latest price in local currency."""

    @abstractmethod
    def get_price_history(self, symbol: str, start: date, end: date) -> list[dict]:
        """Returns [{date, open, high, low, close, volume}, ...]"""

    @abstractmethod
    def get_basic_info(self, symbol: str) -> dict:
        """Returns {name, sector, currency, ...}"""
```

---

## Data Model (SQLite Schema)

### portfolio_positions

```sql
CREATE TABLE portfolio_positions (
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
```

Note: `cached_*` fields are derived from `transactions`. Source of truth is always `transactions`.

### transactions

```sql
CREATE TABLE transactions (
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

CREATE INDEX idx_transactions_symbol ON transactions(symbol, market_type);
CREATE INDEX idx_transactions_executed_at ON transactions(executed_at);
```

### journal_entries

```sql
CREATE TABLE journal_entries (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    decision_type TEXT CHECK(decision_type IN ('buy', 'sell', 'hold', 'watch', 'reflection')),
    emotion TEXT CHECK(emotion IN ('rational', 'greedy', 'fearful', 'fomo', 'uncertain', 'confident', 'regretful')),
    retrospective TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE journal_symbol_tags (
    journal_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    PRIMARY KEY (journal_id, symbol)
);
```

### daily_snapshots

```sql
CREATE TABLE daily_snapshots (
    id INTEGER PRIMARY KEY,
    snapshot_date DATE NOT NULL UNIQUE,
    total_value_cny REAL NOT NULL,
    total_cost_cny REAL NOT NULL,
    cash_balance REAL NOT NULL DEFAULT 0,
    positions_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### price_history (local cache)

```sql
CREATE TABLE price_history (
    symbol TEXT NOT NULL,
    market_type TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, market_type, trade_date)
);
```

### analysis_cache

```sql
CREATE TABLE analysis_cache (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

---

## Key Dependencies

| Package | Purpose | Notes |
|---------|---------|-------|
| `akshare` (pinned) | A-share market data | Unstable API, pin version, wrap with error handling |
| `yfinance` | US/HK market data | Reserved for future, not in phase 1 |
| `pydantic` | Data models | Validation and serialization |
| `click` | CLI interface | For standalone CLI usage |
| `quantstats` | Performance reporting | Phase 2, when visualization needed |
| `PyPortfolioOpt` | Portfolio optimization | Phase 2, when holdings > 10 |

Phase 1 strategy module uses simple calculations (equal weight, risk parity, manual allocation) without PyPortfolioOpt.

---

## Precision Handling

Use `REAL` (float64) in SQLite with explicit rounding in Python:
- A-shares: round to 2 decimal places (price), integer shares (quantity)
- Crypto: round to 8 decimal places
- When checking "fully sold", use `abs(quantity) < 1e-10` instead of `== 0`

---

## Data Source Strategy

- **A-shares**: AKShare (pinned version). Provider layer catches API changes gracefully.
- **Crypto**: Crypto.com MCP (primary), CoinGecko free API (fallback)
- **US/HK**: yfinance (reserved, not implemented in phase 1)
- All providers implement the same 3-method interface
- `price_history` table caches historical data locally to reduce API calls

---

## Testing Strategy

```
tests/
├── conftest.py                    # Shared fixtures: in-memory SQLite, mock providers
├── test_models.py
├── test_portfolio/
│   ├── test_manager.py            # Buy/sell/position correctness (highest priority)
│   └── test_returns.py            # TWR with hand-calculable examples
├── test_market/
│   ├── test_provider_contract.py  # All providers pass interface tests
│   └── test_akshare_integration.py  # @pytest.mark.integration
├── test_fx.py
└── test_strategy/
    └── test_optimizer.py          # Simple allocation calculations
```

Priority test cases:
1. Buy/sell → position correctness (including full sell → quantity = 0)
2. Float precision boundaries (0.001 BTC × 3, sell 0.003)
3. TWR calculation with known data
4. Provider contract tests with mocked responses
5. Database schema/constraint verification

---

## Verification Plan

1. **Unit tests**: `pytest tests/` — all core logic covered
2. **Integration test**: AKShare provider fetches real data for a known symbol (600519)
3. **End-to-end skill test**: Use each skill in Claude Code conversation:
   - `/portfolio` → add a trade, view holdings, check returns
   - `/market` → query A-share price, query crypto price
   - `/analyze` → analyze a stock, analyze portfolio
   - `/strategy` → get allocation suggestion, simulate rebalance
   - `/journal` → create entry, review past entries, run AI retrospective
4. **Data consistency**: After multiple trades, verify `cached_quantity` matches `SUM from transactions`

---

## Phase 2 (Future)

- HK/US market support (yfinance provider)
- PyPortfolioOpt integration (when holdings > 10)
- QuantStats HTML reports
- Daily snapshot automation (cron/scheduled skill)
- News/sentiment analysis via LLM
- Price alerts and monitoring
