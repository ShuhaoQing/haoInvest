---
name: journal
description: "Investment journal — record thoughts with structured tags (decision type, emotion, related symbols), review past decisions, AI-powered decision pattern analysis and retrospective. Use when the user wants to log investment thinking or review past decisions."
user_invocable: true
---

# /journal — Investment Journal

Manage structured investment journal entries and provide AI-powered retrospective analysis.

## Setup

Run all Python code via `uv run python -c "..."` from the project root `/Users/shuhaoqing/repo/haoInvest`.

```python
from haoinvest.db import Database
from haoinvest.journal import JournalManager
from haoinvest.models import DecisionType, Emotion

db = Database()
db.init_schema()
jm = JournalManager(db)
```

## Commands

### Record Entry
Ask the user to describe their thought. Then help them tag it:
- **Decision type**: buy / sell / hold / watch / reflection
- **Emotion**: rational / greedy / fearful / fomo / uncertain / confident / regretful
- **Related symbols**: which stocks/crypto this relates to

```python
jm.create_entry(
    content="用户的想法内容",
    decision_type=DecisionType.BUY,
    emotion=Emotion.RATIONAL,
    related_symbols=["600519"],
)
```

If the user doesn't specify emotion or decision type, ask them gently — these tags are what makes the retrospective analysis valuable.

### View Past Entries
```python
entries = jm.get_entries(limit=10)  # Recent entries
entries = jm.get_entries(symbol="600519")  # Entries about a specific stock
```

### Add Retrospective
For entries that were buy/sell decisions, help the user add a retrospective:
```python
jm.add_retrospective(entry_id=1, retrospective="事后看这个决策是正确的，股价确实涨了20%")
```

### Decision Pattern Analysis
```python
stats = jm.get_decision_stats(days=90)
```

Display:
- Decision type distribution (how many buys vs sells vs holds)
- Emotion distribution (how often rational vs emotional)
- Entries that need retrospective review

Then provide AI analysis of patterns:
- "你过去3个月做了8次买入决策，其中5次标记为'理性'，但3次标记为'FOMO'。FOMO驱动的决策结果如何？"
- Identify behavioral biases: chasing highs, panic selling, overtrading

### AI Retrospective
For a specific entry:
```python
context = jm.prepare_retrospective_context(entry_id=1)
```

Use the context (entry details + related transactions) to provide an honest, constructive review:
- Was the reasoning sound?
- Did the outcome match expectations?
- What could be improved?

## Response Format
- Always respond in Chinese
- Be encouraging but honest in retrospective reviews
- Frame feedback as learning opportunities, not criticism
- Use the user's actual data to make points concrete
- When showing entries, include emotion tags — they're important for self-awareness
