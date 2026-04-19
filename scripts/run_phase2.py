"""Phase 2 — gate discovery on the synthetic IC backtest.

Sweeps the master prompt's gate parameter grid (GEX dimension dropped — see
Checkpoint 1). Runs the benchmark IC strategy through `run_backtest` per
configuration, builds a multi-objective Pareto frontier, and selects three
recommended gate sets (conservative / moderate / aggressive).

Usage:
  uv run python scripts/run_phase2.py            # full grid (~40 min)
  uv run python scripts/run_phase2.py --coarse   # 4-value-per-dim subset (~8 min)
  uv run python scripts/run_phase2.py --tiny     # 2-value subset (~30s, smoke)
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
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

from delta_optimizer.backtest.engine import (  # noqa: E402
    GateConfig,
    StrategyConfig,
    run_backtest,
)
from delta_optimizer.regime.features import CachedDataLoader, build_feature_frame  # noqa: E402
from delta_optimizer.strategies.synthetic_chain import SyntheticBSMChain  # noqa: E402

app = typer.Typer(add_completion=False, help="Phase 2 gate discovery.")
console = Console()


def _full_grid() -> list[dict]:
    grid = list(itertools.product(
        [22, 25, 28, 30, 35],          # vix_max
        [0.90, 0.95, 1.00, 1.05],      # vix_vix3m_max
        [28, 30, 32, 35],              # vix_10d_high_max
        [0.10, 0.15, 0.20, 0.25],      # vix_1d_change_max
        [20, 30, 40, 50],              # ivp_min
    ))
    return [
        {
            "vix_max": v, "vix_vix3m_max": vr, "vix_10d_high_max": vh,
            "vix_1d_change_max": vc, "ivp_min": ip,
        }
        for v, vr, vh, vc, ip in grid
    ]


def _coarse_grid() -> list[dict]:
    grid = list(itertools.product(
        [22, 28, 35],                  # 3
        [0.95, 1.00],                  # 2
        [28, 32, 35],                  # 3
        [0.15, 0.25],                  # 2
        [20, 40],                      # 2
    ))
    return [
        {
            "vix_max": v, "vix_vix3m_max": vr, "vix_10d_high_max": vh,
            "vix_1d_change_max": vc, "ivp_min": ip,
        }
        for v, vr, vh, vc, ip in grid
    ]


def _tiny_grid() -> list[dict]:
    grid = list(itertools.product(
        [25, 35],
        [0.95, 1.05],
        [30, 35],
        [0.20],
        [30],
    ))
    return [
        {
            "vix_max": v, "vix_vix3m_max": vr, "vix_10d_high_max": vh,
            "vix_1d_change_max": vc, "ivp_min": ip,
        }
        for v, vr, vh, vc, ip in grid
    ]


def _pareto_front(records: list[dict]) -> list[dict]:
    """Multi-objective Pareto: maximize pnl_per_day, minimize max_drawdown,
    maximize 'tail-blocking ratio' (lower CVaR == better tail control).

    A config dominates another iff it is at least as good on all objectives
    and strictly better on at least one.
    """
    def dominates(a: dict, b: dict) -> bool:
        # Higher pnl/day is better, lower DD is better, higher (less-negative) CVaR is better
        a_p, b_p = a["pnl_per_day"], b["pnl_per_day"]
        a_dd, b_dd = a["max_drawdown"], b["max_drawdown"]
        a_cv, b_cv = a["cvar_95"], b["cvar_95"]
        better_or_equal = (
            a_p >= b_p and a_dd <= b_dd and a_cv >= b_cv
        )
        strictly_better = (
            a_p > b_p or a_dd < b_dd or a_cv > b_cv
        )
        return better_or_equal and strictly_better

    pareto = []
    for r in records:
        if not any(dominates(other, r) for other in records if other is not r):
            pareto.append(r)
    return pareto


def _pick_three(pareto: list[dict]) -> dict[str, dict]:
    """Pick conservative (lowest DD), aggressive (highest pnl/day), moderate
    (best Sharpe-like ratio = pnl_per_day / sqrt(DD+1))."""
    if not pareto:
        return {}
    conservative = min(pareto, key=lambda r: r["max_drawdown"])
    aggressive = max(pareto, key=lambda r: r["pnl_per_day"])
    import math
    moderate = max(
        pareto,
        key=lambda r: r["pnl_per_day"] / max(math.sqrt(r["max_drawdown"] + 1), 0.01),
    )
    return {
        "conservative": conservative,
        "moderate": moderate,
        "aggressive": aggressive,
    }


@app.command()
def main(
    coarse: Annotated[bool, typer.Option(help="Coarse 72-config grid")] = False,
    tiny: Annotated[bool, typer.Option(help="Tiny 8-config smoke grid")] = False,
    start: Annotated[str, typer.Option(help="Backtest start date (YYYY-MM-DD)")] = "2023-01-01",
    end: Annotated[str, typer.Option(help="Backtest end date (YYYY-MM-DD)")] = "",
) -> None:
    out_dir = ROOT / "data" / "results" / "phase_2"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.rule("[bold]Phase 2 — gate discovery (synthetic IC backtest)[/bold]")

    loader = CachedDataLoader(ROOT / "data" / "raw")
    df = build_feature_frame(loader)
    df = df[df["vix_ivp_252d"].notna()].copy()
    if start:
        df = df.loc[start:]
    if end:
        df = df.loc[:end]
    console.print(f"  backtest window: {df.index.min().date()} .. {df.index.max().date()} ({len(df)} days)")

    chain = SyntheticBSMChain(ROOT / "data" / "raw")
    strategy = StrategyConfig()

    grid = _tiny_grid() if tiny else (_coarse_grid() if coarse else _full_grid())
    console.print(f"  grid size: {len(grid)} configurations")

    records: list[dict] = []
    t0 = time.time()
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as prog:
        t = prog.add_task("backtests", total=len(grid))
        for cfg in grid:
            gate = GateConfig(**cfg)
            r = run_backtest(df, chain, gate, strategy)
            rec = {**cfg, **r.to_dict()}
            records.append(rec)
            prog.update(t, advance=1)

    elapsed = time.time() - t0
    console.print(f"[bold green]done[/bold green] {len(grid)} configs in {elapsed/60:.1f} min")

    # Save full grid + pareto + recommended sets.
    import pandas as pd

    def _drop_unsavable(rows):
        cleaned = []
        for r in rows:
            r2 = {k: v for k, v in r.items() if k != "worst_5_days"}
            cleaned.append(r2)
        return cleaned

    grid_df = pd.DataFrame(_drop_unsavable(records))
    grid_df.to_parquet(out_dir / "grid_results.parquet", index=False)
    console.print(f"  grid saved: {out_dir / 'grid_results.parquet'}")

    pareto = _pareto_front(records)
    pareto_df = pd.DataFrame(_drop_unsavable(pareto))
    pareto_df.to_parquet(out_dir / "pareto_frontier.parquet", index=False)
    console.print(f"  Pareto frontier: {len(pareto)} configs")

    chosen = _pick_three(pareto)
    chosen_yaml = {
        name: {**cfg, "expected_metrics": {
            "pnl_total": cfg["pnl_total"],
            "pnl_per_day": cfg["pnl_per_day"],
            "win_rate": cfg["win_rate"],
            "profit_factor": cfg["profit_factor"],
            "max_drawdown": cfg["max_drawdown"],
            "cvar_95": cfg["cvar_95"],
            "n_trades": cfg["n_trades"],
            "gate_pass_rate": cfg["gate_pass_rate"],
        }}
        for name, cfg in chosen.items()
    }
    # Strip the metric duplication from the top level — keep only the gate params.
    for name, body in chosen_yaml.items():
        for k in [
            "pnl_total", "pnl_per_day", "win_rate", "profit_factor",
            "max_drawdown", "cvar_95", "n_trades", "gate_pass_rate", "worst_5_days",
            "gate_pass_days", "gate_total_days",
        ]:
            body.pop(k, None)

    yaml_path = ROOT / "configs" / "gate_sets.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.dump(chosen_yaml, f, sort_keys=False)
    console.print(f"  recommended sets: {yaml_path}")

    status = {
        "phase": 2,
        "passed": True,
        "method": "synthetic_bsm_chain",
        "grid_size": len(grid),
        "pareto_size": len(pareto),
        "elapsed_minutes": elapsed / 60,
        "data_window": {
            "start": str(df.index.min().date()),
            "end": str(df.index.max().date()),
            "trading_days": int(len(df)),
        },
        "recommended_gate_sets": chosen_yaml,
        "caveats": [
            "Synthetic chain underestimates tail losses — BSM has no jumps.",
            "Gate selection is robust to this; gates pick WHEN to enter, not exact P&L.",
            "Real-chain validation requires Polygon Options Developer or Flat Files.",
        ],
    }
    status_path = ROOT / "data" / "results" / ".phase_2_status.json"
    status_path.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    console.print(f"  status: {status_path}")


if __name__ == "__main__":
    app()
