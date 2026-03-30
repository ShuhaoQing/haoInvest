---
name: market
description: "Query real-time market data — stock prices, sector overview, crypto quotes. Use when the user asks about current prices, market conditions, or wants to check a ticker."
user_invocable: true
---

# /market — Market Data

Fetch and display real-time market data for A-shares and crypto.

## Setup

Run all Python code via `uv run python -c "..."` from the project root `/Users/shuhaoqing/repo/haoInvest`.

```python
from haoinvest.market import get_provider
from haoinvest.models import MarketType
```

## Market Type Detection

Automatically detect market type from symbol format:
- **6-digit number** (600519, 000001): A-share → `MarketType.A_SHARE`
- **Contains `_USDT`, `BTC`, `ETH`** or known crypto tickers: Crypto → `MarketType.CRYPTO`

## Commands

### Quick Quote
```python
provider = get_provider(MarketType.A_SHARE)  # or CRYPTO
price = provider.get_current_price("600519")
info = provider.get_basic_info("600519")
```
Display: name, current price, currency, sector, key ratios if available.

### Crypto Quote
For crypto, the Crypto.com MCP tools are available. Prefer MCP when possible:
- `mcp__claude_ai_Crypto_com__get_ticker` for single ticker
- `mcp__claude_ai_Crypto_com__get_tickers` for multiple

Fallback to CoinGecko provider if MCP is unavailable:
```python
provider = get_provider(MarketType.CRYPTO)
price = provider.get_current_price("BTC_USDT")
```

### Price History
```python
from datetime import date
bars = provider.get_price_history("600519", date(2026, 1, 1), date(2026, 3, 28))
```

## Response Format
- Always respond in Chinese
- Show price with appropriate precision
- For A-shares: include PE/PB if available from basic_info
- For crypto: show USD price and approximate CNY equivalent
