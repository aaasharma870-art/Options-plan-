"""Phase 4 — portfolio backtest + stress tests + allocation comparison.

Loads all Phase-3-accepted bots + the Aryan Optimized legacy baseline,
runs each independently to get a daily-PnL matrix, then aggregates per
the three allocation methods.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import typer
import yaml
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from delta_optimizer.backtest.engine import GateConfig, StrategyConfig  # noqa
from delta_optimizer.backtest.portfolio import (  # noqa
    BotInPortfolio,
    aggregate_portfolio,
    equal_weight,
    mean_variance_weights,
    risk_parity_weights,
    run_per_bot,
    stress_test,
)
from delta_optimizer.regime.features import CachedDataLoader, build_feature_frame  # noqa
from delta_optimizer.strategies.synthetic_chain import SyntheticBSMChain  # noqa

app = typer.Typer(add_completion=False, help="Phase 4 portfolio backtest.")
console = Console()

STARTING_CAPITAL = 50000.0


def _gate_from_config(gates_list: list[dict]) -> GateConfig:
    g = GateConfig()
    for gate in gates_list:
        t = gate.get("type", "")
        v = gate.get("value")
        if t in ("vix_level_max", "vix_max"):
            g.vix_max = float(v)
        elif t == "vix_vix3m_max":
            g.vix_vix3m_max = float(v)
        elif t == "vix_10d_high_max":
            g.vix_10d_high_max = float(v)
        elif t == "vix_1d_change_max":
            g.vix_1d_change_max = float(v)
        elif t == "ivp_min":
            g.ivp_min = float(v)
    return g


def _strategy_from_phase3(slug: str, accepted_dir: Path) -> StrategyConfig:
    """Build StrategyConfig from Phase 3 best_params if available, else defaults."""
    p = accepted_dir / f"{slug}.json"
    if not p.exists():
        return None
    body = json.loads(p.read_text())
    bp = body["tuning"]["best_params"]
    is_butterfly = "iron_fly" in slug or "butterfly" in slug
    sc = bp.get("short_call_delta", 0.50 if is_butterfly else 0.16)
    sp = bp.get("short_put_delta", 0.50 if is_butterfly else 0.16)
    dte_idx = int(bp.get("dte_idx", 3))
    dte_pairs = [(7, 14), (14, 21), (21, 30), (30, 45), (45, 60)]
    dte_min, dte_max = dte_pairs[min(dte_idx, len(dte_pairs) - 1)]
    underlying = body.get("underlying", "SPY")
    return StrategyConfig(
        short_call_delta=sc,
        long_call_delta=bp["long_call_delta"],
        short_put_delta=sp,
        long_put_delta=bp["long_put_delta"],
        dte_min=dte_min, dte_max=dte_max,
        profit_target_pct=bp["profit_target"],
        stop_loss_credit_multiple=bp["stop_loss"],
        time_exit_dte=bp["time_exit"],
        max_concurrent=3,
        qty_per_leg=1,
        underlying=underlying,
    )


def _strategy_from_legacy(cfg: dict) -> StrategyConfig:
    s = cfg["structure"]
    return StrategyConfig(
        short_call_delta=float(s.get("short_call_delta", 0.18)),
        long_call_delta=float(s.get("long_call_delta", 0.07)),
        short_put_delta=float(s.get("short_put_delta", 0.18)),
        long_put_delta=float(s.get("long_put_delta", 0.07)),
        dte_min=int(cfg["entry"]["dte_min"]),
        dte_max=int(cfg["entry"]["dte_max"]),
        profit_target_pct=float(cfg["exit"]["profit_target_pct"]) / 100.0,
        stop_loss_credit_multiple=float(cfg["exit"]["stop_loss_credit_multiple"]),
        time_exit_dte=int(cfg["exit"]["time_exit_dte"]),
        max_concurrent=int(cfg["sizing"]["max_concurrent"]),
        qty_per_leg=int(cfg["sizing"]["contracts_per_trade"]),
        underlying=cfg["underlying"]["symbol"],
    )


@app.command()
def main() -> None:
    out_dir = ROOT / "data" / "results" / "phase_4"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.rule("[bold]Phase 4 — portfolio backtest[/bold]")

    loader = CachedDataLoader(ROOT / "data" / "raw")
    feature_df = build_feature_frame(loader)
    feature_df = feature_df[feature_df["vix_ivp_252d"].notna()].copy()
    chain = SyntheticBSMChain(ROOT / "data" / "raw")

    # Build the list of bots (6 Phase-3-accepted + 1 legacy)
    bots: list[BotInPortfolio] = []

    # 1. Phase 3 accepted
    accepted_dir = ROOT / "data" / "results" / "phase_3" / "accepted"
    proposals_dir = ROOT / "configs" / "proposals"
    for j in sorted(accepted_dir.glob("*.json")):
        slug = j.stem
        prop_yaml = proposals_dir / f"{slug}.yaml"
        if not prop_yaml.exists():
            continue
        prop = yaml.safe_load(prop_yaml.read_text())
        gate = _gate_from_config(prop.get("regime_gates", []))
        strategy = _strategy_from_phase3(slug, accepted_dir)
        if strategy is None:
            continue
        bots.append(BotInPortfolio(
            bot_id=slug,
            underlying=prop["underlying"]["symbol"],
            gate=gate, strategy=strategy,
            allocation_usd=float(prop.get("sizing", {}).get("allocation_usd", 10000)),
        ))

    # 2. Legacy bot — Aryan Optimized
    legacy_yaml = ROOT / "configs" / "legacy" / "aryan-optimized.yaml"
    if legacy_yaml.exists():
        legacy = yaml.safe_load(legacy_yaml.read_text())
        bots.append(BotInPortfolio(
            bot_id=legacy["bot_id"],
            underlying=legacy["underlying"]["symbol"],
            gate=_gate_from_config(legacy.get("regime_gates", [])),
            strategy=_strategy_from_legacy(legacy),
            allocation_usd=float(legacy.get("sizing", {}).get("allocation_usd", 10000)),
        ))

    console.print(f"  bots in portfolio: {len(bots)}  (6 Phase-3 accepted + 1 legacy)")

    # 3. Run each bot independently → daily PnL matrix
    console.rule("Running per-bot backtests")
    series_by_bot = run_per_bot(bots, feature_df, chain)
    pnl_matrix = pd.DataFrame(series_by_bot)
    console.print(f"  P&L matrix: {pnl_matrix.shape[0]} days × {pnl_matrix.shape[1]} bots")

    # 4. Allocation methods
    bot_ids = list(pnl_matrix.columns)
    methods = {
        "equal_weight": equal_weight(bot_ids),
        "risk_parity": risk_parity_weights(pnl_matrix),
        "mean_variance_40cap": mean_variance_weights(pnl_matrix, max_per_bot=0.40),
    }

    # 5. Aggregate per method
    results = {}
    for name, w in methods.items():
        r = aggregate_portfolio(pnl_matrix, w, STARTING_CAPITAL, apply_breaker=True)
        results[name] = r

    # Pretty print summary table
    table = Table(title="Portfolio aggregate metrics by allocation")
    table.add_column("method")
    table.add_column("Sharpe", justify="right")
    table.add_column("Max DD", justify="right")
    table.add_column("Max DD %", justify="right")
    table.add_column("p95 daily loss", justify="right")
    table.add_column("worst day", justify="right")
    table.add_column("CB days", justify="right")
    table.add_column("gates pass")
    for name, r in results.items():
        passes = r.aggregate_passes
        gates_str = "/".join(["✓" if v else "✗" for v in passes.values()])
        table.add_row(
            name, f"{r.sharpe_calendar:.2f}",
            f"${r.max_drawdown_dollar:,.0f}",
            f"{r.max_drawdown_pct:.1%}",
            f"{r.pct_95_loss:.2%}",
            f"${r.worst_day_loss:,.0f} ({r.worst_day_date})",
            str(r.circuit_breaker_days),
            gates_str,
        )
    console.print(table)

    # 6. Per-bot weights table
    wt_table = Table(title="Allocation weights per method")
    wt_table.add_column("bot")
    for m in methods:
        wt_table.add_column(m, justify="right")
    for bid in bot_ids:
        wt_table.add_row(bid, *(f"{methods[m][bid]:.1%}" for m in methods))
    console.print(wt_table)

    # 7. Stress tests (sub-windows of available history)
    console.rule("Stress tests (sub-windows of cached history)")
    stress_windows = [
        ("2023_full", "2023-01-01", "2023-12-31"),
        ("2024_full", "2024-01-01", "2024-12-31"),
        ("apr_2025_vix_spike", "2025-03-15", "2025-05-15"),
        ("oct_2025_drawdown", "2025-09-15", "2025-11-15"),
        ("recent_q1_2026", "2026-01-01", "2026-04-17"),
    ]
    # Use the equal-weight allocation for stress tests (simplest, comparable)
    stress_results = []
    for name, start, end in stress_windows:
        st = stress_test(pnl_matrix, methods["equal_weight"], STARTING_CAPITAL, name, start, end)
        stress_results.append(st)
        if st.get("skipped"):
            console.print(f"  {name}: skipped ({st['reason']})")
        else:
            console.print(
                f"  {name}: {st['n_days']}d  pnl=${st['total_pnl']:,.0f}  "
                f"maxDD=${st['max_dd_dollar']:,.0f} ({st['max_dd_pct']:.1%})  "
                f"worst=${st['worst_day']:,.0f} ({st['worst_day_date']})"
            )

    # 8. Per-bot correlation (C7 differentiation among Phase-3 accepted + legacy)
    corr = pnl_matrix.corr()
    console.print("\n[bold]Pairwise daily-PnL correlation (C7 differentiation):[/bold]")
    console.print(corr.round(2).to_string())

    # 9. Save status JSON + raw data
    pnl_matrix.to_parquet(out_dir / "pnl_matrix.parquet", index=True)
    corr.to_parquet(out_dir / "correlation_matrix.parquet", index=True)
    status = {
        "phase": 4,
        "starting_capital": STARTING_CAPITAL,
        "n_bots": len(bots),
        "bot_ids": bot_ids,
        "methods": {
            name: {
                "weights": r.weights,
                "sharpe": r.sharpe_calendar,
                "max_dd_dollar": r.max_drawdown_dollar,
                "max_dd_pct": r.max_drawdown_pct,
                "p95_daily_loss": r.pct_95_loss,
                "worst_day": r.worst_day_loss,
                "worst_day_date": r.worst_day_date,
                "circuit_breaker_days": r.circuit_breaker_days,
                "aggregate_passes": r.aggregate_passes,
                "n_trading_days": r.n_trading_days,
            }
            for name, r in results.items()
        },
        "stress_tests": stress_results,
        "correlation_matrix": corr.to_dict(),
    }
    status_path = ROOT / "data" / "results" / ".phase_4_status.json"
    status_path.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")
    console.print(f"\n  status: {status_path}")


if __name__ == "__main__":
    app()
