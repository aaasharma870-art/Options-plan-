"""Daily-bar backtest engine for credit-spread strategies.

Loop: each trading day, run gate check → if pass, attempt entry → mark all
open positions → check exits → record. P&L all in Decimal.

Design constraints from PROJECT_BRIEF.md:
  C8 no look-ahead: entries fill at T+1 open (or T close with strict as-of).
     This implementation uses T close with as-of: every signal computed at
     time T uses ONLY data with timestamp <= T. The synthetic chain provider
     enforces this — its `_underlying_close(_, as_of)` uses .loc[:ts].iloc[-1].
  C9 Decimal P&L: every cashflow uses Decimal.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Iterable

import pandas as pd

from delta_optimizer.regime.score import score_dataframe, ScoreThresholds
from delta_optimizer.strategies.base import Position
from delta_optimizer.strategies.iron_condor import (
    IronCondorParams,
    build_iron_condor,
)
from delta_optimizer.strategies.synthetic_chain import SyntheticBSMChain

log = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    entry_date: str
    exit_date: str
    structure: str
    underlying: str
    expiration: str
    credit: Decimal
    max_loss: Decimal
    pnl: Decimal
    exit_reason: str
    days_held: int
    metadata: dict = field(default_factory=dict)


@dataclass
class GateConfig:
    """Phase 2 benchmark gate configuration."""

    vix_max: float | None = None
    vix_vix3m_max: float | None = None
    vix_10d_high_max: float | None = None
    vix_1d_change_max: float | None = None
    ivp_min: float | None = None

    def passes(self, row: pd.Series) -> bool:
        if self.vix_max is not None and row.get("vix_close", float("inf")) > self.vix_max:
            return False
        if (
            self.vix_vix3m_max is not None
            and row.get("vix_vix3m", 0.0) > self.vix_vix3m_max
        ):
            return False
        if (
            self.vix_10d_high_max is not None
            and row.get("vix_10d_high", float("inf")) > self.vix_10d_high_max
        ):
            return False
        if self.vix_1d_change_max is not None:
            v = row.get("vix_1d_change")
            if v is not None and not pd.isna(v) and abs(v) > self.vix_1d_change_max:
                return False
        if self.ivp_min is not None and row.get("vix_ivp_252d", 0.0) < self.ivp_min:
            return False
        return True

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class StrategyConfig:
    """Iron condor benchmark per PROJECT_BRIEF.md Phase 2 § Benchmark."""

    short_call_delta: float = 0.16
    long_call_delta: float = 0.05
    short_put_delta: float = 0.16
    long_put_delta: float = 0.05
    dte_min: int = 30
    dte_max: int = 45
    profit_target_pct: float = 0.50  # 50% of credit
    stop_loss_credit_multiple: float = 2.0  # close at -2x credit
    time_exit_dte: int = 21
    max_concurrent: int = 3
    qty_per_leg: int = 1
    underlying: str = "SPY"


@dataclass
class BacktestResult:
    trades: list[TradeRecord]
    gate_pass_days: int
    gate_total_days: int
    pnl_total: Decimal
    pnl_per_day_blocked_zero: Decimal  # expectancy / day, blocked = $0
    win_rate: float
    profit_factor: float
    max_drawdown: Decimal
    cvar_95: Decimal  # mean of worst 5% trading-day P&Ls
    worst_5_days: list[tuple[str, Decimal]]

    def to_dict(self) -> dict:
        return {
            "n_trades": len(self.trades),
            "gate_pass_days": self.gate_pass_days,
            "gate_total_days": self.gate_total_days,
            "gate_pass_rate": (
                self.gate_pass_days / self.gate_total_days
                if self.gate_total_days else 0
            ),
            "pnl_total": float(self.pnl_total),
            "pnl_per_day": float(self.pnl_per_day_blocked_zero),
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": float(self.max_drawdown),
            "cvar_95": float(self.cvar_95),
            "worst_5_days": [(d, float(p)) for d, p in self.worst_5_days],
        }


def _trading_days(feature_df: pd.DataFrame) -> list[pd.Timestamp]:
    return list(feature_df.index)


def _next_business_day_after(ts: pd.Timestamp, days: int) -> pd.Timestamp:
    return ts + pd.tseries.offsets.BDay(days)


def _approximate_expiration(entry_ts: pd.Timestamp, dte_min: int, dte_max: int) -> date:
    """Pick expiration in the [dte_min, dte_max] window. SPY has weeklies on
    every Friday — we choose the Friday closest to (entry + (dte_min+dte_max)/2)."""
    target_days = (dte_min + dte_max) // 2
    target = entry_ts + timedelta(days=target_days)
    # Snap to the next Friday at or after target.
    days_until_friday = (4 - target.weekday()) % 7
    expiry = (target + timedelta(days=days_until_friday)).date()
    return expiry


def run_backtest(
    feature_df: pd.DataFrame,
    chain: SyntheticBSMChain,
    gate: GateConfig,
    strategy: StrategyConfig,
    *,
    log_progress: bool = False,
) -> BacktestResult:
    """Walk every trading day. Open IC if gate passes. Mark/exit per strategy."""
    open_positions: list[tuple[Position, pd.Timestamp]] = []
    trades: list[TradeRecord] = []
    gate_pass_days = 0
    daily_pnl: dict[pd.Timestamp, Decimal] = {}

    days = _trading_days(feature_df)
    for i, ts in enumerate(days):
        row = feature_df.loc[ts]
        # 1. Mark + exit existing
        survived: list[tuple[Position, pd.Timestamp]] = []
        for pos, opened_ts in open_positions:
            current_value = chain.mark_position(pos.legs, ts.date())
            # P&L = credit (already received) + current_value (negative for short)
            # Wait — mark_position returns the position's current per-share Decimal *value*.
            # For an iron condor we OPEN with credit > 0 (we received $X). To CLOSE we'd PAY
            # the current absolute value. So unrealized P&L = credit + current_value.
            unrealized = pos.credit + current_value
            credit = pos.credit
            exit_reason: str | None = None
            # Profit target: closed when unrealized >= profit_target_pct * credit
            if unrealized >= credit * Decimal(str(strategy.profit_target_pct)):
                exit_reason = "profit_target"
            # Stop loss: unrealized <= -stop_loss_credit_multiple * credit
            elif unrealized <= -credit * Decimal(str(strategy.stop_loss_credit_multiple)):
                exit_reason = "stop_loss"
            else:
                # Time exit
                exp = datetime.strptime(pos.expiration, "%Y-%m-%d").date()
                dte = (exp - ts.date()).days
                if dte <= strategy.time_exit_dte:
                    exit_reason = "time_exit"

            if exit_reason is not None:
                pnl = unrealized
                trades.append(
                    TradeRecord(
                        entry_date=str(opened_ts.date()),
                        exit_date=str(ts.date()),
                        structure=pos.structure,
                        underlying=pos.underlying,
                        expiration=pos.expiration,
                        credit=credit,
                        max_loss=pos.max_loss,
                        pnl=pnl,
                        exit_reason=exit_reason,
                        days_held=(ts.date() - opened_ts.date()).days,
                        metadata=pos.metadata,
                    )
                )
                daily_pnl[ts] = daily_pnl.get(ts, Decimal(0)) + pnl
            else:
                survived.append((pos, opened_ts))
        open_positions = survived

        # 2. Gate check
        if not gate.passes(row):
            continue
        gate_pass_days += 1

        # 3. Attempt entry
        if len(open_positions) >= strategy.max_concurrent:
            continue

        expiration = _approximate_expiration(ts, strategy.dte_min, strategy.dte_max)
        params = IronCondorParams(
            short_call_delta=strategy.short_call_delta,
            long_call_delta=strategy.long_call_delta,
            short_put_delta=strategy.short_put_delta,
            long_put_delta=strategy.long_put_delta,
            qty_per_leg=strategy.qty_per_leg,
            use_mid=True,
        )

        # Inject as_of into chain provider for find_by_delta
        class _Bound:
            def __init__(self, chain, as_of_str):
                self._c = chain
                self._as_of = as_of_str

            def find_by_delta(self, underlying, expiration, option_type, target_delta):
                return self._c.find_by_delta(
                    underlying, expiration, option_type, target_delta,
                    as_of=self._as_of,
                )

        bound = _Bound(chain, str(ts.date()))
        try:
            ic = build_iron_condor(
                strategy.underlying, str(ts.date()), expiration.isoformat(), bound, params
            )
        except (ValueError, TypeError) as e:
            log.debug("entry skipped %s: %s", ts.date(), e)
            ic = None

        if ic is not None and ic.credit > 0:
            open_positions.append((ic, ts))

    # 4. Close anything still open at end of backtest at last mark
    final_ts = days[-1]
    for pos, opened_ts in open_positions:
        current_value = chain.mark_position(pos.legs, final_ts.date())
        pnl = pos.credit + current_value
        trades.append(
            TradeRecord(
                entry_date=str(opened_ts.date()),
                exit_date=str(final_ts.date()),
                structure=pos.structure,
                underlying=pos.underlying,
                expiration=pos.expiration,
                credit=pos.credit,
                max_loss=pos.max_loss,
                pnl=pnl,
                exit_reason="backtest_end",
                days_held=(final_ts.date() - opened_ts.date()).days,
                metadata=pos.metadata,
            )
        )
        daily_pnl[final_ts] = daily_pnl.get(final_ts, Decimal(0)) + pnl

    # 5. Aggregate metrics
    pnl_total = sum((t.pnl for t in trades), Decimal(0))
    n_winners = sum(1 for t in trades if t.pnl > 0)
    n_losers = sum(1 for t in trades if t.pnl < 0)
    win_rate = (n_winners / len(trades)) if trades else 0.0
    gross_win = sum((t.pnl for t in trades if t.pnl > 0), Decimal(0))
    gross_loss = abs(sum((t.pnl for t in trades if t.pnl < 0), Decimal(0)))
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")

    # Per-day P&L series (filled-zero for non-event days, used for DD/CVaR)
    pnl_series = pd.Series(
        [float(daily_pnl.get(ts, Decimal(0))) for ts in days], index=days
    )
    equity = pnl_series.cumsum()
    drawdown = equity.cummax() - equity
    max_dd = Decimal(str(round(drawdown.max(), 2)))
    sorted_pnl = pnl_series.sort_values()
    cutoff = max(int(len(sorted_pnl) * 0.05), 1)
    cvar = Decimal(str(round(float(sorted_pnl.iloc[:cutoff].mean()), 2)))
    worst_5 = [
        (str(ts.date()), Decimal(str(round(p, 2))))
        for ts, p in sorted_pnl.head(5).items()
    ]

    pnl_per_day = pnl_total / Decimal(len(days)) if days else Decimal(0)

    return BacktestResult(
        trades=trades,
        gate_pass_days=gate_pass_days,
        gate_total_days=len(days),
        pnl_total=pnl_total,
        pnl_per_day_blocked_zero=pnl_per_day,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown=max_dd,
        cvar_95=cvar,
        worst_5_days=worst_5,
    )
