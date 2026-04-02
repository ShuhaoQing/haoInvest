# haoInvest

[![CI](https://github.com/ShuhaoQing/haoInvest/actions/workflows/ci.yml/badge.svg)](https://github.com/ShuhaoQing/haoInvest/actions/workflows/ci.yml)

Personal investment portfolio management system — track holdings, analyze stocks, and build investment discipline.

Built for a beginner investor in China covering A-shares, US stocks, HK stocks, and crypto.

## Features

- **Portfolio Management** — Record trades, track positions, calculate time-weighted returns (TWR)
- **Market Data** — Real-time quotes from AKShare (A-shares), Yahoo Finance (US/HK), Crypto.com (crypto)
- **Fundamental Analysis** — PE/PB/ROE valuation assessment with financial health scoring; batch support for multi-symbol comparison
- **Peer Comparison** — Find and compare same-sector stocks by valuation and performance
- **Sector Browsing** — Browse A-share industry sectors and their constituent stocks
- **Comprehensive Report** — Full stock report with buy-readiness checklist combining fundamental, technical, and risk analysis
- **Risk Metrics** — Annualized volatility, max drawdown, Sharpe ratio, Sortino ratio (powered by QuantStats)
- **Technical Analysis** — MA, MACD, RSI, Bollinger Bands with Chinese explanations (powered by pandas-ta)
- **Portfolio Optimization** — Equal weight, risk parity, minimum volatility, maximum Sharpe allocation (powered by PyPortfolioOpt)
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
uv run haoinvest analyze fundamental 600519,000858 # Batch comparison
uv run haoinvest analyze risk --symbol NVDA       # Volatility, Sharpe, drawdown
uv run haoinvest analyze correlation 600519,NVDA  # Correlation matrix
uv run haoinvest analyze peer 600519              # Same-sector peer comparison
uv run haoinvest analyze report 600519            # Full report with buy-readiness checklist

# Sectors
uv run haoinvest market sector-list               # A-share industry sectors
uv run haoinvest market sector 白酒               # Sector constituent stocks

# Strategy
uv run haoinvest strategy optimize --method risk_parity  # also: max_sharpe, min_volatility
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
│  Claude Code Skill (/haoinvest)     │  ← Natural language interface
├─────────────────────────────────────┤
│  CLI (haoinvest/cli/)               │  ← Typer commands, TSV/KV/JSON output
├─────────────────────────────────────┤
│  Adapters (analysis/, strategy/)    │  ← Thin wrappers, caching, I/O
├─────────────────────────────────────┤
│  Engine (engine/)                   │  ← Pure computation, no DB dependency
│  pandas-ta · QuantStats · PyPfOpt  │
├─────────────────────────────────────┤
│  Data (market/, portfolio/, db.py)  │  ← Providers, positions, SQLite
│  AKShare · yfinance · Crypto.com   │
└─────────────────────────────────────┘
```

## License

[MIT](LICENSE)
