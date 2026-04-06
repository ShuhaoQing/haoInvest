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


# API timeout for A-share data sources (Sina/Tencent/eastmoney)
API_TIMEOUT = int(os.environ.get("HAOINVEST_API_TIMEOUT", "30"))

# Cache expiry in seconds
ANALYSIS_CACHE_TTL = int(
    os.environ.get("HAOINVEST_CACHE_TTL", str(3600 * 4))
)  # 4 hours
PRICE_CACHE_TTL = int(os.environ.get("HAOINVEST_PRICE_CACHE_TTL", str(3600)))  # 1 hour

# Precision rules
PRECISION = {
    "a_share": {"price": 2, "quantity": 0},  # A-shares: 2 decimal price, integer shares
    "crypto": {"price": 8, "quantity": 8},
    "hk": {"price": 3, "quantity": 0},
    "us": {"price": 2, "quantity": 0},
}

ZERO_THRESHOLD = 1e-10  # Use abs(quantity) < ZERO_THRESHOLD instead of == 0

# Guardrails defaults (conservative for beginners)
GUARDRAILS_DEFAULTS = {
    "max_single_position_pct": 15.0,
    "max_sector_pct": 35.0,
    "max_total_positions": 8,
    "min_cash_reserve_pct": 10.0,
    "gain_review_threshold": 30.0,
    "loss_review_threshold": -10.0,
    "rapid_change_threshold": 10.0,
}

# Sector info cache TTL (7 days — sectors don't change often)
SECTOR_CACHE_TTL = 7 * 24 * 3600
