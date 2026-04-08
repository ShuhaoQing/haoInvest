"""Analysis report assembly — combines fundamental and risk data."""

from __future__ import annotations

from datetime import date

from ..db import Database
from ..models import (
    BuyReadinessChecklist,
    ChecklistItem,
    FundamentalAnalysis,
    MarketType,
    RiskMetrics,
    SignalSummary,
    StockReport,
)
from .fundamental import analyze_stock
from .risk import calculate_risk_metrics
from .signals import aggregate_signals
from .technical import analyze_technical
from .volume import analyze_volume


def full_stock_report(
    db: Database,
    symbol: str,
    market_type: MarketType,
    price_start: date | None = None,
    price_end: date | None = None,
    include_technical: bool = False,
) -> StockReport:
    """Generate a comprehensive analysis report for a single stock.

    Combines fundamental analysis with risk metrics from price history.
    When include_technical=True, also adds technical indicators, volume
    analysis, and aggregated signals.
    Results are cached in the database.
    """
    date_suffix = f"_{price_start}_{price_end}" if (price_start or price_end) else ""
    cache_key = (
        f"full_report_tech{date_suffix}"
        if include_technical
        else f"full_report{date_suffix}"
    )
    cached = db.get_cached_analysis(symbol, cache_key)
    if cached:
        return StockReport.model_validate(cached)

    fundamental = analyze_stock(symbol, market_type)
    risk = calculate_risk_metrics(db, symbol, market_type, price_start, price_end)

    report = StockReport(
        symbol=fundamental.symbol,
        name=fundamental.name,
        sector=fundamental.sector,
        industry=fundamental.industry,
        market_type=fundamental.market_type,
        current_price=fundamental.current_price,
        currency=fundamental.currency,
        pe_ratio=fundamental.pe_ratio,
        pb_ratio=fundamental.pb_ratio,
        total_market_cap=fundamental.total_market_cap,
        valuation=fundamental.valuation,
        risk_metrics=risk,
        roe=fundamental.roe,
        roa=fundamental.roa,
        debt_to_equity=fundamental.debt_to_equity,
        revenue_growth=fundamental.revenue_growth,
        profit_margin=fundamental.profit_margin,
        gross_margin=fundamental.gross_margin,
        operating_margin=fundamental.operating_margin,
        current_ratio=fundamental.current_ratio,
        free_cash_flow=fundamental.free_cash_flow,
        operating_cash_flow=fundamental.operating_cash_flow,
        peg_ratio=fundamental.peg_ratio,
        dividend_yield=fundamental.dividend_yield,
        eps=fundamental.eps,
        book_value_per_share=fundamental.book_value_per_share,
        operating_cash_flow_per_share=fundamental.operating_cash_flow_per_share,
        net_profit_growth=fundamental.net_profit_growth,
        revenue_growth_qoq=fundamental.revenue_growth_qoq,
        net_profit_growth_qoq=fundamental.net_profit_growth_qoq,
        report_date=fundamental.report_date,
        report_type=fundamental.report_type,
        financial_health=fundamental.financial_health,
    )

    if include_technical:
        report.technical = analyze_technical(
            db, symbol, market_type, price_start, price_end
        )
        report.volume = analyze_volume(db, symbol, market_type, price_start, price_end)
        report.signals = aggregate_signals(
            db, symbol, market_type, price_start, price_end
        )

    # Compute buy-readiness checklist
    report.checklist = _compute_checklist(report)

    # Cache the result
    db.save_analysis(symbol, cache_key, report.model_dump())

    return report


def compute_checklist_from_parts(
    fundamental: "FundamentalAnalysis",
    risk: "RiskMetrics",
    signals: "SignalSummary | None" = None,
) -> BuyReadinessChecklist:
    """Compute buy-readiness checklist from separate module results.

    Used by the composable `analyze run` command which doesn't build
    a full StockReport.
    """
    items: list[ChecklistItem] = []

    val_score = _score_valuation(fundamental.valuation.overall)
    items.append(
        ChecklistItem(
            dimension="估值", score=val_score, assessment=fundamental.valuation.overall
        )
    )

    prof_score = _score_profitability(fundamental.roe, fundamental.profit_margin)
    items.append(
        ChecklistItem(
            dimension="盈利能力",
            score=prof_score,
            assessment=fundamental.financial_health.profitability
            if fundamental.financial_health
            else "N/A",
        )
    )

    growth_score = _score_growth(fundamental.revenue_growth)
    items.append(
        ChecklistItem(
            dimension="成长性",
            score=growth_score,
            assessment=fundamental.financial_health.growth
            if fundamental.financial_health
            else "N/A",
        )
    )

    risk_score = _score_risk(risk.max_drawdown_pct, risk.sharpe_ratio)
    risk_text = (
        f"最大回撤 {risk.max_drawdown_pct:.1f}%" if risk.max_drawdown_pct else "N/A"
    )
    items.append(
        ChecklistItem(dimension="风险", score=risk_score, assessment=risk_text)
    )

    if signals:
        tech_score = _score_technical(signals.overall_signal, signals.confidence)
        tech_text = f"{signals.overall_signal} (置信度: {signals.confidence})"
    else:
        tech_score = 3
        tech_text = "无技术面数据"
    items.append(
        ChecklistItem(dimension="技术面", score=tech_score, assessment=tech_text)
    )

    total = sum(item.score for item in items)
    max_score = len(items) * 5

    if total >= max_score * 0.75:
        recommendation = "建议关注"
    elif total >= max_score * 0.5:
        recommendation = "谨慎观望"
    else:
        recommendation = "建议回避"

    return BuyReadinessChecklist(
        items=items,
        total_score=total,
        max_score=max_score,
        recommendation=recommendation,
    )


