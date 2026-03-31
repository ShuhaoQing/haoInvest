# haoInvest

Personal investment portfolio management system — track holdings, analyze stocks, and build investment discipline.

Built for a beginner investor in China covering A-shares, US stocks, HK stocks, and crypto.

## Features

- **Portfolio Management** — Record trades, track positions, calculate time-weighted returns (TWR)
- **Market Data** — Real-time quotes from AKShare (A-shares), Yahoo Finance (US/HK), Crypto.com (crypto)
- **Fundamental Analysis** — PE/PB/ROE valuation assessment
- **Risk Metrics** — Annualized volatility, max drawdown, Sharpe ratio
- **Portfolio Optimization** — Equal weight, risk parity, minimum volatility allocation strategies
- **Investment Journal** — Structured entries with decision type and emotion tagging for pattern analysis
- **Claude Code Skills** — Natural language interface via 5 custom skills (`/portfolio`, `/market`, `/analyze`, `/strategy`, `/journal`)

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)

## Installation

```bash
git clone https://github.com/user/haoInvest.git
cd haoInvest
uv sync
```

## Usage

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

### Via Claude Code Skills

Use the custom skills in Claude Code for natural language interaction:

| Skill | Purpose |
|-------|---------|
| `/portfolio` | View holdings, record trades, check P&L |
| `/market` | Query real-time prices and market conditions |
| `/analyze` | Fundamental analysis and risk metrics |
| `/strategy` | Portfolio optimization and rebalance suggestions |
| `/journal` | Log investment decisions and review patterns |

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

## License

Private project.
