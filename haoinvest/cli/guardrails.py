"""CLI commands for investment guardrails."""

from typing import Optional

import typer

from ..db import Database
from ..market import get_provider
from ..models import MarketType
from .formatters import error_output, json_output, kv_output
from .market import _detect_market_type

app = typer.Typer(help="Guardrails — position rules, alerts, trade review.")


def _init_db() -> Database:
    db = Database()
    db.init_schema()
    return db


def _fetch_current_prices(db: Database) -> dict[tuple[str, MarketType], float]:
    """Fetch current prices for all holdings."""
    positions = db.get_positions(include_zero=False)
    prices: dict[tuple[str, MarketType], float] = {}
    for pos in positions:
        try:
            provider = get_provider(pos.market_type)
            prices[(pos.symbol, pos.market_type)] = provider.get_current_price(
                pos.symbol
            )
        except Exception as e:
            error_output(f"Failed to get price for {pos.symbol}: {e}")
    return prices


@app.command("health-check")
def health_check_cmd(
    cash: float = typer.Option(0.0, "--cash", help="Current cash balance"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Check current portfolio against guardrail rules."""
    from ..guardrails.rules import health_check

    db = _init_db()
    prices = _fetch_current_prices(db)
    result = health_check(db, prices, cash_balance=cash)

    if use_json:
        json_output(result)
    else:
        if result.passed:
            print(f"✓ {result.summary}")
        else:
            print(f"✗ {result.summary}")
            for v in result.violations:
                severity_icon = "⚠" if v.severity.value == "warning" else "✗"
                print(f"  {severity_icon} [{v.rule_name}] {v.message}")


@app.command("alerts")
def alerts_cmd(
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Scan all positions for threshold violations."""
    from ..guardrails.alerts import scan_alerts

    db = _init_db()
    prices = _fetch_current_prices(db)
    alerts = scan_alerts(db, prices)

    if use_json:
        json_output(alerts)
    else:
        if not alerts:
            print("✓ 没有触发报警的持仓")
            return
        for a in alerts:
            icon = {"gain_review": "📈", "loss_review": "📉", "rapid_change": "⚡"}.get(
                a.alert_type.value, "!"
            )
            print(f"  {icon} {a.message}")
            if a.holding_days is not None:
                print(f"    持有天数: {a.holding_days}")
            if a.original_thesis:
                print(f"    原始买入理由: {a.original_thesis[:80]}")


@app.command("config")
def config_cmd(
    set_value: Optional[str] = typer.Option(
        None, "--set", help="Set config: KEY=VALUE"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View or set guardrail configuration."""
    from ..guardrails.rules import load_config

    db = _init_db()

    if set_value:
        if "=" not in set_value:
            error_output("Format: --set KEY=VALUE")
            raise typer.Exit(1)
        key, value = set_value.split("=", 1)
        db.set_guardrails_config(key.strip(), value.strip())
        print(f"✓ {key.strip()} = {value.strip()}")
        return

    config = load_config(db)
    if use_json:
        json_output(config)
    else:
        kv_output(config)


@app.command("pre-trade-data")
def pre_trade_data_cmd(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    action: str = typer.Argument(help="buy or sell"),
    quantity: float = typer.Argument(help="Number of units"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us, hk"
    ),
    price: Optional[float] = typer.Option(
        None, "--price", "-p", help="Price per unit (default: current market price)"
    ),
    cash: float = typer.Option(0.0, "--cash", help="Current cash balance"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Collect all data for agent pre-trade review (single call)."""
    from ..guardrails.pre_trade_data import collect_pre_trade_data

    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
    db = _init_db()

    # Get current price if not specified
    trade_price = price
    if trade_price is None:
        try:
            provider = get_provider(mt)
            trade_price = provider.get_current_price(symbol)
        except Exception as e:
            error_output(f"Failed to get price for {symbol}: {e}")
            raise typer.Exit(1)

    prices = _fetch_current_prices(db)
    prices[(symbol, mt)] = trade_price

    result = collect_pre_trade_data(
        db, symbol, mt, action, quantity, trade_price, prices, cash_balance=cash
    )

    if use_json:
        json_output(result)
    else:
        # Text summary for human readers
        print(f"Pre-Trade Data: {action.upper()} {quantity} x {symbol} @ {trade_price}")
        print()
        if result.simulated_violations:
            print("⚠ 规则违规:")
            for v in result.simulated_violations:
                print(f"  - {v.message}")
        else:
            print("✓ 无规则违规")
        print()
        if result.current_position:
            cp = result.current_position
            print(f"当前持仓: {cp.quantity} 股, 均价 {cp.avg_cost}, 浮盈 {cp.unrealized_pnl_pct}%")
        else:
            print("当前无持仓")
        if result.recent_price_change.one_week_pct is not None:
            print(f"近期走势: 1周 {result.recent_price_change.one_week_pct:+.1f}%", end="")
            if result.recent_price_change.one_month_pct is not None:
                print(f", 1月 {result.recent_price_change.one_month_pct:+.1f}%")
            else:
                print()
