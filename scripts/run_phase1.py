"""Phase 1 orchestrator.

Loads cached data, builds the feature frame, scores regime, runs the ANOVA
validation gate, writes status JSON, renders the regime timeline, and writes
checkpoints/checkpoint_1.md.

Usage: uv run python scripts/run_phase1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import typer
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from delta_optimizer.regime.features import (  # noqa: E402
    CachedDataLoader,
    build_feature_frame,
    write_feature_parquet,
)
from delta_optimizer.regime.score import (  # noqa: E402
    ScoreThresholds,
    bucket_for_score,
    score_dataframe,
)
from delta_optimizer.regime.validate import evaluate_gate  # noqa: E402

app = typer.Typer(add_completion=False, help="Phase 1: regime classifier validation.")
console = Console()

BUCKET_COLORS = {
    "GREEN": "#22c55e",
    "YELLOW": "#eab308",
    "ORANGE": "#f97316",
    "RED": "#ef4444",
}


def _attempt_threshold_iterations(
    df, base: ScoreThresholds
) -> tuple[ScoreThresholds, list[dict]]:
    """If the base thresholds fail, try ±3 unit perturbations around VIX bounds.

    Master prompt's escape clause: 'iterate on thresholds within ±3 units of
    starting values. If still fails after 3 iterations, stop and write
    diagnostic report.'
    """
    attempts = []
    candidates: list[ScoreThresholds] = [base]
    # Three additional candidates: tighten VIX, loosen VIX, shift IVP bands.
    candidates.append(ScoreThresholds(vix_low=15.0, vix_high=20.0))
    candidates.append(ScoreThresholds(vix_low=18.0, vix_high=24.0))
    candidates.append(
        ScoreThresholds(
            ivp_low_red=20.0,
            ivp_low_yellow=40.0,
            ivp_high_yellow=85.0,
            ivp_high_red=95.0,
        )
    )

    best = base
    best_result = None
    for i, t in enumerate(candidates):
        r = evaluate_gate(df, t)
        attempts.append(
            {
                "iteration": i,
                "thresholds": r.thresholds,
                "passed": r.passed,
                "anova_p": r.anova_p,
                "cohens_d_green_vs_red": r.cohens_d_green_vs_red,
            }
        )
        if r.passed:
            return t, attempts
        if best_result is None or (
            r.cohens_d_green_vs_red is not None
            and (best_result.cohens_d_green_vs_red is None
                 or r.cohens_d_green_vs_red > best_result.cohens_d_green_vs_red)
        ):
            best, best_result = t, r
    return best, attempts


def _render_timeline(scored, out_path: Path) -> None:
    """Render regime score over time with bucket-colored shading."""
    fig, axes = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # Top: VIX with regime-colored shading.
    ax = axes[0]
    ax.plot(scored.index, scored["vix_close"], color="black", linewidth=0.8, label="VIX")
    ax.set_ylabel("VIX")
    ax.set_title("Regime score over time (3-factor: VIX level, VIX-IVP, VIX/VIX3M)")

    last_bucket = None
    span_start = scored.index[0]
    for ts, bucket in scored["regime_bucket"].items():
        if bucket != last_bucket and last_bucket is not None:
            color = BUCKET_COLORS.get(last_bucket, "#cccccc")
            ax.axvspan(span_start, ts, alpha=0.18, color=color)
            span_start = ts
        last_bucket = bucket
    if last_bucket is not None:
        ax.axvspan(span_start, scored.index[-1], alpha=0.18,
                   color=BUCKET_COLORS.get(last_bucket, "#cccccc"))

    # Bucket legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.45) for c in BUCKET_COLORS.values()]
    ax.legend(handles, list(BUCKET_COLORS.keys()), loc="upper left")

    # Bottom: regime score bars.
    ax2 = axes[1]
    valid = scored[scored["regime_score"] >= 0]
    colors = [BUCKET_COLORS.get(b, "#888") for b in valid["regime_bucket"]]
    ax2.bar(valid.index, valid["regime_score"], color=colors, width=1.0, edgecolor="none")
    ax2.set_ylabel("composite (0-6)")
    ax2.set_yticks([0, 1, 2, 3, 4, 5, 6])
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=130)
    plt.close(fig)


def _print_summary_table(result_dict: dict) -> None:
    t = Table(title="Phase 1 ANOVA gate")
    t.add_column("metric")
    t.add_column("value", justify="right")
    t.add_row("passed", str(result_dict["passed"]))
    t.add_row("n_total", str(result_dict["n_total"]))
    t.add_row(
        "anova_p",
        f"{result_dict['anova_p']:.6f}" if result_dict["anova_p"] is not None else "n/a",
    )
    t.add_row(
        "cohens_d_green_vs_red",
        f"{result_dict['cohens_d_green_vs_red']:.4f}"
        if result_dict["cohens_d_green_vs_red"] is not None else "n/a",
    )
    console.print(t)

    bucket_t = Table(title="forward 5d realized vol by bucket")
    bucket_t.add_column("bucket")
    bucket_t.add_column("n", justify="right")
    bucket_t.add_column("mean fwd RV", justify="right")
    bucket_t.add_column("stddev fwd RV", justify="right")
    for b in ["GREEN", "YELLOW", "ORANGE", "RED"]:
        bucket_t.add_row(
            b,
            str(result_dict["n_per_bucket"].get(b, 0)),
            f"{result_dict['fwd_rv_mean_per_bucket'].get(b, float('nan')):.4f}",
            f"{result_dict['fwd_rv_std_per_bucket'].get(b, float('nan')):.4f}",
        )
    console.print(bucket_t)


@app.command()
def main() -> None:
    cache_dir = ROOT / "data" / "raw"
    out_dir = ROOT / "data" / "results" / "phase_1"
    out_dir.mkdir(parents=True, exist_ok=True)

    console.rule("[bold]Phase 1: regime classifier")

    loader = CachedDataLoader(cache_dir)
    df = build_feature_frame(loader)
    write_feature_parquet(df, out_dir / "features.parquet")
    console.print(f"  features: {len(df):,} rows  cols={list(df.columns)}")

    base = ScoreThresholds()
    final_thresholds, attempts = _attempt_threshold_iterations(df, base)
    final_result = evaluate_gate(df, final_thresholds)

    scored = score_dataframe(df, final_thresholds)
    scored.to_parquet(out_dir / "scored.parquet", index=True)
    _render_timeline(scored, out_dir / "regime_timeline.png")

    status_payload = {
        "phase": 1,
        "passed": final_result.passed,
        "result": final_result.to_dict(),
        "threshold_iterations": attempts,
        "data_window": {
            "start": str(scored.index.min().date()),
            "end": str(scored.index.max().date()),
            "trading_days": int(len(scored)),
        },
        "factors_used": ["vix_level", "vix_iv_percentile_252d", "vix_vix3m"],
        "factors_deferred": ["spx_net_gex"],
        "notes": [
            "Phase 1 runs a 3-factor regime classifier.",
            "GEX is deferred until Phase 2 chain backfill — see Checkpoint 0.",
            "IV Percentile uses VIX (which IS SPY's 30-day ATM IV) over a 252d window.",
        ],
    }

    status_path = ROOT / "data" / "results" / ".phase_1_status.json"
    status_path.write_text(json.dumps(status_payload, indent=2, default=str), encoding="utf-8")
    console.print(f"  status: {status_path}  passed={final_result.passed}")

    _print_summary_table(final_result.to_dict())

    if final_result.passed:
        console.print("[bold green]Phase 1 gate PASSED[/bold green]")
    else:
        console.print(
            "[bold red]Phase 1 gate FAILED[/bold red] — see status JSON for details and "
            "Checkpoint 1 for diagnostic"
        )


if __name__ == "__main__":
    app()
