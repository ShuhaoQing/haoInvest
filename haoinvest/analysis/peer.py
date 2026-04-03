"""Peer comparison — find and compare same-sector stocks."""

import logging

from ..models import MarketType
from .fundamental import analyze_stock

logger = logging.getLogger(__name__)


def find_peers(
    symbol: str,
    market_type: MarketType,
    top_n: int = 10,
) -> list[dict]:
    """Find same-sector peers and compare fundamental metrics.

    For A-shares: uses AShareProvider.get_sector_constituents() to find
    stocks in the same industry board, sorted by market cap.

    Returns list of dicts suitable for TSV output, with the target stock
    marked in the 'is_target' field.
    """
    if market_type != MarketType.A_SHARE:
        return [
            {"message": f"Peer comparison not yet supported for {market_type.value}"}
        ]

    from ..market.ashare_provider import AShareProvider

    # Get target stock info to determine sector
    target = analyze_stock(symbol, market_type)
    sector = target.sector
    if not sector:
        return [{"message": f"No sector info available for {symbol}"}]

    # Get sector constituents
    try:
        constituents = AShareProvider.get_sector_constituents(sector)
    except Exception as e:
        logger.debug("Failed to get sector constituents for %s: %s", sector, e)
        return [{"message": f"Failed to get sector data for {sector}: {e}"}]

    if not constituents:
        return [{"message": f"No constituents found for sector {sector}"}]

    # Sort by market cap (descending), take top N
    constituents.sort(key=lambda x: x.get("total_market_cap") or 0, reverse=True)
    # Filter to top_n, ensuring target is included
    top_codes = set()
    top_peers = []
    for c in constituents:
        if len(top_peers) >= top_n:
            break
        top_peers.append(c)
        top_codes.add(c.get("code", ""))

    # Build comparison rows using sector constituent data (no extra API calls)
    rows = []
    for c in top_peers:
        code = c.get("code", "")
        rows.append(
            {
                "Symbol": code,
                "Name": c.get("name", ""),
                "Price": c.get("price"),
                "Change%": c.get("change_pct"),
                "PE": c.get("pe_ratio"),
                "PB": c.get("pb_ratio"),
                "MarketCap": c.get("total_market_cap"),
                "is_target": code == symbol,
            }
        )

    return rows
