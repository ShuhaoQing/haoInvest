"""CLI commands for portfolio management."""

import json
from datetime import date, datetime
from typing import Optional

import typer

from ..market import get_provider
from ..models import (
    InvestmentThesis,
    MarketType,
    ThesisStatus,
    Transaction,
    TransactionAction,
)
from ..portfolio.manager import PortfolioManager
from ..portfolio.returns import portfolio_returns_summary, realized_pnl, unrealized_pnl
from ._shared import init_db
from .formatters import error_output, json_output, kv_output, tsv_output
from .market import _detect_market_type

app = typer.Typer(help="Portfolio — holdings, trades, returns.")
thesis_app = typer.Typer(help="Investment thesis — record and review buy rationale.")
app.add_typer(thesis_app, name="thesis")


@app.command("list")
def list_holdings(
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View all current holdings."""
    db = init_db()
    pm = PortfolioManager(db)
    summary = pm.get_portfolio_summary()

    if not summary:
        print("(no holdings)")
        return

    if use_json:
        json_output(summary)
    else:
        tsv_output(
            summary,
            columns=[
                "symbol",
                "market_type",
                "quantity",
                "avg_cost",
                "position_cost",
                "allocation_pct",
                "currency",
            ],
        )


@app.command("add-trade")
def add_trade(
    symbol: str = typer.Argument(help="Stock/crypto symbol"),
    action: str = typer.Argument(
        help="buy, sell, dividend, split, transfer_in, transfer_out"
    ),
    quantity: float = typer.Argument(help="Number of units"),
    price: float = typer.Argument(help="Price per unit"),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    fee: float = typer.Option(0.0, "--fee", help="Commission/fee"),
    tax: float = typer.Option(0.0, "--tax", help="Stamp tax"),
    date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Date YYYY-MM-DD (default: now)"
    ),
    currency: str = typer.Option("CNY", "--currency", help="Currency code"),
    note: str = typer.Option("", "--note", "-n", help="Trade note"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Record a trade transaction."""
    mt = MarketType(market_type) if market_type else _detect_market_type(symbol)

    try:
        txn_action = TransactionAction(action)
    except ValueError:
        error_output(
            f"Invalid action: {action}. Use: buy, sell, dividend, split, transfer_in, transfer_out"
        )
        raise typer.Exit(1)

    executed_at = datetime.fromisoformat(date) if date else datetime.now()

    txn = Transaction(
        symbol=symbol,
        market_type=mt,
        action=txn_action,
        quantity=quantity,
        price=price,
        fee=fee,
        tax=tax,
        currency=currency,
        executed_at=executed_at,
        note=note,
    )

    db = init_db()

    # Advisory guardrail check before trade
    try:
        from ..guardrails.rules import validate_trade as _validate

        _prices: dict[tuple[str, MarketType], float] = {}
        for pos in db.get_positions(include_zero=False):
            try:
                _provider = get_provider(pos.market_type)
                _prices[(pos.symbol, pos.market_type)] = _provider.get_current_price(
                    pos.symbol
                )
            except Exception:
                pass
        _prices[(symbol, mt)] = price
        _violations = _validate(db, symbol, mt, action, quantity, price, _prices)
        for _v in _violations:
            print(f"  ⚠ {_v.message}", file=__import__("sys").stderr)
    except Exception:
        pass  # guardrails are advisory, never block

    pm = PortfolioManager(db)
    txn_id = pm.add_trade(txn)

    result = {
        "transaction_id": txn_id,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
    }

    if use_json:
        json_output(result)
    else:
        kv_output(result)


@app.command()
def returns(
    symbol: Optional[str] = typer.Option(
        None, "--symbol", "-s", help="Specific symbol (default: all holdings)"
    ),
    market_type: Optional[str] = typer.Option(
        None, "--market-type", "-m", help="Override: a_share, crypto, us"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """View returns — unrealized P&L for holdings."""
    db = init_db()

    if symbol:
        mt = MarketType(market_type) if market_type else _detect_market_type(symbol)
        try:
            provider = get_provider(mt)
            price = provider.get_current_price(symbol)
        except Exception as e:
            error_output(f"Failed to get price for {symbol}: {e}")
            raise typer.Exit(1)

        upnl = unrealized_pnl(db, symbol, mt, price)
        rpnl = realized_pnl(db, symbol, mt)
        output = {"symbol": symbol, **upnl.model_dump(), **rpnl.model_dump()}

        if use_json:
            json_output(output)
        else:
            kv_output(output)
    else:
        # All holdings — fetch current prices
        positions = db.get_positions(include_zero=False)
        if not positions:
            print("(no holdings)")
            return

        prices: dict[tuple[str, MarketType], float] = {}
        for pos in positions:
            try:
                provider = get_provider(pos.market_type)
                prices[(pos.symbol, pos.market_type)] = provider.get_current_price(
                    pos.symbol
                )
            except Exception as e:
                error_output(f"Failed to get price for {pos.symbol}: {e}")

        summary = portfolio_returns_summary(db, prices)

        if use_json:
            json_output(summary)
        else:
            kv_output(
                {
                    "TotalMarketValue": summary.total_market_value,
                    "TotalCostBasis": summary.total_cost_basis,
                    "TotalUnrealizedPnL": summary.total_unrealized_pnl,
                    "TotalUnrealizedPnL%": summary.total_unrealized_pnl_pct,
                }
            )
            print()
            tsv_output(
                summary.holdings,
                columns=[
                    "symbol",
                    "market_type",
                    "quantity",
                    "avg_cost",
                    "current_price",
                    "unrealized_pnl",
                    "unrealized_pnl_pct",
                ],
            )


# --- Thesis subcommands ---


@thesis_app.command("add")
def thesis_add(
    symbol: str = typer.Argument(help="Stock symbol, e.g. 600519"),
    entry_price: float = typer.Argument(help="Entry price"),
    summary: str = typer.Argument(help="Core thesis / buy rationale"),
    assumptions: Optional[str] = typer.Option(
        None,
        "--assumptions",
        "-a",
        help='Key assumptions as JSON list, e.g. \'["ROE>15%", "行业景气"]\'',
    ),
    target: Optional[float] = typer.Option(None, "--target", help="Target price"),
    stop_loss: Optional[float] = typer.Option(
        None, "--stop-loss", help="Stop loss price"
    ),
    entry_date_str: Optional[str] = typer.Option(
        None, "--date", "-d", help="Entry date YYYY-MM-DD (default: today)"
    ),
    review_days: int = typer.Option(
        30, "--review-days", help="Review interval in days"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """记录投资逻辑 — record why you bought a stock."""
    entry_date = date.fromisoformat(entry_date_str) if entry_date_str else date.today()
    if assumptions:
        try:
            key_assumptions = json.loads(assumptions)
        except json.JSONDecodeError:
            error_output(
                "Invalid JSON for --assumptions. Expected format: "
                '\'["assumption1", "assumption2"]\''
            )
            raise typer.Exit(1)
    else:
        key_assumptions = []

    thesis = InvestmentThesis(
        symbol=symbol,
        entry_date=entry_date,
        entry_price=entry_price,
        thesis_summary=summary,
        key_assumptions=key_assumptions,
        target_price=target,
        stop_loss_price=stop_loss,
        review_interval_days=review_days,
    )

    db = init_db()
    thesis_id = db.add_thesis(thesis)

    result = {"thesis_id": thesis_id, "symbol": symbol, "summary": summary}
    if use_json:
        json_output(result)
    else:
        kv_output(result)


@thesis_app.command("list")
def thesis_list(
    symbol: Optional[str] = typer.Option(
        None, "--symbol", "-s", help="Filter by symbol"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", help="Filter: active, invalidated, realized"
    ),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """查看投资逻辑 — list all investment theses."""
    db = init_db()
    thesis_status = ThesisStatus(status) if status else None
    theses = db.get_theses(symbol=symbol, status=thesis_status)

    if not theses:
        typer.echo("(no theses found)")
        return

    if use_json:
        json_output([t.model_dump(mode="json") for t in theses])
    else:
        rows = []
        for t in theses:
            days_since_review = None
            if t.last_reviewed_at:
                days_since_review = (datetime.now() - t.last_reviewed_at).days
            elif t.created_at:
                days_since_review = (datetime.now() - t.created_at).days

            overdue = ""
            if (
                days_since_review is not None
                and days_since_review > t.review_interval_days
            ):
                overdue = " ⚠"

            rows.append(
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "status": t.status.value,
                    "entry": f"{t.entry_price}@{t.entry_date}",
                    "target": t.target_price or "N/A",
                    "stop_loss": t.stop_loss_price or "N/A",
                    "review": f"{days_since_review}d ago{overdue}"
                    if days_since_review
                    else "N/A",
                    "summary": t.thesis_summary[:40],
                }
            )
        tsv_output(
            rows,
            columns=[
                "id",
                "symbol",
                "status",
                "entry",
                "target",
                "stop_loss",
                "review",
                "summary",
            ],
        )


@thesis_app.command("show")
def thesis_show(
    thesis_id: int = typer.Argument(help="Thesis ID"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """查看单个投资逻辑详情 — show thesis details."""
    db = init_db()
    thesis = db.get_thesis(thesis_id)

    if not thesis:
        error_output(f"Thesis #{thesis_id} not found")
        raise typer.Exit(1)

    if use_json:
        json_output(thesis.model_dump(mode="json"))
    else:
        kv_output(
            {
                "ID": thesis.id,
                "Symbol": thesis.symbol,
                "Status": thesis.status.value,
                "EntryDate": thesis.entry_date,
                "EntryPrice": thesis.entry_price,
                "TargetPrice": thesis.target_price or "N/A",
                "StopLoss": thesis.stop_loss_price or "N/A",
                "ReviewInterval": f"{thesis.review_interval_days} days",
                "LastReviewed": thesis.last_reviewed_at or "never",
                "Summary": thesis.thesis_summary,
                "Assumptions": ", ".join(thesis.key_assumptions)
                if thesis.key_assumptions
                else "N/A",
                "InvalidationReason": thesis.invalidation_reason or "N/A",
            }
        )


@thesis_app.command("invalidate")
def thesis_invalidate(
    thesis_id: int = typer.Argument(help="Thesis ID to invalidate"),
    reason: str = typer.Argument(help="Why the thesis is no longer valid"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """标记逻辑失效 — mark a thesis as invalidated."""
    db = init_db()
    thesis = db.get_thesis(thesis_id)
    if not thesis:
        error_output(f"Thesis #{thesis_id} not found")
        raise typer.Exit(1)

    db.update_thesis_status(thesis_id, ThesisStatus.INVALIDATED, reason)

    result = {"thesis_id": thesis_id, "status": "invalidated", "reason": reason}
    if use_json:
        json_output(result)
    else:
        kv_output(result)


@thesis_app.command("realize")
def thesis_realize(
    thesis_id: int = typer.Argument(help="Thesis ID to mark as realized"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """标记逻辑兑现 — mark a thesis as realized (target hit or sold)."""
    db = init_db()
    thesis = db.get_thesis(thesis_id)
    if not thesis:
        error_output(f"Thesis #{thesis_id} not found")
        raise typer.Exit(1)

    db.update_thesis_status(thesis_id, ThesisStatus.REALIZED)

    result = {"thesis_id": thesis_id, "status": "realized"}
    if use_json:
        json_output(result)
    else:
        kv_output(result)


@thesis_app.command("review")
def thesis_review(
    thesis_id: int = typer.Argument(help="Thesis ID to mark as reviewed"),
    use_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """标记已审查 — mark a thesis as reviewed (resets review timer)."""
    db = init_db()
    thesis = db.get_thesis(thesis_id)
    if not thesis:
        error_output(f"Thesis #{thesis_id} not found")
        raise typer.Exit(1)

    db.mark_thesis_reviewed(thesis_id)

    result = {"thesis_id": thesis_id, "reviewed_at": datetime.now().isoformat()}
    if use_json:
        json_output(result)
    else:
        kv_output(result)
