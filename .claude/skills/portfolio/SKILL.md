---
name: portfolio
description: "Manage investment portfolio — view holdings, add trades, track returns, periodic review. Use when the user asks about their holdings, wants to record a trade, check P&L, or review portfolio performance."
user_invocable: true
---

# /portfolio — Portfolio Management

You are managing the user's investment portfolio using the `haoinvest` Python library.

## Setup

Run all Python code via `uv run python -c "..."` from the project root `/Users/shuhaoqing/repo/haoInvest`.

Initialize database and portfolio manager:
```python
from haoinvest.db import Database
from haoinvest.portfolio.manager import PortfolioManager
from haoinvest.portfolio.returns import unrealized_pnl, realized_pnl, portfolio_returns_summary
from haoinvest.models import MarketType, Transaction, TransactionAction
from datetime import datetime

db = Database()
db.init_schema()
pm = PortfolioManager(db)
```

## Commands

Based on the user's request, execute one of these actions:

### View Holdings
```python
summary = pm.get_portfolio_summary()
```
Display as a formatted table: symbol, market type, quantity, avg cost, position cost, allocation %.

### Add Trade
Ask the user for: symbol, market type (A股/crypto), action (buy/sell), quantity, price, fees, date, note.

For A-shares: fee = commission, tax = stamp tax (0.05% on sells).
```python
pm.add_trade(Transaction(
    symbol="600519", market_type=MarketType.A_SHARE,
    action=TransactionAction.BUY, quantity=100, price=1680.0,
    fee=5.0, tax=0, executed_at=datetime(2026, 3, 28),
    note="reason for trade",
))
```

### Returns Tracking
For a single holding:
```python
result = unrealized_pnl(db, "600519", MarketType.A_SHARE, current_price=1700.0)
```

For realized P&L:
```python
result = realized_pnl(db, "600519", MarketType.A_SHARE)
```

For the entire portfolio (needs current prices from market providers):
```python
from haoinvest.market import get_provider
prices = {}
for pos in pm.get_holdings():
    provider = get_provider(pos.market_type)
    prices[(pos.symbol, pos.market_type)] = provider.get_current_price(pos.symbol)
result = portfolio_returns_summary(db, prices)
```

### Periodic Review
Show: total returns, per-holding P&L, recent transactions, and linked journal entries for a given period.

## Response Format
- Always respond in Chinese
- Format numbers with appropriate precision (A-share prices to 2 decimals, crypto to 8)
- Show P&L in both absolute value and percentage
- After adding a trade, show the updated holding for confirmation
