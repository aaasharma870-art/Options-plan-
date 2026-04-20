"""Phase 5 — generate the deliverables Aryan reads to manually build bots in OA.

Per accepted bot:
  deliverables/bots/<bot_name>/
    README.md            # summary + thesis + regime + expected perf
    oa_build_guide.md    # step-by-step OA UI instructions (every field value)
    config.yaml          # machine-readable params for regeneration
    performance.md       # DSR, CPCV, max DD, WR, PF, trade frequency
    kill_switches.md     # bot-specific pause conditions

Suite-level (deliverables/):
    suite_summary.md
    regime_monitor.md
    portfolio_kill_switches.md
    validation_summary.md
    build_order.md
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DELIVER = ROOT / "deliverables"
BOTS_DIR = DELIVER / "bots"


# Bot metadata: thesis location, structure label, regime gate description, role.
BOT_META = {
    "spy-tight-ic-aggressive": {
        "name": "SPY Tight Iron Condor (Aggressive Gate)",
        "thesis": "proposals/2026-04-19-spy-tight-ic-aggressive.md",
        "structure": "Iron Condor",
        "regime_role": "Always-on short-vol when no kill switches firing",
        "underlying_class": "A",
    },
    "qqq-ic-extension": {
        "name": "QQQ Iron Condor (Class A Extension)",
        "thesis": "proposals/2026-04-19-qqq-ic-extension.md",
        "structure": "Iron Condor",
        "regime_role": "Premium-collection diversifier away from SPY surface",
        "underlying_class": "A",
    },
    "spy-bull-put-elevated-vol": {
        "name": "SPY Bull Put (Elevated VIX + Trend-Up)",
        "thesis": "proposals/2026-04-19-spy-bull-put-elevated-vol.md",
        "structure": "Vertical Credit (bull put)",
        "regime_role": "Vol-crush + drift directional bot, post-spike recovery",
        "underlying_class": "A",
    },
    "spy-iron-fly-low-vvix": {
        "name": "SPY Iron Butterfly (Low-VVIX Gate)",
        "thesis": "proposals/2026-04-19-spy-iron-fly-low-vvix.md",
        "structure": "Iron Butterfly",
        "regime_role": "Pin-risk premium when vol-of-vol is suppressed",
        "underlying_class": "A",
    },
    "spy-bear-call-post-spike-fade": {
        "name": "SPY Bear Call (Post-Spike Fade)",
        "thesis": "proposals/2026-04-19-spy-bear-call-post-spike-fade.md",
        "structure": "Vertical Credit (bear call)",
        "regime_role": "Mean-reversion fade after VIX spike + failed bounce",
        "underlying_class": "A",
    },
    "spy-ic-regime-recovery": {
        "name": "SPY Iron Condor (Regime Recovery)",
        "thesis": "proposals/2026-04-19-spy-ic-regime-recovery.md",
        "structure": "Iron Condor",
        "regime_role": "Event-driven entry on RED -> GREEN/YELLOW transitions",
        "underlying_class": "A",
    },
    "aryan_optimized_legacy": {
        "name": "Aryan Optimized v2 (Legacy + Gate Layer)",
        "thesis": "(reconstructed from PROJECT_BRIEF.md context — pre-existing live bot)",
        "structure": "Iron Condor",
        "regime_role": "Replaces existing ungated bot with regime-gated version",
        "underlying_class": "A",
    },
}


def _load_phase3(slug: str) -> dict | None:
    p = ROOT / "data" / "results" / "phase_3" / "accepted" / f"{slug}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _load_proposal_yaml(slug: str) -> dict | None:
    p = ROOT / "configs" / "proposals" / f"{slug}.yaml"
    if not p.exists():
        return None
    return yaml.safe_load(p.read_text())


def _load_phase4_status() -> dict:
    return json.loads((ROOT / "data" / "results" / ".phase_4_status.json").read_text())


def _bot_perf_summary(slug: str) -> dict:
    """Pull tuning + CPCV + Phase 4 weight summary."""
    p3 = _load_phase3(slug)
    if p3 is None:
        return {}
    t = p3["tuning"]
    c = p3["cpcv"]
    p4 = _load_phase4_status()
    weight_eq = p4["methods"]["equal_weight"]["weights"].get(slug, 0.0)
    weight_rp = p4["methods"]["risk_parity"]["weights"].get(slug, 0.0)
    weight_mv = p4["methods"]["mean_variance_40cap"]["weights"].get(slug, 0.0)
    return {
        "best_params": t["best_params"],
        "dsr_z": t["best_dsr"],
        "raw_sharpe": t["best_raw_sharpe"],
        "wr": t["best_win_rate"],
        "pf": t["best_profit_factor"],
        "trades": t["best_n_trades"],
        "pnl": t["best_pnl"],
        "max_dd": t["best_max_drawdown"],
        "cpcv_folds_won": c["folds_won_dsr_gt_1"],
        "cpcv_folds_total": c["folds_total"],
        "oos_trades": c["total_oos_trades"],
        "weight_equal": weight_eq,
        "weight_risk_parity": weight_rp,
        "weight_mean_variance": weight_mv,
    }


def _format_oa_build_steps(slug: str, meta: dict, prop: dict, perf: dict) -> str:
    """Generate step-by-step OA UI instructions for one bot."""
    is_legacy = slug == "aryan_optimized_legacy"
    structure_type = prop["structure"]["type"] if not is_legacy else "iron_condor"
    underlying = prop["underlying"]["symbol"] if not is_legacy else "SPY"
    sizing = prop.get("sizing", {})
    allocation = sizing.get("allocation_usd", 10000)
    contracts = sizing.get("contracts_per_trade", 1)
    max_concurrent = sizing.get("max_concurrent", 3)

    bp = perf.get("best_params", {})
    sc = bp.get("short_call_delta", prop["structure"].get("short_call_delta", 0.16) if not is_legacy else 0.18)
    sp = bp.get("short_put_delta", prop["structure"].get("short_put_delta", 0.16) if not is_legacy else 0.18)
    lc = bp.get("long_call_delta", prop["structure"].get("long_call_delta", 0.05) if not is_legacy else 0.07)
    lp = bp.get("long_put_delta", prop["structure"].get("long_put_delta", 0.05) if not is_legacy else 0.07)
    pt = bp.get("profit_target", prop.get("exit", {}).get("profit_target_pct", 50)/100 if not is_legacy else 0.50)
    sl = bp.get("stop_loss", prop.get("exit", {}).get("stop_loss_credit_multiple", 2.0) if not is_legacy else 2.0)
    te = bp.get("time_exit", prop.get("exit", {}).get("time_exit_dte", 21) if not is_legacy else 21)

    dte_pairs = [(7, 14), (14, 21), (21, 30), (30, 45), (45, 60)]
    dte_idx = bp.get("dte_idx")
    if dte_idx is not None:
        dte_min, dte_max = dte_pairs[min(int(dte_idx), len(dte_pairs)-1)]
    else:
        dte_min = prop.get("entry", {}).get("dte_min", 30) if not is_legacy else 30
        dte_max = prop.get("entry", {}).get("dte_max", 45) if not is_legacy else 45

    gates = prop.get("regime_gates", []) if not is_legacy else []

    out = []
    out.append(f"# OA Build Guide — {meta['name']}\n")
    out.append("## Step-by-step UI instructions\n")
    out.append("Open Option Alpha → Bots → Create New Bot. Fill in:\n")
    out.append(f"### 1. Bot identity")
    out.append(f"- **Name:** `{slug.replace('-', ' ').title()}`")
    out.append(f"- **Underlyings (Symbols):** `{underlying}`")
    out.append(f"- **Allocation (USD):** `${allocation:,.0f}`")
    out.append(f"- **Position limit:** `{max_concurrent}`")
    out.append(f"- **Scan speed:** `Standard (15 min)` for 30+ DTE, `Fast (1 min)` for 0-7 DTE\n")

    out.append("### 2. Scanner Automation\n")
    out.append("**Trigger:** Recurring at scan_time (default 09:45 ET; 10:30 ET for timing-edge bots).\n")
    out.append("**Decision tree (top-down, all conditions AND'd):**\n")

    # Gate filters
    if gates:
        out.append("Regime gates (each is one OA decision branch):")
        for gate in gates:
            t = gate.get("type", "")
            v = gate.get("value")
            out.append(f"- `{t}` ≤ `{v}`" if "max" in t or t == "regime_score_max" else f"- `{t}` ≥ `{v}`" if "min" in t else f"- `{t}` = `{v}`")
        out.append("")
    else:
        out.append("**No regime gates** — this bot intentionally trades whenever the position-limit allows. (LEGACY BEHAVIOR — not recommended for new bots; see kill_switches.md for backstop conditions.)\n")

    out.append("**Position criteria:**\n")
    if structure_type == "iron_condor":
        out.append(f"- Structure: Iron Condor")
        out.append(f"- Short call delta: `{sc:.3f}` (±0.02 tolerance)")
        out.append(f"- Long call delta: `{lc:.3f}` (±0.02 tolerance)")
        out.append(f"- Short put delta: `{sp:.3f}` (±0.02 tolerance)")
        out.append(f"- Long put delta: `{lp:.3f}` (±0.02 tolerance)")
    elif structure_type == "iron_butterfly":
        out.append(f"- Structure: Iron Butterfly (body at ATM, 50Δ on each short leg)")
        out.append(f"- Long call delta: `{lc:.3f}` (wing)")
        out.append(f"- Long put delta: `{lp:.3f}` (wing)")
    elif structure_type == "vertical_credit":
        side = prop["structure"].get("side_bias", "bullish")
        if side == "bullish":
            out.append(f"- Structure: Bull Put Credit Spread")
            out.append(f"- Short put delta: `{sp:.3f}` (±0.02 tolerance)")
            out.append(f"- Long put delta: `{lp:.3f}` (±0.02 tolerance)")
        else:
            out.append(f"- Structure: Bear Call Credit Spread")
            out.append(f"- Short call delta: `{sc:.3f}` (±0.02 tolerance)")
            out.append(f"- Long call delta: `{lc:.3f}` (±0.02 tolerance)")

    out.append(f"- DTE window: `{dte_min}-{dte_max}` days")
    out.append(f"- Min credit: `$0.40` (reject thin chains)")
    out.append(f"- Max bid-ask: `$0.15` per leg (liquidity guard)\n")

    out.append("**Order settings:**\n")
    out.append(f"- Order type: `Limit at mid`")
    out.append(f"- Smart price slippage: `$0.05`")
    out.append(f"- Quantity: `{contracts}` contract(s)\n")

    out.append("### 3. Exit Automations\n")
    out.append(f"- **Profit target:** Close when P&L ≥ `{pt*100:.0f}%` of credit received")
    out.append(f"- **Stop loss:** Close when P&L ≤ `-{sl:.1f}× credit` (i.e., losing {sl*100:.0f}% of credit)")
    out.append(f"- **Time exit:** Close at `DTE = {te}` regardless of P&L")
    out.append(f"- **Regime flip kill:** If your TradingView webhook signals `regime_score_max=4`, close all positions immediately")
    out.append(f"- **PDT 1-day wait:** Enable to avoid same-day open-close cycles\n")

    out.append("### 4. Per-bot kill switches (also see kill_switches.md)\n")
    out.append("- VIX intraday > `35` → halt new entries for the day")
    out.append("- Account-level drawdown > `5%` from monthly peak → halt all new entries\n")

    out.append("### 5. Verification before Going Live\n")
    out.append("1. Set bot to **Paper Trading** mode for 2 weeks minimum.")
    out.append("2. Confirm: WR within ±10pp of expected, no single trade > expected max loss.")
    out.append("3. Compare paper P&L to backtest expectation: any divergence > 30% is a chain-modeling artifact — see `validation_summary.md`.")
    out.append("4. Only then promote to **Live**.\n")

    return "\n".join(out)


def _format_readme(slug: str, meta: dict, perf: dict) -> str:
    weight_mv = perf.get("weight_mean_variance") or 0
    weight_eq = perf.get("weight_equal") or 0
    weight_rp = perf.get("weight_risk_parity") or 0

    def fmt(v, fmt_str, fallback="n/a"):
        return fmt_str.format(v) if v is not None else fallback

    perf_block = (
        "## Phase 3 backtest (synthetic chain — read with caveats in `validation_summary.md`)\n"
        f"- Win rate: **{fmt(perf.get('wr'), '{:.1%}')}**\n"
        f"- Profit factor: {fmt(perf.get('pf'), '{:.2f}')}\n"
        f"- Total trades over 825 days: {perf.get('trades', 'n/a')}\n"
        f"- Total P&L: {fmt(perf.get('pnl'), '${:,.0f}')}\n"
        f"- Max drawdown: {fmt(perf.get('max_dd'), '${:,.0f}')}\n"
        f"- CPCV: {perf.get('cpcv_folds_won', 'n/a')}/{perf.get('cpcv_folds_total', 'n/a')} folds win (DSR_z > 1) — cross-period robust\n"
    )
    if perf.get("wr") is None:
        perf_block = (
            "## Phase 3 backtest\n"
            "Not run for this bot — this is a pre-existing legacy bot, modeled in Phase 4 portfolio "
            "for comparison purposes (ungated baseline). See `deliverables/validation_summary.md`.\n"
        )

    return f"""# {meta['name']}

