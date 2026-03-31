# haoInvest CLI 重构设计

## Context

当前 haoInvest 的 5 个 Claude Code skills 通过 `uv run python -c "..."` 内联执行 Python 代码。这带来几个问题：
1. **Skill 文件臃肿** — 每个 skill 包含大量 Python 代码片段，维护困难
2. **无法独立使用** — 离开 Claude Code 就无法方便地调用核心功能
3. **测试困难** — 内联代码无法被单元测试覆盖

同时，`akshare_provider.py` 的 fallback 处理代码有可读性问题：死代码、魔法数字、静默异常。

**目标：** 将 Python 库封装为 CLI 工具，简化 skills 为 CLI 命令调用，同时清理 akshare provider。

---

## Part 1: CLI 架构

### 框架选型

**Typer** — 基于 Click 构建，用 type hints 自动生成参数解析，与项目 Pydantic 风格一致。项目已依赖 Click。

### 命令结构

```
haoinvest <group> <command> [args] [options]

# Portfolio
haoinvest portfolio list                          # 查看持仓
haoinvest portfolio add-trade <symbol> <action> <quantity> <price> [--date] [--fee] [--market-type]
haoinvest portfolio returns [--symbol]             # 收益率（全部或单只）

# Market
haoinvest market quote <symbol>                    # 实时报价 + 基本面
haoinvest market history <symbol> [--start] [--end] # 历史行情

# Analysis
haoinvest analyze fundamental <symbol>             # 基本面分析
haoinvest analyze risk [--symbols] [--start]       # 风险指标（默认全持仓）

# Strategy
haoinvest strategy optimize [--method equal|risk-parity|min-vol]
haoinvest strategy rebalance [--target-json]       # 再平衡建议

# Journal
haoinvest journal add <symbol> <decision-type> <content> [--emotion]
haoinvest journal list [--symbol] [--limit]
haoinvest journal review [--symbol]                # 获取日记数据供 AI 分析
```

### 输出格式策略

LLM 是主要消费者。研究表明 Key-Value 文本比 JSON 省 30-40% token，且 LLM 解析准确率高。

**分层策略：**
- **单条记录**（报价、基本面）→ Key-Value 文本
  ```
  Name: 贵州茅台
  Price: 1800.50
  PE(TTM): 35.2
  PB: 12.1
  Sector: 白酒
  ```
- **列表数据**（持仓、交易历史）→ TSV（Tab-Separated Values）
  ```
  Symbol	Name	Quantity	AvgCost	CurrentPrice	PnL%
  600519	贵州茅台	100	1650.00	1800.50	9.12
  ```
- **复杂嵌套**（优化结果含多层数据）→ JSON

全局 `--json` flag 可强制所有输出为 JSON，供需要结构化解析的场景使用。

### 目录结构

```
haoinvest/cli/
├── __init__.py       # 主 Typer app，注册子命令组
├── portfolio.py      # portfolio 子命令
├── market.py         # market 子命令
├── analyze.py        # analyze 子命令
├── strategy.py       # strategy 子命令
├── journal.py        # journal 子命令
└── formatters.py     # 输出格式化工具（kv, tsv, json）
```

### CLI 层原则

- **薄胶水层** — 只做参数解析 + 输出格式化，调用已有库代码
- **所有 CLI 函数遵循同一模式**：解析参数 → 初始化 DB → 调用业务函数 → 格式化输出
- **错误输出到 stderr**，正常数据输出到 stdout

### pyproject.toml 变更

```toml
[project.scripts]
haoinvest = "haoinvest.cli:app"

# 新增依赖
# typer==0.24.1（最新稳定版，会自动拉 click）
# 移除单独的 click==8.3.1（typer 自带）
```

---

## Part 2: akshare_provider.py 清理

### 问题清单

| # | 问题 | 行号 | 严重性 |
|---|------|------|--------|
| 1 | Sina 请求死代码（取了数据但没用） | 206-217 | 高 |
| 2 | 魔法数字 tfields[39/46/45] | 226-232 | 中 |
| 3 | 多层 try-except pass 静默吞异常 | 68,126,187 | 高 |
| 4 | PE/PB 返回空字符串而非 None | 203-204 | 中 |
| 5 | 三次重复的 try-akshare-fallback 模式 | 57-72,104-130,170-191 | 中 |
| 6 | 格式注释错误（open/close 顺序写反） | 154 | 低 |

