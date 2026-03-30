"""Centralized configuration management."""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Return the data directory (~/.haoinvest/), creating it if needed."""
    data_dir = Path(os.environ.get("HAOINVEST_DATA_DIR", Path.home() / ".haoinvest"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Return the SQLite database path."""
    return get_data_dir() / "haoinvest.db"


# AKShare has unstable APIs — pin version in pyproject.toml
# and handle errors gracefully in providers.
AKSHARE_TIMEOUT = int(os.environ.get("HAOINVEST_AKSHARE_TIMEOUT", "30"))

# Cache expiry in seconds
ANALYSIS_CACHE_TTL = int(os.environ.get("HAOINVEST_CACHE_TTL", str(3600 * 4)))  # 4 hours
PRICE_CACHE_TTL = int(os.environ.get("HAOINVEST_PRICE_CACHE_TTL", str(3600)))  # 1 hour

# Precision rules
PRECISION = {
    "a_share": {"price": 2, "quantity": 0},  # A-shares: 2 decimal price, integer shares
    "crypto": {"price": 8, "quantity": 8},
    "hk": {"price": 3, "quantity": 0},
    "us": {"price": 2, "quantity": 0},
}

ZERO_THRESHOLD = 1e-10  # Use abs(quantity) < ZERO_THRESHOLD instead of == 0