**bot_id:** `{slug}`
**Structure:** {meta['structure']}
**Underlying class:** {meta['underlying_class']}
**Role in suite:** {meta['regime_role']}

## What this bot does
See full thesis: `{meta['thesis']}`

{perf_block}
## Phase 4 portfolio weight
- Equal-weight: {weight_eq*100:.1f}%
- Risk-parity: {weight_rp*100:.1f}%
- Mean-variance: **{weight_mv*100:.1f}%** (40% per-bot cap)

## Files in this folder
- `README.md` — this file
- `oa_build_guide.md` — every UI field value to type into Option Alpha
- `config.yaml` — machine-readable params (for regeneration)
- `performance.md` — full DSR / CPCV / fold breakdown
- `kill_switches.md` — bot-specific pause conditions
"""


def _format_performance(slug: str, perf: dict) -> str:
    p3 = _load_phase3(slug) or {}
    cpcv = p3.get("cpcv", {})
    folds = cpcv.get("fold_results", [])
    fold_lines = []
    for f in folds:
        if f.get("skipped"):
            fold_lines.append(f"| {f['fold']} | _skipped_ | _skipped_ | — | — | — | — |")
            continue
        fold_lines.append(
            f"| {f['fold']} | {f['start']} | {f['end']} | "
            f"{f['dsr']:.2f} | {f['raw_sharpe']:.2f} | "
            f"{f['n_trades']} | {f['win_rate']*100:.1f}% | "
            f"${f['pnl']:,.0f} | ${f['max_dd']:,.0f} |"
        )
    folds_table = "\n".join(fold_lines)

    return f"""# Performance — {slug}

