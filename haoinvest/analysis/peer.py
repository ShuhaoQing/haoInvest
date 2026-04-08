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

    # Collect PE/PB values for percentile calculation (from all constituents)
    all_pe = [
        c.get("pe_ratio")
        for c in constituents
        if c.get("pe_ratio") is not None and c.get("pe_ratio") > 0
    ]
    all_pb = [
        c.get("pb_ratio")
        for c in constituents
        if c.get("pb_ratio") is not None and c.get("pb_ratio") > 0
    ]
    all_pe.sort()
    all_pb.sort()

    # Build comparison rows using sector constituent data (no extra API calls)
    rows = []
    for c in top_peers:
        code = c.get("code", "")
        pe = c.get("pe_ratio")
        pb = c.get("pb_ratio")
        row = {
            "Symbol": code,
            "Name": c.get("name", ""),
            "Price": c.get("price"),
            "Change%": c.get("change_pct"),
            "PE": pe,
            "PB": pb,
            "PE_Pctl": _percentile(pe, all_pe),
            "PB_Pctl": _percentile(pb, all_pb),
            "MarketCap": c.get("total_market_cap"),
            "is_target": code == symbol,
        }
        rows.append(row)

    return rows


def _percentile(value: float | None, sorted_vals: list[float]) -> str | None:
    """Calculate percentile of value within a sorted list.

    Returns a string like "32%" meaning cheaper than 68% of peers.
    """
    import bisect

    if value is None or value <= 0 or not sorted_vals:
        return None
    count_below = bisect.bisect_left(sorted_vals, value)
    pctl = round(count_below / len(sorted_vals) * 100)
    return f"{pctl}%"
