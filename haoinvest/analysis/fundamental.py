"""Fundamental analysis: PE/PB/ROE and valuation assessment."""

from ..market import get_provider
from ..models import FundamentalAnalysis, MarketType, ValuationAssessment


def analyze_stock(symbol: str, market_type: MarketType) -> FundamentalAnalysis:
    """Run fundamental analysis on a single stock."""
    provider = get_provider(market_type)

    price = provider.get_current_price(symbol)
    info = provider.get_basic_info(symbol)

    pe = _safe_float(info.pe_ratio)
    pb = _safe_float(info.pb_ratio)

    valuation = _assess_valuation(pe, pb, market_type)

    return FundamentalAnalysis(
        symbol=symbol,
        name=info.name,
        sector=info.sector,
        market_type=market_type.value,
        current_price=price,
        currency=info.currency,
        pe_ratio=pe,
        pb_ratio=pb,
        total_market_cap=info.total_market_cap,
        valuation=valuation,
    )


def _assess_valuation(
    pe: float | None, pb: float | None, market_type: MarketType
) -> ValuationAssessment:
    """Simple valuation assessment based on PE and PB ratios.

    This is a rough heuristic for educational purposes, not financial advice.
    """
    pe_assessment = "N/A"
    pb_assessment = "N/A"
    overall = "无法评估"

    if pe is not None and pe > 0:
        if pe < 15:
            pe_assessment = "低估 (PE < 15)"
        elif pe < 25:
            pe_assessment = "合理 (15 ≤ PE < 25)"
        elif pe < 40:
            pe_assessment = "偏高 (25 ≤ PE < 40)"
        else:
            pe_assessment = "高估 (PE ≥ 40)"

    if pb is not None and pb > 0:
        if pb < 1:
            pb_assessment = "低估 (PB < 1)"
        elif pb < 3:
            pb_assessment = "合理 (1 ≤ PB < 3)"
        elif pb < 6:
            pb_assessment = "偏高 (3 ≤ PB < 6)"
        else:
            pb_assessment = "高估 (PB ≥ 6)"

    # Simple overall
    scores = []
    if pe is not None and pe > 0:
        if pe < 15:
            scores.append(1)
        elif pe < 25:
            scores.append(2)
        elif pe < 40:
            scores.append(3)
        else:
            scores.append(4)

    if pb is not None and pb > 0:
        if pb < 1:
            scores.append(1)
        elif pb < 3:
            scores.append(2)
        elif pb < 6:
            scores.append(3)
        else:
            scores.append(4)

    if scores:
        avg = sum(scores) / len(scores)
        if avg <= 1.5:
            overall = "偏低估"
        elif avg <= 2.5:
            overall = "估值合理"
        elif avg <= 3.5:
            overall = "偏高估"
        else:
            overall = "明显高估"

    return ValuationAssessment(
        pe_assessment=pe_assessment,
        pb_assessment=pb_assessment,
        overall=overall,
    )


def _safe_float(val) -> float | None:
    """Convert a value to float, returning None if not possible."""
    if val is None or val == "":
        return None
    try:
        result = float(val)
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None