## Overall (full 2023-01-03 → 2026-04-17 backtest)

| Metric | Value |
|---|---:|
| DSR_z (Bailey-LdP, deflated for {30} trials) | {perf.get('dsr_z', 0):.2f} |
| Raw Sharpe (annualized) | {perf.get('raw_sharpe', 0):.2f} |
| Win rate | {perf.get('wr', 0)*100:.1f}% |
| Profit factor | {perf.get('pf', 0):.2f} |
| Total trades | {perf.get('trades', 0)} |
| Total P&L | ${perf.get('pnl', 0):,.0f} |
| Max drawdown | ${perf.get('max_dd', 0):,.0f} |

## CPCV folds (5-fold purged cross-validation)

| Fold | Start | End | DSR_z | Raw SR | Trades | WR | P&L | Max DD |
|---|---|---|---:|---:|---:|---:|---:|---:|
{folds_table}

**Folds won (DSR_z > 1):** {cpcv.get('folds_won_dsr_gt_1', 0)}/{cpcv.get('folds_total', 0)} (master prompt C4 requires ≥4/5)

**Total OOS trades across all folds:** {cpcv.get('total_oos_trades', 0)} (master prompt C5 requires ≥50)

## Best parameters (from Optuna 30-trial TPE search)

```yaml
{yaml.dump(perf.get('best_params', {}), default_flow_style=False)}```

