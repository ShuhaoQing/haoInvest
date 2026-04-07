---
name: haoinvest
description: "Investment management — portfolio, market data, analysis, strategy, journal. Use when the user asks about holdings, prices, stock analysis, allocation, or investment journaling."
user_invocable: true
---

# /haoinvest — Investment Management

All-in-one investment management via CLI + Claude Code agent. CLI does data + computation; you (the agent) do interpretation + recommendations.

## Agent Workflows

### Workflow 1: "帮我分析 XXX" — Analyze a stock

1. Run composable analysis (single call, all modules including peer):
   ```bash
   uv run haoinvest analyze run <symbol>
   ```
   Or select specific modules:
   ```bash
   uv run haoinvest analyze run <symbol> --modules fundamental,risk,peer
   ```
2. Interpret ALL sections in Chinese:
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

### Workflow 3: "我想买/卖 XXX" — Pre-Trade Review (5维度审查)

**触发条件**: 用户表达买入/卖出意图时。

1. Run composable analysis + guardrails pre-trade data (2 calls):
   ```bash
   uv run haoinvest analyze run <symbol> --json
   uv run haoinvest guardrails pre-trade-data <symbol> <buy/sell> <qty> -m <type> --json
   ```
   If user hasn't specified quantity, ask first. If price not known, the command auto-fetches.

2. **5维度审查** — interpret each dimension:

   | 维度 | 数据来源 | Go | Caution | Stop |
   |------|---------|-----|---------|------|
   | 估值 | report.checklist.recommendation | "建议关注" | "谨慎观望" | "建议回避" |
   | 仓位 | pre-trade-data.simulated_violations (max_single_position_pct) | 无违规 | 有 warning | 有 critical |
   | 行业均衡 | pre-trade-data.simulated_violations (max_sector_pct) | 无违规 | 有违规 | — |
   | 信号 | report.signals.overall_signal | "偏多" | "中性" | "偏空" |
   | 情绪 | 语言检测 + pre-trade-data | 无风险信号 | 轻微信号 | 强信号 |

3. **综合判定**:
   - 0-1 个 Caution → **执行 (Go)**: "各维度基本通过，可以考虑执行"
   - 2-3 个 Caution → **谨慎 (Caution)**: "有几个维度需要注意，建议再想想"
   - 任何 Stop → **停止 (Stop)**: "建议暂缓，先解决以下问题..."

4. **隐式情绪检测** (见 Workflow 3b)

5. If proceeding, suggest recording journal:
   ```bash
   uv run haoinvest journal add "<决策理由>" --decision buy --emotion <detected> --symbols <symbol>
   ```

6. Always remind: **这不是投资建议，最终决定需要你自己判断**

### Workflow 3b: 隐式情绪检测 (每次交易讨论时自动执行)

**不要直接问用户"你现在什么情绪"** — 人在情绪中往往察觉不到。

**语言信号检测**:
| 情绪 | 关键词/模式 |
|------|-----------|
| FOMO | "赶紧买"、"不能再等了"、"错过就没了"、"别人都买了"、"马上" |
| GREEDY | "全仓冲"、"必涨"、"加杠杆"、"all in"、"翻倍" |
| FEARFUL | "撑不住了"、"割了吧"、"快跑"、"受不了了"、"止损" |

**数据信号检测** (from pre-trade-data):
- `recent_price_change.one_month_pct > 20%` + 买入意图 → 可能追涨
- `recent_price_change.one_month_pct < -15%` + 卖出意图 → 可能杀跌
- `current_alerts` 中有 `rapid_change` → 加强警惕
- `emotion_stats` 中该情绪的 `profitable_pct < 40%` → 历史表现不佳

**检测到风险信号时**:
- 温和提醒（不指责）："注意，这只股票最近一个月涨了28%。现在买入可能受到追涨情绪影响。"
- 引用历史数据："过去5次类似情况下的交易，只有20%盈利。"
- 建议："考虑等待24小时冷静后再决策。或者先做一下基本面分析，看看当前价格是否合理。"

**Journal 记录时建议情绪标签**: 根据检测到的信号建议标签，让用户确认或修正。

### Workflow 3c: 止盈/止损建议 (alerts 触发时)

当 `hao guardrails alerts --json` 返回报警时:

**gain_review 触发 (浮盈超过阈值)**:
1. 提醒："你持有的 XXX 浮盈已达 Y%，超过了 Z% 的审查阈值。"
2. 回顾原始 thesis: "你当初买入的理由是：{original_thesis}"
3. 引导思考:
   - thesis 是否仍然成立？公司基本面有变化吗？
   - 当前估值还合理吗？运行 `analyze report` 看看
   - 如果 thesis 不变且估值合理 → 可继续持有
   - 如果估值已偏高 → 建议考虑分批止盈（卖出 20-30% 锁定利润）

**loss_review 触发 (浮亏超过阈值)**:
1. 提醒："你持有的 XXX 浮亏已达 Y%。"
2. 回顾原始 thesis
3. 引导思考:
   - thesis 是否已被打破？（行业变化、公司暴雷、逻辑失效）
   - 如果 thesis 打破 → 建议果断止损，"不要让沉没成本影响判断"
   - 如果 thesis 未变，仅市场波动 → 建议耐心持有，考虑是否低位加仓

### Workflow 4: "对比 A 和 B" — Compare stocks

1. Batch composable analysis (single call):
   ```bash
   uv run haoinvest analyze run <A>,<B> --modules fundamental,risk,signals
   ```
2. Summarize: who's better on what dimension, and overall recommendation

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
# Composable analysis (preferred — single call, choose modules)
uv run haoinvest analyze run <symbol(s)>                       # All modules (fundamental,technical,risk,volume,signals,peer,checklist)
uv run haoinvest analyze run <symbol> --modules fundamental,risk,peer  # Selective modules
uv run haoinvest analyze run <symbol> --json                   # JSON output for structured parsing
uv run haoinvest analyze run <A>,<B> --modules fundamental     # Batch comparison

# Individual commands (still available)
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

### Guardrails
```bash
uv run haoinvest guardrails health-check [--cash <amt>] [--json]   # Check portfolio against rules
uv run haoinvest guardrails alerts [--json]                        # Scan all positions for threshold violations
uv run haoinvest guardrails config [--set KEY=VALUE] [--json]      # View/set guardrail configuration
uv run haoinvest guardrails pre-trade-data <sym> <buy/sell> <qty> [-m <type>] [--price] [--cash] [--json]  # Agent pre-trade data (aggregated)
```
Default rules (configurable): single position ≤15%, sector ≤35%, max 8 positions, cash reserve ≥10%, gain review +30%, loss review -10%, rapid change ±10%/week.

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
