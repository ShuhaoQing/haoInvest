---
name: haoinvest
description: "Investment management — portfolio, market data, analysis, strategy, journal. Use when the user asks about holdings, prices, stock analysis, allocation, or investment journaling."
user_invocable: true
---

# /haoinvest — Investment Management

All-in-one investment management via CLI. Run commands with `uv run haoinvest <group> <command>`.

## Market Type Auto-Detection

The CLI auto-detects market type from symbol format:
- **6-digit number** (600519, 000001) → A-share
- **Contains `_USDT`** or known crypto (BTC, ETH, SOL) → Crypto
- **Otherwise** → US market
- Override with `--market-type a_share|crypto|us`

## Command Reference

### Market Data
```bash
uv run haoinvest market quote <symbol>                          # Price + basic info
uv run haoinvest market history <symbol> [--start] [--end]      # OHLCV bars (default: 30 days)
```

### Portfolio
```bash
uv run haoinvest portfolio list                                  # All holdings
uv run haoinvest portfolio add-trade <symbol> <action> <qty> <price> [--fee] [--tax] [--date] [--note]
uv run haoinvest portfolio returns [--symbol <sym>]              # P&L (all or single)
```
Actions: `buy`, `sell`, `dividend`, `split`, `transfer_in`, `transfer_out`

### Analysis
```bash
uv run haoinvest analyze fundamental <symbol>                    # PE/PB + valuation assessment
uv run haoinvest analyze risk [--symbol <sym>] [--start] [--end] # Volatility, Sharpe, drawdown
uv run haoinvest analyze correlation <sym1,sym2,...>             # Correlation matrix
```

### Strategy
```bash
uv run haoinvest strategy optimize [--method equal_weight|risk_parity|min_volatility|max_sharpe] [--symbols <syms>]
uv run haoinvest strategy rebalance --target '{"600519": 0.5, "BTC_USDT": 0.5}'
```

### Journal
```bash
uv run haoinvest journal add "<content>" [--decision buy|sell|hold|watch|reflection] [--emotion rational|greedy|fearful|fomo|uncertain|confident|regretful] [--symbols <syms>]
uv run haoinvest journal list [--symbol <sym>] [--limit <n>]
uv run haoinvest journal review [--entry-id <id>] [--days <n>]
```

## Global Options

All commands support `--json` flag for structured JSON output.

## Output Format

- Default: **Key-Value** text (single records) or **TSV** (tables/lists)
- `--json`: Full JSON output
- **Prefer TSV (default) over `--json` for list commands** (`portfolio list`, `journal list`, `market history`, `strategy rebalance`). TSV is more compact and easier for LLMs to parse. Use `--json` only when you need nested data or programmatic processing.
- You (Claude) should interpret the data and respond in **Chinese**, explaining concepts in beginner-friendly terms

## Crypto Special Handling

For crypto prices, **prefer Crypto.com MCP tools** when available:
- `mcp__claude_ai_Crypto_com__get_ticker` — single ticker
- `mcp__claude_ai_Crypto_com__get_tickers` — multiple tickers

Fall back to CLI `haoinvest market quote BTC_USDT` if MCP is unavailable.

## Sandbox Mode

For analyzing someone else's stocks (not your portfolio), just use `haoinvest analyze` or `haoinvest market` commands — they don't touch portfolio data. Set `HAOINVEST_DATA_DIR=/tmp/haoinvest_sandbox` if you need a temp database for trades.

## Response Guidelines

- Always respond in **Chinese**
- Explain what each metric means for beginners (e.g., "PE 20 意味着...")
- Show appropriate precision: A-shares 2 decimals, crypto 8 decimals
- For journal entries, gently ask about emotion and decision type if not specified
- For strategy recommendations, explain WHY each approach is suggested
- **Always ask for confirmation before recording trades**