### 清理方案

**1. 抽取 fallback 通用模式**

```python
def _with_fallback(self, primary_fn, fallback_fn, symbol, *args):
    """Try primary (akshare), fall back to direct API on failure."""
    with _bypass_proxy():
        try:
            result = primary_fn(symbol, *args)
            if result is not None:
                return result
        except Exception as e:
            logger.debug("AKShare failed for %s: %s, trying fallback", symbol, e)
        return fallback_fn(symbol, *args)
```

每个 public 方法简化为一行 `_with_fallback` 调用。

**2. 删除 Sina 死代码**（206-217 行整段移除）

**3. 提取 Tencent 字段常量 + 独立方法**

```python
# Tencent quote field indices (v_sh603618="1~name~code~...")
_TENCENT_PE_TTM = 39
_TENCENT_TOTAL_CAP_YI = 45
_TENCENT_PB = 46

def _tencent_valuation(self, symbol: str) -> dict:
    """Fetch PE/PB/market cap from Tencent quote API."""
    ...
```

**4. 统一返回类型** — PE/PB 返回 `float | None`，total_cap 返回 `int | None`

**5. 添加 logging** — `logger.debug()` 记录 fallback 触发，不再静默 pass

**6. 修正格式注释** — Tencent kline 是 `[date, open, close, high, low, volume]`

---

## Part 3: Skill 整合

将 5 个独立 skills 合并为 1 个 `/haoinvest` skill。

### 新 Skill 结构

```markdown
# /haoinvest — Investment Management

## 使用方式
通过 `uv run haoinvest <command>` 调用 CLI。

## 命令参考
[命令表 — 与 CLI help 一致]

## 市场类型自动检测
- 6 位数字 → A_SHARE
- 含 _USDT / BTC / ETH → CRYPTO
- 其他 → 先尝试 US

## 输出解释
- CLI 输出 Key-Value / TSV / JSON 格式
- 你（Claude）负责将数据转化为中文回复
- 始终以初学者友好的方式解释数据

## Crypto 特殊处理
优先使用 Crypto.com MCP 工具获取加密货币数据
```

### 删除的 Skills

删除 `.claude/skills/` 下的 5 个独立目录：analyze/, journal/, market/, portfolio/, strategy/

---

## Part 4: 测试策略

### 单元测试（mock，不调外部 API）

每个 CLI 子命令组一个测试文件，使用 Typer 的 `CliRunner`：

```
tests/test_cli/
├── test_portfolio.py
├── test_market.py
├── test_analyze.py
├── test_strategy.py
└── test_journal.py
```

**测试示例股票：**
- A-share: `600519`（贵州茅台）、`000001`（平安银行）
- US: `AAPL`（苹果）
- Crypto: `BTC_USDT`

每个 CLI 命令至少覆盖：正常路径、参数缺失、symbol 不存在。

### 集成测试（@pytest.mark.integration，真实 API）

每个 CLI 子命令同时提供集成测试，调用真实 API 验证端到端行为：
- `haoinvest market quote 600519` — 验证返回格式正确、价格在合理范围
- `haoinvest market history 600519 --start 2026-01-01 --end 2026-01-31` — 验证返回 K 线数据
- `haoinvest portfolio list` — 验证空持仓/有持仓两种情况
- 运行方式：`pytest -m integration tests/test_cli/`

保留现有 `tests/test_market/test_akshare_integration.py` 集成测试。

---

## 验证计划

1. `pytest` — 所有单元测试通过
2. `pytest -m integration` — 集成测试通过（需网络）
3. `uv run haoinvest market quote 600519` — 验证 A-share 报价
4. `uv run haoinvest portfolio list` — 验证持仓查看
5. 在 Claude Code 中调用 `/haoinvest` skill — 验证端到端流程

---

## 不在此次范围

以下问题已记录，后续处理：
- portfolio/manager.py + returns.py 交易处理逻辑重复
- analysis/fundamental.py PE/PB 范围判断重复
- crypto_provider.py 嵌套 dict.get() 简化
- 精度处理不一致（returns.py 硬编码 round(x, 2)）
- strategy/rebalance.py 隐式状态计算