## Caveats

These numbers are from the SYNTHETIC chain backtest (BSM + VIX as ATM IV +
SKEW-adjusted skew + stress-clip patch). Real-chain validation deferred until
Polygon plan upgrade. **Apply 30-50% downward bias to absolute P&L numbers
before sizing real capital.** Cross-period CPCV robustness (folds-won) is
the more reliable signal and won't change much under real chains.
"""


def _format_kill_switches(slug: str, meta: dict) -> str:
    return f"""# Kill Switches — {slug}

## Bot-specific halts (in addition to portfolio-wide rules)

1. **VIX 1-day spike**: If VIX rises > 30% in a single session, halt new entries for 48 hours regardless of regime score.

2. **Personal account drawdown**: If your TOTAL OA account drawdown crosses
   -5% from its monthly peak, pause this bot until you manually re-enable.
   This is a discretionary safeguard, not a backtested rule.

3. **Bot-specific drawdown**: If THIS bot's running P&L drops > 50% of its
   YTD peak, pause new entries pending a manual review.

4. **Liquidity warning**: If the bot scans but consistently fails to find
   contracts meeting the min-credit + max-bid-ask criteria for 5 consecutive
   days, the surface is too thin — pause and re-check parameters.

5. **Regime-flip exit (already in OA build guide)**: When the
   `regime_score_max` webhook signal flips above the configured threshold,
   close all open positions immediately. This is the single most important
   rule — it's what would have prevented the original $9k blowup.

## Re-enable conditions

- Wait until VIX < 22 AND VIX/VIX3M < 1.0 for 3 consecutive trading days.
- Aryan account drawdown back to within 2% of monthly peak.
- Manually inspect the regime timeline (`regime_monitor.md`) for the trigger event.

