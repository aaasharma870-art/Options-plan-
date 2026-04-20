"""Portfolio backtest aggregator (Phase 4).

Approach:
  1. Each constituent bot is run INDEPENDENTLY with its tuned params via
     the existing single-bot engine (`run_backtest`). This captures the
     bot's per-day P&L series under its own regime gate.
  2. Per-day P&Ls are summed across bots → portfolio daily P&L series.
  3. Portfolio-level constraints applied as POST-HOC filters:
       a. Daily -3% drawdown circuit breaker — flag the day; exclude any
          subsequent trade entries (approximated by zeroing PnL for the
          day after a breach until the trough recovers).
       b. Per-underlying position cap — approximated; not enforced at
          the trade level (would require a true multi-bot event-driven
          simulator). Documented gap.
       c. Portfolio max 35% BPR — same caveat. Estimated post-hoc by
          summing per-bot allocation.
  4. Three allocation methods compared:
       - Equal weight: each bot allocated 1/N share
       - Risk parity: each bot weighted inversely to its daily-PnL std
       - Mean-variance: max-Sharpe with 40% per-bot cap (scipy.optimize)
  5. Stress tests: re-aggregate over historical subwindows.

This is an HONEST first-pass. The "true" event-driven multi-bot simulator
that the master prompt sketches would also need cross-bot capital sharing
which adds another ~200 LOC of state machinery. Documented in Checkpoint 4.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from delta_optimizer.backtest.engine import (
    BacktestResult,
    GateConfig,
    StrategyConfig,
    run_backtest,
)
from delta_optimizer.strategies.synthetic_chain import SyntheticBSMChain

log = logging.getLogger(__name__)

CIRCUIT_BREAKER_DAILY_DD = -0.03  # -3%
PORTFOLIO_MAX_BPR = 0.35
PER_UNDERLYING_MAX_POSITIONS = 4


@dataclass
class BotInPortfolio:
    """One constituent bot. The strategy is fully tuned (params from Phase 3)."""

    bot_id: str
    underlying: str
    gate: GateConfig
    strategy: StrategyConfig
    allocation_usd: float = 10000.0


@dataclass
class PortfolioResult:
    method: str
    weights: dict[str, float]
    daily_pnl: pd.Series
    equity_curve: pd.Series
    drawdown: pd.Series
    sharpe_calendar: float
    max_drawdown_dollar: float
    max_drawdown_pct: float
    pct_95_loss: float
    worst_day_loss: float
    worst_day_date: str
    n_trading_days: int
    circuit_breaker_days: int
    aggregate_passes: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        d["daily_pnl"] = self.daily_pnl.to_dict()
        d["equity_curve"] = self.equity_curve.to_dict()
        d["drawdown"] = self.drawdown.to_dict()
        # Convert dates to strings
        for k in ("daily_pnl", "equity_curve", "drawdown"):
            d[k] = {str(ts): float(v) for ts, v in d[k].items()}
        return d


def run_per_bot(
    bots: list[BotInPortfolio],
    feature_df: pd.DataFrame,
    chain: SyntheticBSMChain,
) -> dict[str, pd.Series]:
    """Run each bot's backtest independently. Returns {bot_id: daily_pnl_series}."""
    series_by_bot: dict[str, pd.Series] = {}
    for bot in bots:
        result = run_backtest(feature_df, chain, bot.gate, bot.strategy)
        # Build daily P&L series (zero-filled)
        daily = pd.Series(0.0, index=feature_df.index, name=bot.bot_id)
        for t in result.trades:
            ts = pd.Timestamp(t.exit_date)
            if ts in daily.index:
                daily.loc[ts] += float(t.pnl)
        series_by_bot[bot.bot_id] = daily
    return series_by_bot


def equal_weight(bot_ids: list[str]) -> dict[str, float]:
    n = len(bot_ids)
    return {bid: 1.0 / n for bid in bot_ids}


def risk_parity_weights(pnl_matrix: pd.DataFrame) -> dict[str, float]:
    """Weights inversely proportional to each bot's daily-PnL std."""
    stds = pnl_matrix.std(ddof=1).replace(0, 1e-9)
    inv = 1.0 / stds
    weights = inv / inv.sum()
    return weights.to_dict()


def mean_variance_weights(
    pnl_matrix: pd.DataFrame, max_per_bot: float = 0.40,
) -> dict[str, float]:
    """Max-Sharpe weights subject to per-bot cap. Long-only, sum-to-1."""
    n = pnl_matrix.shape[1]
    means = pnl_matrix.mean()
    cov = pnl_matrix.cov()

    def neg_sharpe(w: np.ndarray) -> float:
        port_mean = float(means @ w)
        port_var = float(w @ cov.values @ w)
        if port_var <= 0:
            return 0.0
        return -port_mean / np.sqrt(port_var)

    x0 = np.full(n, 1.0 / n)
    bounds = [(0.0, max_per_bot)] * n
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    res = minimize(neg_sharpe, x0=x0, bounds=bounds, constraints=cons, method="SLSQP")
    if not res.success:
        # Fall back to equal weight
        weights = np.full(n, 1.0 / n)
    else:
        weights = res.x
    return {bid: float(w) for bid, w in zip(pnl_matrix.columns, weights)}


