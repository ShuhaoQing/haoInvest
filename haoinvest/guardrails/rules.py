"""Position rules engine — health check and pre-trade validation.

All checks are advisory (never block trades). Allocation is computed
from market value, not cost basis.
"""

from __future__ import annotations

import logging

from ..config import GUARDRAILS_DEFAULTS, SECTOR_CACHE_TTL
from ..db import Database
from ..models import (
    GuardrailsConfig,
    HealthCheckResult,
    MarketType,
    RuleViolation,
    Severity,
)

logger = logging.getLogger(__name__)


def load_config(db: Database) -> GuardrailsConfig:
    """Load guardrails config from DB, falling back to defaults."""
    stored = db.get_guardrails_config()
    merged = dict(GUARDRAILS_DEFAULTS)
    for key, value in stored.items():
        if key in merged:
            target_type = type(merged[key])
            try:
                merged[key] = target_type(value)
            except (ValueError, TypeError):
                logger.warning("Invalid guardrails config: %s=%s", key, value)
    return GuardrailsConfig(**merged)


def _get_sector_for_symbol(
    db: Database, symbol: str, market_type: MarketType
) -> str | None:
    """Get sector for a symbol, using analysis_cache with 7-day TTL."""
    cache_key = f"sector_{market_type.value}"
    cached = db.get_cached_analysis(symbol, cache_key)
    if cached and "sector" in cached:
        return cached["sector"]

    try:
        from ..market import get_provider

        provider = get_provider(market_type)
        info = provider.get_basic_info(symbol)
        if info and info.sector:
            db.save_analysis(
                symbol, cache_key, {"sector": info.sector}, ttl_seconds=SECTOR_CACHE_TTL
            )
            return info.sector
    except Exception:
        logger.debug("Failed to fetch sector for %s", symbol, exc_info=True)

    return None


def health_check(
    db: Database,
    current_prices: dict[tuple[str, MarketType], float],
    cash_balance: float = 0.0,
) -> HealthCheckResult:
    """Check current portfolio against all guardrail rules.

    Args:
        current_prices: (symbol, MarketType) -> current price
        cash_balance: available cash (0 = skip cash reserve check)
    """
    config = load_config(db)
    positions = db.get_positions(include_zero=False)

    if not positions:
        return HealthCheckResult(passed=True, summary="暂无持仓")

    violations: list[RuleViolation] = []

    # Compute market values
    position_values: dict[str, float] = {}
    for pos in positions:
        key = (pos.symbol, pos.market_type)
        price = current_prices.get(key, pos.cached_avg_cost)
        position_values[pos.symbol] = pos.cached_quantity * price

    total_market_value = sum(position_values.values())

    if total_market_value <= 0:
        return HealthCheckResult(passed=True, summary="总市值为零")

    # Rule 1: max_single_position_pct
    for pos in positions:
        pct = position_values[pos.symbol] / total_market_value * 100
        if pct > config.max_single_position_pct:
            violations.append(
                RuleViolation(
                    rule_name="max_single_position_pct",
                    severity=Severity.WARNING
                    if pct <= config.max_single_position_pct * 1.5
                    else Severity.CRITICAL,
                    current_value=round(pct, 1),
                    limit_value=config.max_single_position_pct,
                    message=f"{pos.symbol} 占总仓位 {pct:.1f}%，超过上限 {config.max_single_position_pct}%",
                    affected_symbols=[pos.symbol],
                )
            )

    # Rule 2: max_sector_pct
    sector_values: dict[str, float] = {}
    sector_symbols: dict[str, list[str]] = {}
    for pos in positions:
        sector = _get_sector_for_symbol(db, pos.symbol, pos.market_type)
        if sector:
            sector_values[sector] = sector_values.get(sector, 0) + position_values[pos.symbol]
            sector_symbols.setdefault(sector, []).append(pos.symbol)

    for sector, value in sector_values.items():
        pct = value / total_market_value * 100
        if pct > config.max_sector_pct:
            violations.append(
                RuleViolation(
                    rule_name="max_sector_pct",
                    severity=Severity.WARNING,
                    current_value=round(pct, 1),
                    limit_value=config.max_sector_pct,
                    message=f"行业「{sector}」占总仓位 {pct:.1f}%，超过上限 {config.max_sector_pct}%",
                    affected_symbols=sector_symbols.get(sector, []),
                )
            )

    # Rule 3: max_total_positions
    num_positions = len(positions)
    if num_positions > config.max_total_positions:
        violations.append(
            RuleViolation(
                rule_name="max_total_positions",
                severity=Severity.WARNING,
                current_value=float(num_positions),
                limit_value=float(config.max_total_positions),
                message=f"当前持有 {num_positions} 只标的，超过上限 {config.max_total_positions} 只",
            )
        )

    # Rule 4: min_cash_reserve_pct (only when cash > 0)
    if cash_balance > 0:
        total_with_cash = total_market_value + cash_balance
        cash_pct = cash_balance / total_with_cash * 100
        if cash_pct < config.min_cash_reserve_pct:
            violations.append(
                RuleViolation(
                    rule_name="min_cash_reserve_pct",
                    severity=Severity.WARNING,
                    current_value=round(cash_pct, 1),
                    limit_value=config.min_cash_reserve_pct,
                    message=f"现金储备 {cash_pct:.1f}%，低于最低要求 {config.min_cash_reserve_pct}%",
                )
            )

    passed = len(violations) == 0
    summary = "所有规则通过" if passed else f"发现 {len(violations)} 条违规"

    return HealthCheckResult(violations=violations, passed=passed, summary=summary)