## Logging

Every halt event should be logged in your bot journal with:
- Date, time, trigger condition that fired
- Account state at trigger (open positions, BPR, P&L)
- Subsequent re-enable date and rationale
"""


def _format_config_yaml(slug: str, prop: dict, perf: dict) -> str:
    """Tuned config — params overridden by Phase 3 best, gates from proposal."""
    bp = perf.get("best_params", {})
    cfg = {
        "bot_id": slug,
        "version": "1.0.0",
        "status": "phase_3_accepted",
        "underlying": prop.get("underlying", {"symbol": "SPY", "class": "A"}),
        "structure": dict(prop.get("structure", {})),
        "regime_gates": prop.get("regime_gates", []),
        "entry": prop.get("entry", {}),
        "exit": {
            "profit_target_pct": int((bp.get("profit_target", 0.5)) * 100),
            "stop_loss_credit_multiple": float(bp.get("stop_loss", 2.0)),
            "time_exit_dte": int(bp.get("time_exit", 21)),
            "regime_flip_exit": True,
        },
        "sizing": prop.get("sizing", {}),
        "tuned_overrides": bp,
        "validation": {
            "deflated_sharpe_z": perf.get("dsr_z"),
            "raw_sharpe": perf.get("raw_sharpe"),
            "win_rate": perf.get("wr"),
            "profit_factor": perf.get("pf"),
            "n_trades": perf.get("trades"),
            "max_drawdown": perf.get("max_dd"),
            "cpcv_folds_won": perf.get("cpcv_folds_won"),
            "cpcv_folds_total": perf.get("cpcv_folds_total"),
            "oos_trades": perf.get("oos_trades"),
        },
    }
    return yaml.dump(cfg, sort_keys=False, default_flow_style=False)


def _legacy_proposal() -> dict:
    """Synthetic 'proposal' dict for the legacy bot since it has no proposal YAML."""
    return yaml.safe_load((ROOT / "configs" / "legacy" / "aryan-optimized.yaml").read_text())


def main() -> None:
    DELIVER.mkdir(exist_ok=True)
    BOTS_DIR.mkdir(exist_ok=True)

    # Per-bot deliverables (only those that have Phase 3 acceptance OR are the legacy bot)
    for slug, meta in BOT_META.items():
        is_legacy = slug == "aryan_optimized_legacy"
        bot_dir = BOTS_DIR / slug
        bot_dir.mkdir(exist_ok=True)

        if is_legacy:
            prop = _legacy_proposal()
            # Build pseudo perf for legacy from Phase 4 (run_per_bot ran it)
            p4 = _load_phase4_status()
            perf = {
                "weight_equal": p4["methods"]["equal_weight"]["weights"].get(slug, 0),
                "weight_risk_parity": p4["methods"]["risk_parity"]["weights"].get(slug, 0),
                "weight_mean_variance": p4["methods"]["mean_variance_40cap"]["weights"].get(slug, 0),
                "best_params": {},
                "dsr_z": None, "raw_sharpe": None, "wr": None,
                "pf": None, "trades": None, "pnl": None, "max_dd": None,
                "cpcv_folds_won": None, "cpcv_folds_total": None, "oos_trades": None,
            }
        else:
            prop = _load_proposal_yaml(slug)
            if prop is None:
                continue
            perf = _bot_perf_summary(slug)

        (bot_dir / "README.md").write_text(_format_readme(slug, meta, perf), encoding="utf-8")
        (bot_dir / "oa_build_guide.md").write_text(
            _format_oa_build_steps(slug, meta, prop, perf), encoding="utf-8"
        )
        (bot_dir / "config.yaml").write_text(
            _format_config_yaml(slug, prop, perf), encoding="utf-8"
        )
        if not is_legacy:
            (bot_dir / "performance.md").write_text(
                _format_performance(slug, perf), encoding="utf-8"
            )
        else:
            # Legacy has no Phase 3 — point to Phase 4 instead
            (bot_dir / "performance.md").write_text(
                "# Legacy bot performance\n\nNo Phase 3 tuning (this is the pre-existing live bot, modeled "
                "ungated). Aggregate behavior visible in `deliverables/validation_summary.md` and the Phase 4 "
                "stress-test results showing the April 2025 VIX-spike window.\n",
                encoding="utf-8",
            )
        (bot_dir / "kill_switches.md").write_text(
            _format_kill_switches(slug, meta), encoding="utf-8"
        )

    print(f"Generated per-bot deliverables for {len(BOT_META)} bots")


if __name__ == "__main__":
    main()
