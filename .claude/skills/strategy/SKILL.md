---
name: strategy
description: "Portfolio optimization and rebalance — suggest optimal allocation (equal weight, risk parity, min volatility), generate rebalance trades, scenario analysis. Use when the user wants allocation advice or to rebalance."
user_invocable: true
---

# /strategy — Strategy & Rebalance

Provide portfolio optimization suggestions and generate rebalance trade instructions.

## Setup

Run all Python code via `uv run python -c "..."` from the project root `/Users/shuhaoqing/repo/haoInvest`.

```python
from haoinvest.db import Database
from haoinvest.models import MarketType
from haoinvest.portfolio.manager import PortfolioManager
from haoinvest.strategy.optimizer import suggest_allocation
from haoinvest.strategy.rebalance import calculate_rebalance
from haoinvest.market import get_provider

db = Database()
db.init_schema()
pm = PortfolioManager(db)
```

## Commands

### Suggest Allocation
Available methods: `equal_weight`, `risk_parity`, `min_volatility`.

```python
holdings = pm.get_holdings()
symbols_with_market = [(h.symbol, h.market_type) for h in holdings]

# Show all three strategies for comparison
for method in ["equal_weight", "risk_parity", "min_volatility"]:
    result = suggest_allocation(db, symbols_with_market, method=method)
```

Present all three strategies in a comparison table with the explanation for each.
Then recommend the most suitable one based on the user's situation.

### Rebalance Plan
After the user chooses a strategy:
```python
# Get current prices
prices = {}
for h in holdings:
    provider = get_provider(h.market_type)
    prices[h.symbol] = provider.get_current_price(h.symbol)

trades = calculate_rebalance(db, target_weights, prices)
```

Display the trade instructions clearly: what to buy/sell, how much, at what price.
Ask for confirmation before recording trades.

### Execute Rebalance
After user confirms, record each trade via `/portfolio`:
```python
from haoinvest.models import Transaction, TransactionAction
from datetime import datetime

for trade in trades:
    pm.add_trade(Transaction(
        symbol=trade["symbol"],
        market_type=MarketType.A_SHARE,  # detect from context
        action=TransactionAction.BUY if trade["action"] == "buy" else TransactionAction.SELL,
        quantity=trade["quantity"],
        price=trade["price"],
        executed_at=datetime.now(),
        note="Rebalance trade",
    ))
```

### Scenario Analysis
"What if the market drops 20%?"
Calculate impact on portfolio value using current holdings and hypothetical price changes.

## Response Format
- Always respond in Chinese
- Explain WHY each strategy recommends what it does
- Show current vs target allocation side by side
- For rebalance: show exact trade instructions with estimated costs
- Always ask for confirmation before recording trades
- Every suggestion must include the mathematical reasoning
