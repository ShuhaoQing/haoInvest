"""Fundamental analysis: PE/PB/ROE and valuation assessment."""

from ..market import get_provider
from ..models import (
    BasicInfo,
    FinancialHealthAssessment,
    FundamentalAnalysis,
    MarketType,
    ValuationAssessment,
)


def analyze_stock(symbol: str, market_type: MarketType) -> FundamentalAnalysis:
    """Run fundamental analysis on a single stock."""
    provider = get_provider(market_type)

    price = provider.get_current_price(symbol)
    info = provider.get_basic_info(symbol)

    pe = _safe_float(info.pe_ratio)
    pb = _safe_float(info.pb_ratio)

    valuation = _assess_valuation(pe, pb, market_type)
    financial_health = _assess_financial_health(info)

    return FundamentalAnalysis(
        symbol=symbol,
        name=info.name,
        sector=info.sector,
        industry=info.industry,
        market_type=market_type.value,
        current_price=price,
        currency=info.currency,
        pe_ratio=pe,
        pb_ratio=pb,
        total_market_cap=info.total_market_cap,
        valuation=valuation,
        roe=info.roe,
        roa=info.roa,
        debt_to_equity=info.debt_to_equity,
        revenue_growth=info.revenue_growth,
        profit_margin=info.profit_margin,
        gross_margin=info.gross_margin,
        operating_margin=info.operating_margin,
        current_ratio=info.current_ratio,
        free_cash_flow=info.free_cash_flow,
        operating_cash_flow=info.operating_cash_flow,
        peg_ratio=info.peg_ratio,
        dividend_yield=info.dividend_yield,
        eps=info.eps,
        book_value_per_share=info.book_value_per_share,
        operating_cash_flow_per_share=info.operating_cash_flow_per_share,
        net_profit_growth=info.net_profit_growth,
        revenue_growth_qoq=info.revenue_growth_qoq,
        net_profit_growth_qoq=info.net_profit_growth_qoq,
        report_date=info.report_date,
        report_type=info.report_type,
        financial_health=financial_health,
    )


def _assess_valuation(
    pe: float | None, pb: float | None, market_type: MarketType
) -> ValuationAssessment:
    """Data-focused valuation summary.

    Shows PE/PB values with rough bucketing. Deep interpretation (industry-relative,
    growth-adjusted) should be done by Claude using valuation-guide.md reference.
    """
    pe_assessment = "N/A"
    pb_assessment = "N/A"
    overall = "无法评估"

    if pe is not None and pe > 0:
        pe_assessment = f"PE {pe:.1f}"

    if pb is not None and pb > 0:
        pb_assessment = f"PB {pb:.2f}"

    # Rough overall bucket — NOTE: this is a crude heuristic.
    # True valuation requires peer comparison (see valuation-guide.md).
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
            overall = "偏低"
        elif avg <= 2.5:
            overall = "中等"
        elif avg <= 3.5:
            overall = "偏高"
        else:
            overall = "高"

    return ValuationAssessment(
        pe_assessment=pe_assessment,
        pb_assessment=pb_assessment,
        overall=overall,
    )


def _assess_financial_health(info: BasicInfo) -> FinancialHealthAssessment:
    """Multi-dimensional financial health assessment with Chinese labels."""
    profitability = _assess_profitability(info.roe, info.profit_margin)
    growth = _assess_growth(info.revenue_growth)
    leverage = _assess_leverage(info.debt_to_equity, info.current_ratio)
    cash_flow = _assess_cash_flow(info.free_cash_flow, info.operating_cash_flow)

    # Overall: count how many dimensions are positive
    assessments = [profitability, growth, leverage, cash_flow]
    known = [a for a in assessments if a != "N/A"]
    if not known:
        overall = "无法评估"
    else:
        positive_keywords = (
            "优秀",
            "良好",
            "高速增长",
            "稳定增长",
            "保守",
            "适中",
            "充裕",
            "正常",
        )
        positive = sum(1 for a in known if any(k in a for k in positive_keywords))
        ratio = positive / len(known)
        if ratio >= 0.75:
            overall = "财务健康"
        elif ratio >= 0.5:
            overall = "财务一般"
        elif ratio >= 0.25:
            overall = "财务偏弱"
        else:
            overall = "财务风险较高"

    return FinancialHealthAssessment(
        profitability=profitability,
        growth=growth,
        leverage=leverage,
        cash_flow=cash_flow,
        overall=overall,
    )


