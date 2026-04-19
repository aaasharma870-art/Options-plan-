"""Phase 0 FRED pull — DTB3 (13-week T-bill rate, our risk-free proxy)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env")

from delta_optimizer.ingest.fred_client import FredClient  # noqa: E402

app = typer.Typer(add_completion=False, help="FRED pulls (DTB3).")
console = Console()


@app.command()
def main(
    series: Annotated[str, typer.Option(help="FRED series id")] = "DTB3",
    start: Annotated[str, typer.Option(help="ISO date")] = "2022-01-01",
    end: Annotated[str, typer.Option(help="ISO date, default today")] = "",
) -> None:
    """Pull a FRED series and cache it. Idempotent."""
    from datetime import date

    end = end or date.today().isoformat()
    client = FredClient(cache_dir=ROOT / "data" / "raw")
    payload = client.series(series, start, end)
    n = sum(1 for v in payload["values"] if v is not None)
    console.print(
        f"[bold green]done[/bold green] series={series} obs={n} "
        f"range={payload['dates'][0] if payload['dates'] else 'n/a'}"
        f" -> {payload['dates'][-1] if payload['dates'] else 'n/a'}"
    )


if __name__ == "__main__":
    app()
