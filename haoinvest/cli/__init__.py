"""haoInvest CLI — personal investment portfolio management."""

import typer

from . import analyze, journal, market, portfolio, strategy

app = typer.Typer(
    name="haoinvest",
    help="Personal investment portfolio management system.",
    no_args_is_help=True,
)

app.add_typer(market.app, name="market")
app.add_typer(portfolio.app, name="portfolio")
app.add_typer(analyze.app, name="analyze")
app.add_typer(strategy.app, name="strategy")
app.add_typer(journal.app, name="journal")
