"""Investment journal management: CRUD, symbol tags, AI retrospective helper."""

from datetime import datetime, timedelta
from typing import Optional

from .db import Database
from .models import DecisionType, Emotion, JournalEntry


class JournalManager:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create_entry(
        self,
        content: str,
        decision_type: Optional[DecisionType] = None,
        emotion: Optional[Emotion] = None,
        related_symbols: Optional[list[str]] = None,
    ) -> int:
        """Create a new journal entry."""
        entry = JournalEntry(
            content=content,
            decision_type=decision_type,
            emotion=emotion,
            related_symbols=related_symbols or [],
        )
        return self.db.add_journal_entry(entry)

    def get_entries(
        self,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> list[JournalEntry]:
        """Get journal entries, optionally filtered by symbol."""
        return self.db.get_journal_entries(symbol=symbol, limit=limit)

    def add_retrospective(self, entry_id: int, retrospective: str) -> None:
        """Add a retrospective note to an existing journal entry."""
        self.db.update_journal_retrospective(entry_id, retrospective)

    def get_decision_stats(self, days: int = 90) -> dict:
        """Analyze decision patterns over the past N days.

        Returns stats useful for AI retrospective: decision type distribution,
        emotion distribution, and entries ready for retrospective review.
        """
        entries = self.db.get_journal_entries(limit=500)
        cutoff = datetime.now() - timedelta(days=days)

        recent = [e for e in entries if e.created_at and e.created_at >= cutoff]

        # Decision type distribution
        decision_counts: dict[str, int] = {}
        for e in recent:
            key = e.decision_type.value if e.decision_type else "unspecified"
            decision_counts[key] = decision_counts.get(key, 0) + 1

        # Emotion distribution
        emotion_counts: dict[str, int] = {}
        for e in recent:
            key = e.emotion.value if e.emotion else "unspecified"
            emotion_counts[key] = emotion_counts.get(key, 0) + 1

        # Entries without retrospective (candidates for review)
        needs_review = [
            {
                "id": e.id,
                "content": e.content[:100],
                "decision_type": e.decision_type.value if e.decision_type else None,
                "emotion": e.emotion.value if e.emotion else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in recent
            if e.retrospective is None
            and e.decision_type in (DecisionType.BUY, DecisionType.SELL)
        ]

        return {
            "period_days": days,
            "total_entries": len(recent),
            "decision_distribution": decision_counts,
            "emotion_distribution": emotion_counts,
            "needs_retrospective": needs_review,
        }

    def prepare_retrospective_context(self, entry_id: int) -> dict | None:
        """Prepare context for AI-powered retrospective of a specific entry.

        Returns the entry details plus related transactions if any symbols
        are tagged, so the AI can assess whether the decision was good.
        """
        entries = self.db.get_journal_entries(limit=500)
        entry = next((e for e in entries if e.id == entry_id), None)
        if entry is None:
            return None

        context: dict = {
            "entry": {
                "id": entry.id,
                "content": entry.content,
                "decision_type": entry.decision_type.value
                if entry.decision_type
                else None,
                "emotion": entry.emotion.value if entry.emotion else None,
                "related_symbols": entry.related_symbols,
                "created_at": entry.created_at.isoformat()
                if entry.created_at
                else None,
                "existing_retrospective": entry.retrospective,
            },
            "related_transactions": [],
        }

        # Fetch transactions for related symbols
        for symbol in entry.related_symbols:
            txns = self.db.get_transactions(symbol=symbol)
            for t in txns:
                context["related_transactions"].append(
                    {
                        "symbol": t.symbol,
                        "action": t.action.value,
                        "quantity": t.quantity,
                        "price": t.price,
                        "executed_at": t.executed_at.isoformat(),
                    }
                )

        return context