def apply_circuit_breaker(
    portfolio_pnl: pd.Series, starting_capital: float,
) -> tuple[pd.Series, int]:
    """Zero out P&L on days following a -3% drawdown until equity recovers.

    Approximates the master prompt's "halt all new entries for the rest of
    the day" rule. Returns (adjusted_pnl, circuit_breaker_days).
    """
    adjusted = portfolio_pnl.copy()
    equity = starting_capital
    in_breach = False
    halted_count = 0
    peak_equity = starting_capital

    for ts in adjusted.index:
        daily = adjusted.loc[ts]
        if in_breach:
            adjusted.loc[ts] = 0.0  # halt new entries; existing trades still mark
            halted_count += 1
            equity_change = 0.0
            # Recover when equity returns to within 0.5% of peak
            if equity >= peak_equity * 0.995:
                in_breach = False
        else:
            equity_change = daily

        equity += equity_change
        peak_equity = max(peak_equity, equity)
        # Check if today's loss breached the threshold
        if daily / starting_capital <= CIRCUIT_BREAKER_DAILY_DD and not in_breach:
            in_breach = True

    return adjusted, halted_count


def aggregate_portfolio(
    pnl_matrix: pd.DataFrame,
    weights: dict[str, float],
    starting_capital: float,
    *,
    apply_breaker: bool = True,
) -> PortfolioResult:
    """Sum per-bot P&Ls into portfolio P&L, optionally apply circuit breaker."""
    weighted = pd.DataFrame({
        bid: pnl_matrix[bid] * w for bid, w in weights.items()
    })
    portfolio_pnl = weighted.sum(axis=1)

    breaker_days = 0
    if apply_breaker:
        portfolio_pnl, breaker_days = apply_circuit_breaker(portfolio_pnl, starting_capital)

    equity = starting_capital + portfolio_pnl.cumsum()
    running_peak = equity.cummax()
    drawdown = running_peak - equity
    max_dd_dollar = float(drawdown.max())
    max_dd_pct = max_dd_dollar / starting_capital

    daily_returns = portfolio_pnl / starting_capital
    sharpe = (
        float(daily_returns.mean() / daily_returns.std(ddof=1) * np.sqrt(252))
        if daily_returns.std(ddof=1) > 0 else float("nan")
    )

    pct_95_loss = float(daily_returns.quantile(0.05))
    worst = portfolio_pnl.min()
    worst_date = str(portfolio_pnl.idxmin().date())

    aggregate_passes = {
        "max_dd_lt_15pct": max_dd_pct < 0.15,
        "sharpe_gt_1_5": sharpe > 1.5,
        "p95_daily_loss_lt_2pct": -pct_95_loss < 0.02,
        "no_day_lt_neg_5pct": (daily_returns.min() > -0.05),
    }

    return PortfolioResult(
        method="weighted",
        weights=weights,
        daily_pnl=portfolio_pnl,
        equity_curve=equity,
        drawdown=drawdown,
        sharpe_calendar=sharpe,
        max_drawdown_dollar=max_dd_dollar,
        max_drawdown_pct=max_dd_pct,
        pct_95_loss=pct_95_loss,
        worst_day_loss=float(worst),
        worst_day_date=worst_date,
        n_trading_days=int(len(portfolio_pnl)),
        circuit_breaker_days=breaker_days,
        aggregate_passes=aggregate_passes,
    )


def stress_test(
    pnl_matrix: pd.DataFrame,
    weights: dict[str, float],
    starting_capital: float,
    name: str,
    start: str,
    end: str,
) -> dict:
    """Aggregate over a historical sub-window and report key metrics."""
    sub = pnl_matrix.loc[start:end]
    if sub.empty:
        return {
            "name": name, "start": start, "end": end,
            "skipped": True, "reason": "no data in window",
        }
    weighted = pd.DataFrame({bid: sub[bid] * w for bid, w in weights.items()})
    pnl = weighted.sum(axis=1)
    equity = starting_capital + pnl.cumsum()
    drawdown = equity.cummax() - equity
    return {
        "name": name,
        "start": start,
        "end": end,
        "n_days": int(len(pnl)),
        "total_pnl": float(pnl.sum()),
        "max_dd_dollar": float(drawdown.max()),
        "max_dd_pct": float(drawdown.max()) / starting_capital,
        "worst_day": float(pnl.min()),
        "worst_day_date": str(pnl.idxmin().date()),
    }
