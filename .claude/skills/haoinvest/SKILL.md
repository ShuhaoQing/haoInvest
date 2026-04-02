---
name: haoinvest
description: "Investment management — portfolio, market data, analysis, strategy, journal. Use when the user asks about holdings, prices, stock analysis, allocation, or investment journaling."
user_invocable: true
---

# /haoinvest — Investment Management

All-in-one investment management via CLI + Claude Code agent. CLI does data + computation; you (the agent) do interpretation + recommendations.

## Agent Workflows

### Workflow 1: "帮我分析 XXX" — Analyze a stock

1. Run comprehensive report:
   ```bash
   uv run haoinvest analyze report <symbol>
   ```
2. For A-shares, also run peer comparison:
   ```bash
   uv run haoinvest analyze peer <symbol>
   ```
3. Interpret ALL sections in Chinese:
   - 估值: Is it cheap or expensive? Compare PE/PB to peers.
   - 财务健康: Is the company profitable and growing?
   - 风险: How volatile is it? What's the worst drawdown?
   - 技术面: What's the current trend?
   - Checklist: What's the buy-readiness score?
4. Point out weak areas and suggest what else to check
5. If data is missing (e.g., financial health = N/A), say so honestly

### Workflow 2: "我有闲钱想投资" — Investment direction

1. Check current portfolio:
   ```bash
   uv run haoinvest portfolio list
   ```
2. Identify concentration: which sectors are overweight?
3. Scan sector rankings:
   ```bash
   uv run haoinvest market sector-list
   ```
4. Drill into promising sectors:
   ```bash
   uv run haoinvest market sector <板块名>
   ```
5. Run reports on 2-3 candidates from underrepresented sectors
6. Explain WHY each candidate diversifies the portfolio

### Workflow 3: "我想买 XXX" — Buy decision

1. Run comprehensive report with checklist:
   ```bash
   uv run haoinvest analyze report <symbol>
   ```
2. Explain the buy-readiness score dimension by dimension
3. If score is low, explain which dimensions are concerning
4. Compare with peers:
   ```bash
   uv run haoinvest analyze peer <symbol>
   ```
5. Always remind: **这不是投资建议，最终决定需要你自己判断**

### Workflow 4: "对比 A 和 B" — Compare stocks

1. Batch fundamental comparison:
   ```bash
   uv run haoinvest analyze fundamental <A>,<B> --verbose
   ```
2. Batch technical comparison:
   ```bash
   uv run haoinvest analyze technical <A>,<B>
   ```
3. Summarize: who's better on what dimension, and overall recommendation

### Workflow 5: "定期体检" — Portfolio checkup

1. Portfolio holdings + P&L:
   ```bash
   uv run haoinvest portfolio list
   uv run haoinvest portfolio returns
   ```
2. Risk assessment:
   ```bash
   uv run haoinvest analyze risk
   ```
3. For each holding with poor risk metrics, run a quick report
4. Check allocation via:
   ```bash
   uv run haoinvest strategy optimize
   ```
5. Suggest rebalancing if needed

### Workflow 6: "情绪复盘" — Decision review

1. Review journal patterns:
   ```bash
   uv run haoinvest journal review --days 30
   ```
2. Analyze: which emotions led to good/bad decisions?
3. For entries needing retrospective, help add reflections
4. Gently suggest behavioral improvements

## Command Reference

### Market Data
```bash
uv run haoinvest market quote <symbol(s)>                      # Price + info (batch: comma-separated)
uv run haoinvest market history <symbol> [--start] [--end]     # OHLCV bars (30 days default)
uv run haoinvest market sector-list                            # A-share industry board ranking
uv run haoinvest market sector <name>                          # Sector constituents
```

### Analysis
```bash
uv run haoinvest analyze report <symbol>                       # Full report + buy-readiness checklist
uv run haoinvest analyze fundamental <symbol(s)> [--verbose]   # Valuation + financial health (batch OK)
uv run haoinvest analyze technical <symbol(s)>                 # MA/MACD/RSI/BB (batch OK)
uv run haoinvest analyze peer <symbol>                         # Same-sector peer comparison (A-shares)
uv run haoinvest analyze risk [--symbol <sym>]                 # Volatility, Sharpe, drawdown
uv run haoinvest analyze correlation <sym1,sym2,...>           # Correlation matrix
uv run haoinvest analyze volume <symbol>                       # Volume anomaly detection
uv run haoinvest analyze signals <symbol>                      # Aggregated technical signal
```

### Portfolio
```bash
uv run haoinvest portfolio list                                # All holdings
uv run haoinvest portfolio add-trade <symbol> <action> <qty> <price> [--fee] [--tax] [--date] [--note]
uv run haoinvest portfolio returns [--symbol <sym>]            # P&L
```
Actions: `buy`, `sell`, `dividend`, `split`, `transfer_in`, `transfer_out`

### Strategy
```bash
uv run haoinvest strategy optimize [--method equal_weight|risk_parity|min_volatility|max_sharpe]
uv run haoinvest strategy rebalance --target '{"600519": 0.5, "BTC_USDT": 0.5}'
```

### Journal
```bash
uv run haoinvest journal add "<content>" [--decision buy|sell|hold|watch|reflection] [--emotion rational|greedy|fearful|fomo|uncertain|confident|regretful] [--symbols <syms>]
uv run haoinvest journal list [--symbol <sym>] [--limit <n>]
uv run haoinvest journal review [--entry-id <id>] [--days <n>]
```

## Market Type Auto-Detection

- **6-digit number** (600519, 000001) → A-share
- **Contains `_USDT`** or known crypto (BTC, ETH, SOL) → Crypto
- **Otherwise** → US market
- Override with `--market-type a_share|crypto|us`

## Output Format

- Default: **Key-Value** (single records) or **TSV** (tables)
- `--json`: Full JSON output
- **Prefer TSV for list commands** — more compact for LLM parsing
- All commands support `--json`

## Crypto Special Handling

For crypto prices, **prefer Crypto.com MCP tools** when available:
- `mcp__claude_ai_Crypto_com__get_ticker` / `get_tickers`

Fall back to CLI if MCP is unavailable.

## Teaching Mode

When explaining metrics, always:
- Include "这意味着..." explanations for beginners
- Use analogies (e.g., "PE就像买房时的租售比，越低说明回本越快")
- Start with overall assessment, then detail on request
- Progressive disclosure: don't overwhelm with all metrics at once

## Response Guidelines

- Always respond in **Chinese**
- Show appropriate precision: A-shares 2 decimals, crypto 8 decimals
- For journal entries, gently ask about emotion and decision type if not specified
- For strategy recommendations, explain WHY each approach is suggested
- **Always ask for confirmation before recording trades**
