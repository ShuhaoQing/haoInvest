"""Output formatters for CLI commands.

Three formats:
- Key-Value text: for single records (quote, basic info)
- TSV: for tabular data (holdings, price history)
- JSON: for complex nested data or when --json is used
"""

import json
import sys
from typing import Any


def kv_output(data: dict[str, Any]) -> None:
    """Print key-value pairs, one per line. Skips None values."""
    for key, value in data.items():
        if value is None:
            continue
        print(f"{key}: {value}")


def tsv_output(rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    """Print tab-separated table with header row.

    Args:
        rows: List of dicts with consistent keys.
        columns: Column names to include (and their order). If None, uses all keys.
    """
    if not rows:
        print("(empty)")
        return
    if columns is None:
        columns = list(rows[0].keys())
    print("\t".join(columns))
    for row in rows:
        print("\t".join(str(row.get(c, "")) for c in columns))


def json_output(data: Any) -> None:
    """Print JSON with Chinese characters preserved."""
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def error_output(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)
