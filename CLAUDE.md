# CLAUDE.md — haoInvest

## Project Overview

Personal investment portfolio management system for a beginner investor in China.
Python library + Claude Code skills for tracking portfolios, analyzing stocks, and building investment discipline.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv (NOT pip)
- **Database**: SQLite (~/.haoinvest/haoinvest.db)
- **Data Sources**: Sina/Tencent/eastmoney direct APIs (A-shares), yfinance (US/HK), Crypto.com MCP (crypto)
- **Testing**: pytest

## Quick Commands

```bash
uv sync                              # Install dependencies
pytest                               # Run all tests
pytest -m "not integration"          # Skip tests that call external APIs
pytest tests/test_fx.py              # Single module
uv run ruff check .                  # Lint
uv run ruff format --check .         # Format check
```

## Project Structure

```
haoinvest/
├── models.py          # Pydantic models (Transaction, Position, JournalEntry, etc.)
├── db.py              # SQLite persistence, full CRUD, WAL mode
├── config.py          # Config management (~/.haoinvest/)
├── fx.py              # Currency conversion with fallback rates
├── journal.py         # Investment journal with emotion/decision tagging
├── cli/               # Typer CLI — entry point: `uv run haoinvest`
│   ├── __init__.py    # App + subcommand registration
│   ├── formatters.py  # Output formatting (text/JSON)
│   ├── analyze.py     # analyze subcommand
│   ├── journal.py     # journal subcommand
│   ├── market.py      # market subcommand
│   ├── portfolio.py   # portfolio subcommand
│   └── strategy.py    # strategy subcommand
├── engine/            # Computation engine — pandas-ta, QuantStats, PyPortfolioOpt
│   ├── databridge.py  # PriceBar ↔ pandas conversion, safe_float
│   ├── technical_engine.py  # Technical indicators (MA, MACD, RSI, BB)
│   ├── risk_engine.py       # Risk metrics (vol, drawdown, Sharpe, Sortino)
│   └── optimization_engine.py # Portfolio optimization (HRP, min vol, max Sharpe)
├── portfolio/         # Trade recording, position tracking, returns (TWR)
├── analysis/          # Thin adapters over engine
│   ├── fundamental.py # Valuation assessment (PE/PB/ROE), financial health
│   ├── technical.py   # Technical indicator adapter
│   ├── risk.py        # Risk metrics adapter
│   ├── peer.py        # Same-sector peer comparison
│   ├── report.py      # Full stock report with buy-readiness checklist
│   ├── signals.py     # Aggregate buy/sell signals
│   └── volume.py      # Volume analysis
├── market/            # Provider registry — A-share (Sina/Tencent/eastmoney), yfinance, crypto MCP
└── strategy/          # Optimizer adapter + rebalance logic
```

## CI

GitHub Actions runs on push/PR to `main`: ruff lint, ruff format check, pytest (non-integration).

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
- Before adding a dependency, run `uv pip index versions <pkg>` or check PyPI to confirm the actual latest version — never guess or rely on memory
- Prefer the most recent stable version of a library if it is compatible with the project

### Git Workflow

- The `main` branch is protected — never push directly to `main`
- All changes must go through a PR: create a feature branch first, then open a PR
- Branch naming: `feat/short-desc`, `fix/short-desc`

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
