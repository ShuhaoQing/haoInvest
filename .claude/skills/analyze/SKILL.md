---
name: analyze
description: "Deep analysis of stocks and portfolio — fundamental analysis (PE/PB/ROE), risk metrics (volatility, drawdown, Sharpe), correlation matrix. Use when the user wants to evaluate a stock or assess portfolio risk."
user_invocable: true
---

# /analyze — Deep Analysis

Perform fundamental and risk analysis on individual stocks or the entire portfolio.

## Setup

Run all Python code via `uv run python -c "..."` from the project root `/Users/shuhaoqing/repo/haoInvest`.

```python
from haoinvest.db import Database
from haoinvest.models import MarketType
from haoinvest.analysis.fundamental import analyze_stock
from haoinvest.analysis.risk import calculate_risk_metrics, portfolio_correlation
from haoinvest.analysis.report import full_stock_report

db = Database()
db.init_schema()
```

## Commands

### Stock Analysis
Includes current price — no need to call /market first.
```python
result = analyze_stock("600519", MarketType.A_SHARE)
```
Returns: name, price, PE, PB, sector, valuation assessment.

Display the valuation assessment with explanation of what PE/PB levels mean for a beginner.

### Full Report (with risk metrics)
Requires price history in the database. Fetch and cache first if needed:
```python
from haoinvest.market import get_provider
from haoinvest.models import PriceBar
from datetime import date, timedelta

provider = get_provider(MarketType.A_SHARE)
bars_raw = provider.get_price_history("600519", date(2025, 1, 1), date.today())
bars = [PriceBar(symbol="600519", market_type=MarketType.A_SHARE,
        trade_date=b["date"], open=b["open"], high=b["high"],
        low=b["low"], close=b["close"], volume=b["volume"]) for b in bars_raw]
db.save_prices(bars)

report = full_stock_report(db, "600519", MarketType.A_SHARE)
```

### Portfolio Risk Overview
```python
from haoinvest.portfolio.manager import PortfolioManager
pm = PortfolioManager(db)
holdings = pm.get_holdings()

symbols = [(h.symbol, h.market_type) for h in holdings]
# Calculate risk per holding and correlation
for sym, mt in symbols:
    metrics = calculate_risk_metrics(db, sym, mt)

corr = portfolio_correlation(db, symbols)
```

### Comparison Analysis
Analyze multiple stocks side by side. Run `analyze_stock` for each and present in a comparison table.

## Response Format
- Always respond in Chinese
- Explain what each metric means (this user is a beginner)
- Valuation assessment should be clear: 低估/合理/偏高/高估
- For risk metrics, explain in plain language: "年化波动率 25% 意味着..."
- Save analysis results to cache for traceability
