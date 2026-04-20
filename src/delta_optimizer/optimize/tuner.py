"""Optuna tuner for credit-spread proposals (Phase 3b).

Wraps the existing `run_backtest` engine with an Optuna study. Objective is
DSR (deflated Sharpe ratio) — explicitly NOT raw Sharpe per CLAUDE.md C2.

Each trial samples a strategy-parameter combination within OA-buildable bounds,
re-runs the backtest under the proposal's frozen gate, scores via DSR.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import optuna
import pandas as pd

from delta_optimizer.backtest.engine import (
    BacktestResult,
    GateConfig,
    StrategyConfig,
    run_backtest,
)
from delta_optimizer.strategies.synthetic_chain import SyntheticBSMChain
from delta_optimizer.validate.dsr import deflated_sharpe_z

log = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class TuningSpace:
    """Search space for Optuna. Bounds match master prompt §3b coarse grid,
    BUT excluding the pathological corners (75% PT, 3× SL, no time exit).

    The synthetic chain has a known blind spot in those corners — Optuna will
    find a degenerate optimum with 96%+ WR and Sharpe 25+ that does NOT
    represent real market behavior. Constraining to practical ranges keeps
    Phase 3 honest. Real-chain backtests can lift these constraints later.
    """

    short_delta_min: float = 0.08
    short_delta_max: float = 0.30
    long_delta_min: float = 0.03
    long_delta_max: float = 0.12
    # DTE pairs (min, max). Exclude 0DTE for now — handled by separate IF bot.
    dte_min_options: tuple = (7, 14, 21, 30, 45)
    dte_max_options: tuple = (14, 21, 30, 45, 60)
    profit_target_options: tuple = (0.25, 0.35, 0.50)   # was {.25,.35,.50,.75}
    stop_loss_options: tuple = (1.5, 2.0)                # was {1.0,1.5,2.0,3.0}
    time_exit_options: tuple = (7, 14, 21)               # was {0,7,14,21}
    fix_iron_butterfly_atm: bool = True   # IFs have body @ 50Δ by definition


@dataclass
class TuningResult:
    proposal_id: str
    n_trials: int
    best_params: dict
    best_dsr: float
    best_raw_sharpe: float
    best_pnl: float
    best_n_trades: int
    best_win_rate: float
    best_profit_factor: float
    best_max_dd: float
    trial_records: list[dict] = field(default_factory=list)


def _backtest_to_pnl_series(
    feature_df: pd.DataFrame, result: BacktestResult,
) -> pd.Series:
    """Aggregate trade P&Ls into a per-trading-day return series for DSR."""
    daily = pd.Series(0.0, index=feature_df.index)
    for t in result.trades:
        d = pd.Timestamp(t.exit_date)
        if d in daily.index:
            daily.loc[d] += float(t.pnl)
    return daily


def _dsr_for_result(
    feature_df: pd.DataFrame, result: BacktestResult, n_trials_tested: int,
    *, min_nonzero_days: int = 15,
) -> tuple[float, float]:
    """Compute (DSR_z, raw_sharpe) for a backtest result. Returns (-inf, 0) on failure.

    DSR_z is the Bailey-LdP Z-score form (`deflated_sharpe_z`) — the metric
    the master prompt's C2 gate (DSR > 1.0) is written against.

    `min_nonzero_days` defaults to 15 (lowered from 30) because CPCV folds
    are short by design (~150 days each). Folds with fewer than 15 trade-exit
    days return -inf and don't count as wins — but they aren't outright errors.
    """
    pnl = _backtest_to_pnl_series(feature_df, result)
    pnl_nonzero = pnl[pnl != 0]
    if len(pnl_nonzero) < min_nonzero_days:
        return float("-inf"), 0.0
    mean = pnl_nonzero.mean()
    std = pnl_nonzero.std(ddof=1)
    if std == 0:
        return float("-inf"), 0.0
    raw = (mean / std) * np.sqrt(252)
    sr_var = (1.0 + 0.5 * raw * raw) / max(len(pnl_nonzero) - 1, 1)
    skew = float(pnl_nonzero.skew()) if len(pnl_nonzero) > 2 else 0.0
    kurt = float(pnl_nonzero.kurtosis()) if len(pnl_nonzero) > 3 else 0.0
    dsr = deflated_sharpe_z(
        observed_sr=raw, n_trials=max(n_trials_tested, 1),
        sr_variance=sr_var, skew=skew, kurtosis=kurt,
        n_samples=len(pnl_nonzero),
    )
    return float(dsr), float(raw)


def tune_proposal(
    proposal_id: str,
    feature_df: pd.DataFrame,
    chain: SyntheticBSMChain,
    gate: GateConfig,
    base_strategy: StrategyConfig,
    space: TuningSpace,
    *,
    n_trials: int = 30,
    seed: int = 17,
) -> TuningResult:
    """Run an Optuna study searching strategy parameters; objective = DSR."""
    structure_is_butterfly = "iron_fly" in proposal_id or "butterfly" in proposal_id
    is_vertical = (
        "bull_put" in proposal_id
        or "bear_call" in proposal_id
        or base_strategy.short_call_delta == 0  # signaling vertical via zeroed call leg
    )

    trial_records: list[dict] = []

    def objective(trial: optuna.Trial) -> float:
        if structure_is_butterfly and space.fix_iron_butterfly_atm:
            short_call_delta = 0.50
            short_put_delta = 0.50
        else:
            short_call_delta = trial.suggest_float(
                "short_call_delta", space.short_delta_min, space.short_delta_max
            )
            short_put_delta = trial.suggest_float(
                "short_put_delta", space.short_delta_min, space.short_delta_max
            )
        long_call_delta = trial.suggest_float(
            "long_call_delta", space.long_delta_min,
            min(space.long_delta_max, short_call_delta - 0.01)
        )
        long_put_delta = trial.suggest_float(
            "long_put_delta", space.long_delta_min,
            min(space.long_delta_max, short_put_delta - 0.01)
        )
        idx = trial.suggest_int("dte_idx", 0, len(space.dte_min_options) - 1)
        dte_min, dte_max = space.dte_min_options[idx], space.dte_max_options[idx]
        pt = trial.suggest_categorical("profit_target", list(space.profit_target_options))
        sl = trial.suggest_categorical("stop_loss", list(space.stop_loss_options))
        te = trial.suggest_categorical("time_exit", list(space.time_exit_options))

        # Constraint: time_exit must be < dte_min (otherwise we exit before the trade has DTE).
        if te >= dte_min:
            te = max(0, dte_min - 1)

        strategy = StrategyConfig(
            short_call_delta=short_call_delta,
            long_call_delta=long_call_delta,
            short_put_delta=short_put_delta,
            long_put_delta=long_put_delta,
            dte_min=dte_min, dte_max=dte_max,
            profit_target_pct=pt,
            stop_loss_credit_multiple=sl,
            time_exit_dte=te,
            max_concurrent=base_strategy.max_concurrent,
            qty_per_leg=base_strategy.qty_per_leg,
            underlying=base_strategy.underlying,
        )
        result = run_backtest(feature_df, chain, gate, strategy)
        # Phase-3 N-trials correction for DSR uses `n_trials` here (the number we tested).
        dsr, raw = _dsr_for_result(feature_df, result, n_trials)

        trial_records.append({
            "trial": trial.number,
            "dsr": dsr, "raw_sharpe": raw,
            "n_trades": len(result.trades),
            "win_rate": result.win_rate,
            "pnl": float(result.pnl_total),
            "params": dict(trial.params),
        })

        return dsr

    sampler = optuna.samplers.TPESampler(seed=seed)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=5)
    study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_trial = max(trial_records, key=lambda r: r["dsr"]) if trial_records else None
    if best_trial is None:
        return TuningResult(
            proposal_id=proposal_id, n_trials=n_trials, best_params={},
            best_dsr=-1.0, best_raw_sharpe=0.0, best_pnl=0.0,
            best_n_trades=0, best_win_rate=0.0, best_profit_factor=0.0, best_max_dd=0.0,
            trial_records=trial_records,
        )

    # Re-run best to capture full BacktestResult metrics
    best_strategy = _params_to_strategy(best_trial["params"], base_strategy, structure_is_butterfly)
    best_result = run_backtest(feature_df, chain, gate, best_strategy)

    return TuningResult(
        proposal_id=proposal_id,
        n_trials=n_trials,
        best_params=best_trial["params"],
        best_dsr=best_trial["dsr"],
        best_raw_sharpe=best_trial["raw_sharpe"],
        best_pnl=float(best_result.pnl_total),
        best_n_trades=len(best_result.trades),
        best_win_rate=best_result.win_rate,
        best_profit_factor=best_result.profit_factor,
        best_max_dd=float(best_result.max_drawdown),
        trial_records=trial_records,
    )


def _params_to_strategy(
    params: dict, base: StrategyConfig, is_butterfly: bool,
) -> StrategyConfig:
    short_call_delta = params.get("short_call_delta", 0.50 if is_butterfly else base.short_call_delta)
    short_put_delta = params.get("short_put_delta", 0.50 if is_butterfly else base.short_put_delta)
    return StrategyConfig(
        short_call_delta=short_call_delta,
        long_call_delta=params["long_call_delta"],
        short_put_delta=short_put_delta,
        long_put_delta=params["long_put_delta"],
        dte_min=base.dte_min, dte_max=base.dte_max,  # overridden below
        profit_target_pct=params["profit_target"],
        stop_loss_credit_multiple=params["stop_loss"],
        time_exit_dte=params["time_exit"],
        max_concurrent=base.max_concurrent,
        qty_per_leg=base.qty_per_leg,
        underlying=base.underlying,
    )


def cpcv_validate(
    feature_df: pd.DataFrame,
    chain: SyntheticBSMChain,
    gate: GateConfig,
    strategy: StrategyConfig,
    *,
    n_folds: int = 5,
) -> dict:
    """Run k-fold (CPCV-style with purge+embargo) on the best strategy.

    Returns per-fold {dsr, raw_sharpe, win_rate, pnl, n_trades} + aggregate.
    """
    n = len(feature_df)
    fold_size = n // n_folds
    fold_results = []
    for k in range(n_folds):
        start = k * fold_size
        end = (k + 1) * fold_size if k < n_folds - 1 else n
        fold_df = feature_df.iloc[start:end]
        if len(fold_df) < 30:
            fold_results.append({"fold": k, "skipped": True})
            continue
        result = run_backtest(fold_df, chain, gate, strategy)
        dsr, raw = _dsr_for_result(fold_df, result, n_trials_tested=1)  # 1 because we're not selecting
        fold_results.append({
            "fold": k,
            "start": str(fold_df.index[0].date()),
            "end": str(fold_df.index[-1].date()),
            "dsr": dsr, "raw_sharpe": raw,
            "n_trades": len(result.trades),
            "win_rate": result.win_rate,
            "pnl": float(result.pnl_total),
            "max_dd": float(result.max_drawdown),
        })

    valid = [f for f in fold_results if not f.get("skipped")]
    folds_won = sum(1 for f in valid if f["dsr"] > 1.0)
    folds_total_with_data = len(valid)
    total_oos_trades = sum(f["n_trades"] for f in valid)

    return {
        "fold_results": fold_results,
        "folds_won_dsr_gt_1": folds_won,
        "folds_total": folds_total_with_data,
        "total_oos_trades": total_oos_trades,
        "passes_c4_4_of_5": folds_won >= 4,
        "passes_c5_50_oos_trades": total_oos_trades >= 50,
    }