def validate_trade(
    db: Database,
    symbol: str,
    market_type: MarketType,
    action: str,
    quantity: float,
    price: float,
    current_prices: dict[tuple[str, MarketType], float],
    cash_balance: float = 0.0,
) -> list[RuleViolation]:
    """Simulate a trade and return all rule violations after the trade.

    Returns violations for the post-trade state. The agent can compare
    with current health_check() to see what changed.
    """
    config = load_config(db)
    positions = db.get_positions(include_zero=False)

    # Build position values including the simulated trade
    position_values: dict[str, float] = {}
    for pos in positions:
        key = (pos.symbol, pos.market_type)
        p = current_prices.get(key, pos.cached_avg_cost)
        qty = pos.cached_quantity
        if pos.symbol == symbol and pos.market_type == market_type:
            if action.lower() == "buy":
                qty += quantity
            elif action.lower() == "sell":
                qty = max(0, qty - quantity)
        position_values[pos.symbol] = qty * p

    # Handle new position (not yet in portfolio)
    if symbol not in position_values and action.lower() == "buy":
        position_values[symbol] = quantity * price

    total_market_value = sum(position_values.values())
    if total_market_value <= 0:
        return []

    violations: list[RuleViolation] = []

    # Check single position limit after trade
    if symbol in position_values:
        pct = position_values[symbol] / total_market_value * 100
        if pct > config.max_single_position_pct:
            violations.append(
                RuleViolation(
                    rule_name="max_single_position_pct",
                    severity=Severity.WARNING
                    if pct <= config.max_single_position_pct * 1.5
                    else Severity.CRITICAL,
                    current_value=round(pct, 1),
                    limit_value=config.max_single_position_pct,
                    message=f"{'买入' if action.lower() == 'buy' else '卖出'}后 {symbol} 将占总仓位 {pct:.1f}%，超过上限 {config.max_single_position_pct}%",
                    affected_symbols=[symbol],
                )
            )

    # Check sector limit after trade
    sector = _get_sector_for_symbol(db, symbol, market_type)
    if sector:
        sector_total = 0.0
        for pos in positions:
            pos_sector = _get_sector_for_symbol(db, pos.symbol, pos.market_type)
            if pos_sector == sector:
                sector_total += position_values.get(pos.symbol, 0)
        # Include the new symbol if not already in positions
        if symbol not in {p.symbol for p in positions}:
            sector_total += position_values.get(symbol, 0)

        sector_pct = sector_total / total_market_value * 100
        if sector_pct > config.max_sector_pct:
            violations.append(
                RuleViolation(
                    rule_name="max_sector_pct",
                    severity=Severity.WARNING,
                    current_value=round(sector_pct, 1),
                    limit_value=config.max_sector_pct,
                    message=f"交易后行业「{sector}」将占总仓位 {sector_pct:.1f}%，超过上限 {config.max_sector_pct}%",
                    affected_symbols=[symbol],
                )
            )

    # Check total positions after trade (only for new buys)
    if action.lower() == "buy":
        existing = {(p.symbol, p.market_type) for p in positions}
        if (symbol, market_type) not in existing:
            new_count = len(positions) + 1
            if new_count > config.max_total_positions:
                violations.append(
                    RuleViolation(
                        rule_name="max_total_positions",
                        severity=Severity.WARNING,
                        current_value=float(new_count),
                        limit_value=float(config.max_total_positions),
                        message=f"买入后将持有 {new_count} 只标的，超过上限 {config.max_total_positions} 只",
                    )
                )

    # Check cash reserve after trade (only for buys with cash > 0)
    if action.lower() == "buy" and cash_balance > 0:
        trade_cost = quantity * price
        new_cash = cash_balance - trade_cost
        if new_cash >= 0:
            total_with_cash = total_market_value + new_cash
            cash_pct = new_cash / total_with_cash * 100
            if cash_pct < config.min_cash_reserve_pct:
                violations.append(
                    RuleViolation(
                        rule_name="min_cash_reserve_pct",
                        severity=Severity.WARNING,
                        current_value=round(cash_pct, 1),
                        limit_value=config.min_cash_reserve_pct,
                        message=f"买入后现金储备将降至 {cash_pct:.1f}%，低于最低要求 {config.min_cash_reserve_pct}%",
                    )
                )

    return violations
