# CLAUDE.md — haoInvest

## Project Overview

Personal investment portfolio management system for a beginner investor in China.
Python library + Claude Code skills for tracking portfolios, analyzing stocks, and building investment discipline.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv (NOT pip)
- **Database**: SQLite (~/.haoinvest/haoinvest.db)
- **Data Sources**: AKShare (A-shares), yfinance (US/HK), Crypto.com MCP (crypto)
- **Testing**: pytest

## Quick Commands

```bash
uv sync                              # Install dependencies
pytest                               # Run all tests
pytest -m "not integration"          # Skip tests that call external APIs
pytest tests/test_fx.py              # Single module
```

## Project Structure

```
haoinvest/
├── models.py          # Pydantic models (Transaction, Position, JournalEntry, etc.)
├── db.py              # SQLite persistence, full CRUD, WAL mode
├── config.py          # Config management (~/.haoinvest/)
├── fx.py              # Currency conversion with fallback rates
├── journal.py         # Investment journal with emotion/decision tagging
├── portfolio/         # Trade recording, position tracking, returns (TWR)
├── analysis/          # Fundamental (PE/PB/ROE), risk (volatility, Sharpe, drawdown)
├── market/            # Provider registry — akshare, yfinance, crypto MCP
└── strategy/          # Optimizer (equal weight, risk parity, min vol), rebalance
```

## Key Architecture Decisions

- **Transaction-driven positions**: Positions are derived from transaction history, not entered manually
- **Provider registry pattern**: Market data providers are pluggable via `market/__init__.py`
- **Cache with TTL**: Analysis results cached in SQLite to avoid redundant API calls
- **Precision rules**: Decimal places vary by market type (A-shares: 2dp, crypto: 8dp)
- **Zero threshold**: Use 1e-10 for floating-point comparison, never direct equality

## Rules

### Dependencies

- Always use `uv add`, never `pip install`
- Pin ALL dependencies with `==` to the latest stable version (e.g., `requests==2.32.3`)
- Never use `>=`, `~=`, or unpinned versions — reproducibility is non-negotiable
- Before adding a dependency, verify the latest version exists on PyPI

### Code Style

- Models go in `models.py` — all Pydantic data classes live there
- Database operations go in `db.py` — no SQL outside this file
- Market providers implement the abstract `MarketProvider` interface in `market/provider.py`
- Use `MarketType` enum for all market type references, never raw strings

### Testing

- Mark tests that call external APIs with `@pytest.mark.integration`
- Unit tests must not make network calls
- Use fixtures from `tests/conftest.py` for shared test setup

### Data Directory

- All user data lives under `~/.haoinvest/` (configurable via `HAOINVEST_DATA_DIR`)
- Never hardcode absolute paths to data files