def _compute_checklist(report: StockReport) -> BuyReadinessChecklist:
    """Score each dimension 1-5 and produce a recommendation."""
    items: list[ChecklistItem] = []

    # 1. Valuation
    val_score = _score_valuation(report.valuation.overall)
    items.append(
        ChecklistItem(
            dimension="估值", score=val_score, assessment=report.valuation.overall
        )
    )

    # 2. Profitability
    prof_score = _score_profitability(report.roe, report.profit_margin)
    items.append(
        ChecklistItem(
            dimension="盈利能力",
            score=prof_score,
            assessment=report.financial_health.profitability
            if report.financial_health
            else "N/A",
        )
    )

    # 3. Growth
    growth_score = _score_growth(report.revenue_growth)
    items.append(
        ChecklistItem(
            dimension="成长性",
            score=growth_score,
            assessment=report.financial_health.growth
            if report.financial_health
            else "N/A",
        )
    )

    # 4. Risk
    risk_score = _score_risk(
        report.risk_metrics.max_drawdown_pct, report.risk_metrics.sharpe_ratio
    )
    risk_text = (
        f"最大回撤 {report.risk_metrics.max_drawdown_pct:.1f}%"
        if report.risk_metrics.max_drawdown_pct
        else "N/A"
    )
    items.append(
        ChecklistItem(dimension="风险", score=risk_score, assessment=risk_text)
    )

    # 5. Technical (if available)
    if report.signals:
        tech_score = _score_technical(
            report.signals.overall_signal, report.signals.confidence
        )
        tech_text = (
            f"{report.signals.overall_signal} (置信度: {report.signals.confidence})"
        )
    else:
        tech_score = 3  # neutral when no data
        tech_text = "无技术面数据"
    items.append(
        ChecklistItem(dimension="技术面", score=tech_score, assessment=tech_text)
    )

    total = sum(item.score for item in items)
    max_score = len(items) * 5

    if total >= max_score * 0.75:
        recommendation = "建议关注"
    elif total >= max_score * 0.5:
        recommendation = "谨慎观望"
    else:
        recommendation = "建议回避"

    return BuyReadinessChecklist(
        items=items,
        total_score=total,
        max_score=max_score,
        recommendation=recommendation,
    )


def _score_valuation(overall: str) -> int:
    mapping = {"偏低": 5, "中等": 4, "偏高": 2, "高": 1}
    return mapping.get(overall, 3)


def _score_profitability(roe: float | None, profit_margin: float | None) -> int:
    if roe is not None:
        if roe > 15:
            return 5
        elif roe > 10:
            return 4
        elif roe > 5:
            return 3
        else:
            return 2
    if profit_margin is not None:
        if profit_margin > 20:
            return 5
        elif profit_margin > 10:
            return 4
        elif profit_margin > 5:
            return 3
        else:
            return 2
    return 3  # neutral when no data


def _score_growth(revenue_growth: float | None) -> int:
    """Score growth (revenue_growth is percentage, e.g. 15.0 = 15%)."""
    if revenue_growth is None:
        return 3
    g = revenue_growth
    if g > 20:
        return 5
    elif g > 10:
        return 4
    elif g > 0:
        return 3
    else:
        return 2


def _score_risk(max_drawdown: float | None, sharpe: float | None) -> int:
    if max_drawdown is None and sharpe is None:
        return 3
    score = 3
    if max_drawdown is not None:
        if max_drawdown > -10:
            score = 5
        elif max_drawdown > -20:
            score = 4
        elif max_drawdown > -30:
            score = 3
        else:
            score = 2
    if sharpe is not None:
        if sharpe > 1.0:
            score = min(score + 1, 5)
        elif sharpe < 0:
            score = max(score - 1, 1)
    return score


def _score_technical(signal: str, confidence: str) -> int:
    if signal == "偏多" and confidence in ("高", "中"):
        return 5
    elif signal == "偏多":
        return 4
    elif signal == "中性":
        return 3
    elif signal == "偏空":
        return 2
    return 3
