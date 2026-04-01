# haoInvest

[![CI](https://github.com/ShuhaoQing/haoInvest/actions/workflows/ci.yml/badge.svg)](https://github.com/ShuhaoQing/haoInvest/actions/workflows/ci.yml)

Personal investment portfolio management system — track holdings, analyze stocks, and build investment discipline.

Built for a beginner investor in China covering A-shares, US stocks, HK stocks, and crypto.

## Features

- **Portfolio Management** — Record trades, track positions, calculate time-weighted returns (TWR)
- **Market Data** — Real-time quotes from AKShare (A-shares), Yahoo Finance (US/HK), Crypto.com (crypto)
- **Fundamental Analysis** — PE/PB/ROE valuation assessment
- **Risk Metrics** — Annualized volatility, max drawdown, Sharpe ratio
- **Portfolio Optimization** — Equal weight, risk parity, minimum volatility allocation strategies
- **Investment Journal** — Structured entries with decision type and emotion tagging for pattern analysis
- **Claude Code Skill** — Natural language interface via unified `/haoinvest` skill

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

## Installation

```bash
git clone https://github.com/ShuhaoQing/haoInvest.git
cd haoInvest
uv sync
```

## Usage

### CLI

```bash
# Market data
uv run haoinvest market quote 600519              # A-share quote
uv run haoinvest market history NVDA --start 2025-01-01

# Portfolio
uv run haoinvest portfolio list                   # View holdings
uv run haoinvest portfolio add-trade 600519 buy 100 1800.50
uv run haoinvest portfolio returns                # P&L summary

# Analysis
uv run haoinvest analyze fundamental 600519       # PE/PB valuation
uv run haoinvest analyze risk --symbol NVDA       # Volatility, Sharpe, drawdown
uv run haoinvest analyze correlation 600519,NVDA  # Correlation matrix

# Strategy
uv run haoinvest strategy optimize --method risk_parity
uv run haoinvest strategy rebalance --target '{"600519": 0.5, "NVDA": 0.5}'

# Journal
uv run haoinvest journal add "First buy of Moutai" --decision buy --emotion rational
uv run haoinvest journal list
uv run haoinvest journal review --days 30
```

All commands support `--json` for structured output. Symbols are auto-detected by format (6-digit → A-share, `_USDT` → crypto, otherwise US).

### As a Python Library

```python
from haoinvest.db import Database
from haoinvest.portfolio import PortfolioManager
from haoinvest.models import Transaction, TransactionAction, MarketType
from datetime import datetime

db = Database()
db.init_schema()
pm = PortfolioManager(db)

# Record a trade
txn = Transaction(
    symbol="NVDA",
    market_type=MarketType.US,
    action=TransactionAction.BUY,
    quantity=10,
    price=850.0,
    fee=10.0,
    executed_at=datetime.now()
)
pm.add_trade(txn)

# View holdings
holdings = pm.get_holdings()
```

### Via Claude Code

Use the unified `/haoinvest` skill in Claude Code for natural language interaction covering portfolio, market data, analysis, strategy, and journaling.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HAOINVEST_DATA_DIR` | `~/.haoinvest/` | Data directory path |
| `HAOINVEST_AKSHARE_TIMEOUT` | `30` | AKShare API timeout (seconds) |
| `HAOINVEST_CACHE_TTL` | `14400` | Analysis cache TTL (seconds) |
| `HAOINVEST_PRICE_CACHE_TTL` | `3600` | Price cache TTL (seconds) |

## Testing

```bash
pytest                           # Run all tests
pytest -m "not integration"      # Skip external API tests
pytest tests/test_fx.py          # Single module
```

## Architecture

```
┌─────────────────────────────────────┐
│  Claude Code Skills (5 skills)      │  ← Natural language interface
├─────────────────────────────────────┤
│  Python Library (haoinvest/)        │  ← Business logic
│  ├── portfolio/  analysis/          │
│  ├── market/     strategy/          │
│  └── journal     fx                 │
├─────────────────────────────────────┤
│  SQLite + External APIs             │  ← Data & storage
│  (AKShare, yfinance, Crypto.com)    │
└─────────────────────────────────────┘
```

## Known Issues / Backlog

Issues identified in code review, deferred for future PRs:

- **[test]** `test_analysis_technical.py` imports private functions (`_sma`, `_ema`, `_compute_macd`, etc.) directly — brittle test contract. Extract to `analysis/math_utils.py` or make public when refactoring.
- **[bug]** Analysis cache key in `report.py` does not include `price_start`/`price_end` — same symbol with different date ranges will hit the same cache entry. Needs a cache key scheme that incorporates date range.
- **[cleanup]** Defensive `isinstance(market_type, MarketType)` check in `technical.py`, `volume.py`, `signals.py` is redundant — type signatures already enforce `MarketType`. Remove and let type errors surface naturally.
- **[ux]** `analyze_technical` returns `message=None` when data is 14–25 days (enough for RSI but not Bollinger/MACD) — add a warning so users know some indicators are unavailable.
- **[docs]** Bollinger Bands position thresholds (0.8/0.2) are a custom choice, not industry standard — add a comment explaining the rationale.
- **[docs]** MACD golden/death cross detection uses histogram sign (simplified) rather than the traditional crossover event — add a note in verbose explanation or code comment.

## License

[MIT](LICENSE)
