"""CLI commands for investment journal."""

from typing import Optional

import typer

from ..db import Database
from ..journal import JournalManager
from ..models import DecisionType, Emotion
from .formatters import error_output, json_output, kv_output, tsv_output

app = typer.Typer(help="Journal — record decisions, review patterns.")


def _init_db() -> Database:
    db = Database()
    db.init_schema()
    return db


@app.command()
def add(
    content: str = typer.Argument(help="Journal entry content"),
    decision_type: Optional[str] = typer.Option(
        None, "--decision", "-d", help="buy, sell, hold, watch, reflection"
    ),
    emotion: Optional[str] = typer.Option(
        None,
        "--emotion",
        "-e",
        help="rational, greedy, fearful, fomo, uncertain, confident, regretful",
    ),
    symbols: Optional[str] = typer.Option(
        None, "--symbols", "-s", help="Comma-separated related symbols"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Add a new journal entry."""
    dt = DecisionType(decision_type) if decision_type else None
    em = Emotion(emotion) if emotion else None
    related = [s.strip() for s in symbols.split(",")] if symbols else []

    db = _init_db()
    jm = JournalManager(db)
    entry_id = jm.create_entry(
        content, decision_type=dt, emotion=em, related_symbols=related
    )

    result = {"entry_id": entry_id, "content": content[:80]}
    if use_json:
        json_output(result)
    else:
        kv_output(result)


@app.command("list")
def list_entries(
    symbol: Optional[str] = typer.Option(
        None, "--symbol", "-s", help="Filter by related symbol"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max entries to return"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View recent journal entries."""
    db = _init_db()
    jm = JournalManager(db)
    entries = jm.get_entries(symbol=symbol, limit=limit)

    if not entries:
        print("(no entries)")
        return

    rows = []
    for e in entries:
        rows.append(
            {
                "ID": e.id,
                "Date": e.created_at.strftime("%Y-%m-%d") if e.created_at else "",
                "Decision": e.decision_type.value if e.decision_type else "",
                "Emotion": e.emotion.value if e.emotion else "",
                "Symbols": ",".join(e.related_symbols) if e.related_symbols else "",
                "Content": e.content[:60],
            }
        )

    if use_json:
        json_output(rows)
    else:
        tsv_output(
            rows, columns=["ID", "Date", "Decision", "Emotion", "Symbols", "Content"]
        )


@app.command()
def review(
    entry_id: Optional[int] = typer.Option(
        None, "--entry-id", "-i", help="Specific entry ID for retrospective context"
    ),
    days: int = typer.Option(90, "--days", help="Stats window in days"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get decision stats or retrospective context for AI analysis."""
    db = _init_db()
    jm = JournalManager(db)

    if entry_id is not None:
        context = jm.prepare_retrospective_context(entry_id)
        if context is None:
            error_output(f"Entry {entry_id} not found")
            raise typer.Exit(1)
        # Always JSON for complex nested data
        json_output(context)
    else:
        stats = jm.get_decision_stats(days=days)
        if use_json:
            json_output(stats)
        else:
            kv_output(
                {
                    "Period": f"{stats['period_days']} days",
                    "TotalEntries": stats["total_entries"],
                    "Decisions": stats["decision_distribution"],
                    "Emotions": stats["emotion_distribution"],
                    "NeedsRetrospective": len(stats["needs_retrospective"]),
                }
            )
