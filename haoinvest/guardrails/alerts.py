"""Threshold alert system — scan positions for P&L threshold violations."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from ..config import ZERO_THRESHOLD
from ..db import Database
from ..models import (
    AlertType,
    MarketType,
    PositionAlert,
    RecentPriceChange,
    ThesisStatus,
)
from .rules import load_config

logger = logging.getLogger(__name__)


def scan_alerts(
    db: Database,
    current_prices: dict[tuple[str, MarketType], float],
) -> list[PositionAlert]:
    """Scan all positions for threshold violations.

    Returns alerts for positions exceeding gain/loss/rapid-change thresholds.
    """
    config = load_config(db)
    positions = db.get_positions(include_zero=False)
    alerts: list[PositionAlert] = []

    for pos in positions:
        key = (pos.symbol, pos.market_type)
        price = current_prices.get(key)
        if price is None:
            continue

        if abs(pos.cached_avg_cost) < ZERO_THRESHOLD:
            continue

        # Unrealized P&L %
        pnl_pct = (price - pos.cached_avg_cost) / pos.cached_avg_cost * 100

        # Holding days
        txns = db.get_transactions(symbol=pos.symbol, market_type=pos.market_type)
        buy_txns = [t for t in txns if t.action.value == "buy"]
        holding_days = None
        if buy_txns:
            first_buy = min(t.executed_at for t in buy_txns)
            holding_days = (date.today() - first_buy.date()).days

        # Original thesis from journal
        original_thesis = _get_original_thesis(db, pos.symbol)

        # Gain review
        if pnl_pct > config.gain_review_threshold:
            alerts.append(
                PositionAlert(
                    symbol=pos.symbol,
                    alert_type=AlertType.GAIN_REVIEW,
                    current_pnl_pct=round(pnl_pct, 1),
                    threshold_pct=config.gain_review_threshold,
                    holding_days=holding_days,
                    original_thesis=original_thesis,
                    message=f"{pos.symbol} 浮盈 {pnl_pct:.1f}%，超过审查阈值 {config.gain_review_threshold}%",
                )
            )

        # Loss review
        if pnl_pct < config.loss_review_threshold:
            alerts.append(
                PositionAlert(
                    symbol=pos.symbol,
                    alert_type=AlertType.LOSS_REVIEW,
                    current_pnl_pct=round(pnl_pct, 1),
                    threshold_pct=config.loss_review_threshold,
                    holding_days=holding_days,
                    original_thesis=original_thesis,
                    message=f"{pos.symbol} 浮亏 {pnl_pct:.1f}%，超过审查阈值 {config.loss_review_threshold}%",
                )
            )

        # Rapid change (1-week)
        recent = get_recent_price_change(db, pos.symbol, pos.market_type)
        if recent.one_week_pct is not None:
            if abs(recent.one_week_pct) > config.rapid_change_threshold:
                direction = "涨" if recent.one_week_pct > 0 else "跌"
                alerts.append(
                    PositionAlert(
                        symbol=pos.symbol,
                        alert_type=AlertType.RAPID_CHANGE,
                        current_pnl_pct=round(pnl_pct, 1),
                        threshold_pct=config.rapid_change_threshold,
                        holding_days=holding_days,
                        original_thesis=original_thesis,
                        message=f"{pos.symbol} 近7天{direction}幅 {abs(recent.one_week_pct):.1f}%，超过快速波动阈值 {config.rapid_change_threshold}%",
                    )
                )

    # Thesis review alerts
    alerts.extend(_scan_thesis_review_alerts(db))

    return alerts


def _scan_thesis_review_alerts(db: Database) -> list[PositionAlert]:
    """Check for active theses that are overdue for review."""

    theses = db.get_theses(status=ThesisStatus.ACTIVE)
    alerts: list[PositionAlert] = []
    now = datetime.now()

    for thesis in theses:
        last_check = thesis.last_reviewed_at or thesis.created_at
        if last_check is None:
            continue

        days_since = (now - last_check).days
        if days_since > thesis.review_interval_days:
            alerts.append(
                PositionAlert(
                    symbol=thesis.symbol,
                    alert_type=AlertType.THESIS_REVIEW,
                    current_pnl_pct=0,
                    threshold_pct=0,
                    original_thesis=thesis.thesis_summary,
                    message=(
                        f"{thesis.symbol} 投资逻辑已 {days_since} 天未审查"
                        f"（间隔 {thesis.review_interval_days} 天），请审查是否仍然成立"
                    ),
                )
            )

    return alerts


def get_recent_price_change(
    db: Database,
    symbol: str,
    market_type: MarketType,
) -> RecentPriceChange:
    """Calculate 1-week and 1-month price change percentages.

    Returns None for periods with insufficient data.
    """
    today = date.today()
    # Get prices for the last 35 days to cover 1 month + weekends
    start = today - timedelta(days=35)
    bars = db.get_prices(symbol, market_type, start_date=start, end_date=today)

    if len(bars) < 2:
        return RecentPriceChange()

    latest_close = bars[-1].close
    if latest_close is None:
        return RecentPriceChange()

    one_week_pct = None
    one_month_pct = None

    # Find price ~7 days ago
    week_ago = today - timedelta(days=7)
    week_bar = _find_closest_bar(bars, week_ago)
    if week_bar and week_bar.close and abs(week_bar.close) > ZERO_THRESHOLD:
        one_week_pct = round((latest_close - week_bar.close) / week_bar.close * 100, 1)

    # Find price ~30 days ago
    month_ago = today - timedelta(days=30)
    month_bar = _find_closest_bar(bars, month_ago)
    if month_bar and month_bar.close and abs(month_bar.close) > ZERO_THRESHOLD:
        one_month_pct = round(
            (latest_close - month_bar.close) / month_bar.close * 100, 1
        )

    return RecentPriceChange(one_week_pct=one_week_pct, one_month_pct=one_month_pct)


def _find_closest_bar(bars: list, target_date: date):
    """Find the bar closest to (but not after) target_date."""
    candidates = [b for b in bars if b.trade_date <= target_date]
    return candidates[-1] if candidates else None


def _get_original_thesis(db: Database, symbol: str) -> str | None:
    """Find the original buy thesis — check investment_theses first, then journal."""
    # Prefer structured thesis
    theses = db.get_theses(symbol=symbol, status=ThesisStatus.ACTIVE)
    if theses:
        return theses[0].thesis_summary

    # Fallback to journal entries
    entries = db.get_journal_entries(symbol=symbol, limit=50)
    buy_entries = [
        e for e in entries if e.decision_type and e.decision_type.value == "buy"
    ]
    if buy_entries:
        # entries are ordered DESC, so last is earliest
        return buy_entries[-1].content
    return None