def _assess_profitability(roe: float | None, profit_margin: float | None) -> str:
    """Assess profitability based on ROE and net profit margin."""
    if roe is None and profit_margin is None:
        return "N/A"
    # ROE is the primary indicator
    if roe is not None:
        if roe > 15:
            return f"优秀 (ROE {roe:.1f}%)"
        elif roe > 10:
            return f"良好 (ROE {roe:.1f}%)"
        elif roe > 5:
            return f"一般 (ROE {roe:.1f}%)"
        else:
            return f"偏弱 (ROE {roe:.1f}%)"
    # Fallback to profit margin
    if profit_margin is not None:
        if profit_margin > 20:
            return f"优秀 (净利率 {profit_margin:.1f}%)"
        elif profit_margin > 10:
            return f"良好 (净利率 {profit_margin:.1f}%)"
        elif profit_margin > 5:
            return f"一般 (净利率 {profit_margin:.1f}%)"
        else:
            return f"偏弱 (净利率 {profit_margin:.1f}%)"
    return "N/A"


def _assess_growth(revenue_growth: float | None) -> str:
    """Assess growth based on YoY revenue growth (percentage, e.g. 15.0 = 15%)."""
    if revenue_growth is None:
        return "N/A"
    g = revenue_growth
    if g > 20:
        return f"高速增长 ({g:.1f}%)"
    elif g > 10:
        return f"稳定增长 ({g:.1f}%)"
    elif g > 0:
        return f"低增长 ({g:.1f}%)"
    else:
        return f"负增长 ({g:.1f}%)"


def _assess_leverage(debt_to_equity: float | None, current_ratio: float | None) -> str:
    """Assess leverage based on debt-to-equity and current ratio."""
    if debt_to_equity is None and current_ratio is None:
        return "N/A"
    parts = []
    if debt_to_equity is not None:
        if debt_to_equity < 50:
            parts.append(f"保守 (D/E {debt_to_equity:.0f}%)")
        elif debt_to_equity < 100:
            parts.append(f"适中 (D/E {debt_to_equity:.0f}%)")
        elif debt_to_equity < 200:
            parts.append(f"偏高 (D/E {debt_to_equity:.0f}%)")
        else:
            parts.append(f"高杠杆 (D/E {debt_to_equity:.0f}%)")
    if current_ratio is not None:
        if current_ratio >= 2:
            parts.append(f"流动性充足 (CR {current_ratio:.1f})")
        elif current_ratio >= 1:
            parts.append(f"流动性正常 (CR {current_ratio:.1f})")
        else:
            parts.append(f"流动性紧张 (CR {current_ratio:.1f})")
    return "; ".join(parts) if parts else "N/A"


def _assess_cash_flow(
    free_cash_flow: float | None, operating_cash_flow: float | None
) -> str:
    """Assess cash flow health."""
    if free_cash_flow is None and operating_cash_flow is None:
        return "N/A"
    if free_cash_flow is not None:
        if free_cash_flow > 0:
            return "充裕 (自由现金流为正)"
        else:
            return "紧张 (自由现金流为负)"
    if operating_cash_flow is not None:
        if operating_cash_flow > 0:
            return "正常 (经营现金流为正)"
        else:
            return "紧张 (经营现金流为负)"
    return "N/A"


def _safe_float(val) -> float | None:
    """Convert a value to float, returning None if not possible."""
    if val is None or val == "":
        return None
    try:
        result = float(val)
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None
