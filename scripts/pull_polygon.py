"""Phase 0 Polygon (Massive.com) data pulls.

Datasets:
  index    — VIX, VIX3M, VVIX, SKEW EOD (~minutes)
  ohlc     — SPY/QQQ/IWM + 7 single names EOD (~tens of minutes)
  earnings — reference data for the 7 single names (~minutes)
  chains   — full options chains, 0-60 DTE, per trading day (~40-80 hours)
  all      — runs all four in order

Each pull is idempotent: cached responses are reused on rerun.
Progress is logged to data/raw/pull.log and rendered live via Rich.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env")

from delta_optimizer.ingest.polygon_client import PolygonClient  # noqa: E402
from delta_optimizer.ingest.yfinance_client import YAHOO_INDEX_SYMBOLS, YFinanceClient  # noqa: E402

app = typer.Typer(
    add_completion=False,
    help="Phase 0 Polygon pulls. Idempotent. Resume-safe via cache manifest.",
)

console = Console()

# Indices come from Yahoo (Polygon Stocks/Options Starter doesn't include I:VIX etc.)
INDEX_NAMES = list(YAHOO_INDEX_SYMBOLS.keys())
OHLC_UNDERLYINGS = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
SINGLE_NAMES = ["AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "TSLA"]
DEFAULT_START = "2022-01-01"


def _setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[RichHandler(console=console, rich_tracebacks=True), file_handler],
    )


def _yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _trading_days(start: str, end: str) -> list[date]:
    """Approximate trading-day calendar: Mon-Fri between start..end inclusive.

    True NYSE calendar (with holidays) lives in a future module; this is sufficient
    for chain-pull batching where holidays just produce empty responses (cached as such).
    """
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    days = []
    cur = s
    while cur <= e:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _pull_index(yclient: YFinanceClient, start: str, end: str, dry: bool) -> None:
    console.rule(f"[bold]index aggs (Yahoo)[/bold] {start} -> {end}")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("indices", total=len(INDEX_NAMES))
        for name in INDEX_NAMES:
            yahoo_sym = YAHOO_INDEX_SYMBOLS[name]
            if dry:
                console.print(f"  [dim]would pull[/dim] {name} ({yahoo_sym})")
            else:
                try:
                    yclient.daily_close(yahoo_sym, start, end)
                except Exception as e:  # noqa: BLE001
                    console.print(f"[red]  failed[/red] {name}: {e}")
            prog.update(t, advance=1)


def _pull_ohlc(client: PolygonClient, start: str, end: str, dry: bool) -> None:
    console.rule(f"[bold]underlying OHLC[/bold] {start} -> {end}")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("ohlc", total=len(OHLC_UNDERLYINGS))
        for tkr in OHLC_UNDERLYINGS:
            if dry:
                console.print(f"  [dim]would pull[/dim] {tkr}")
            else:
                client.aggs_daily(tkr, start, end)
            prog.update(t, advance=1)


def _pull_earnings(client: PolygonClient, dry: bool) -> None:
    console.rule("[bold]reference (single-name metadata)[/bold]")
    for tkr in SINGLE_NAMES:
        if dry:
            console.print(f"  [dim]would pull reference for[/dim] {tkr}")
        else:
            client.ticker_reference(tkr)
    console.print(
        "[yellow]note:[/yellow] earnings dates require the reference/dividends or "
        "vX/reference/upcoming endpoints; full implementation deferred to Phase 1 "
        "where we structure the earnings calendar properly."
    )


def _pull_chains(client: PolygonClient, start: str, end: str, dry: bool) -> None:
    console.rule(f"[bold]option chains[/bold] {start} -> {end} (the long pull)")
    days = _trading_days(start, end)
    total = len(OHLC_UNDERLYINGS) * len(days)
    console.print(
        f"  [dim]plan:[/dim] {len(OHLC_UNDERLYINGS)} underlyings × {len(days)} days = "
        f"{total} day-snapshots (each may paginate to many calls)"
    )
    if dry:
        console.print("[yellow]dry-run; not pulling[/yellow]")
        return

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("chains", total=total)
        for tkr in OHLC_UNDERLYINGS:
            for day in days:
                # Phase 0: pull the snapshot as-of each day, filtered to next 60d.
                # Polygon's snapshot endpoint returns "live" — for true historical
                # chains per day we'll need /v3/reference/options/contracts and
                # per-contract aggs in Phase 1. Phase 0 captures the structure now.
                exp_lte = (day + timedelta(days=60)).isoformat()
                try:
                    first = client.option_chain_snapshot(tkr, expiration_lte=exp_lte)
                    client.paginate(first)
                except Exception as e:  # noqa: BLE001
                    console.print(f"[red]  failed[/red] {tkr} {day}: {e}")
                prog.update(t, advance=1)


@app.command()
def main(
    dataset: Annotated[
        str, typer.Option(help="index | ohlc | earnings | chains | all")
    ] = "all",
    start: Annotated[str, typer.Option(help="ISO date, default 2022-01-01")] = DEFAULT_START,
    end: Annotated[str, typer.Option(help="ISO date, default yesterday")] = "",
    dry_run: Annotated[bool, typer.Option(help="Plan only, no network")] = False,
) -> None:
    """Run a Phase 0 pull. Resume-safe via content-addressed cache."""
    end = end or _yesterday()
    log_path = ROOT / "data" / "raw" / "pull.log"
    _setup_logging(log_path)

    client = PolygonClient(cache_dir=ROOT / "data" / "raw")
    yclient = YFinanceClient(cache_dir=ROOT / "data" / "raw")

    console.print(
        f"[bold]delta-optimizer pull[/bold] dataset={dataset} start={start} end={end} "
        f"dry_run={dry_run}"
    )
    console.print(f"  cache: {client.cache.root}")
    console.print(f"  bucket: {client.bucket.capacity}/min (will probe on first call)")

    if dataset in ("index", "all"):
        _pull_index(yclient, start, end, dry_run)
    if dataset in ("ohlc", "all"):
        _pull_ohlc(client, start, end, dry_run)
    if dataset in ("earnings", "all"):
        _pull_earnings(client, dry_run)
    if dataset in ("chains", "all"):
        _pull_chains(client, start, end, dry_run)

    console.print(
        f"[bold green]done[/bold green]  bucket now {client.bucket.capacity:.1f}/min"
    )


if __name__ == "__main__":
    app()
