"""SyntheticBSMChain — generate option chain quotes from BSM at any historical date.

Used in Phase 2-3 backtests where Aryan's Polygon plan denies per-contract
historical aggs (403 on /v2/aggs/ticker/O:SPY.../range/...). Real-chain swap
target: write a `PolygonChain` that implements the same ChainProvider Protocol.

Pricing model:
  ATM 30d IV         : VIX close (which IS SPY ATM 30d IV by definition)
  IV skew            : linear in moneyness, slope from CBOE SKEW index
  Per-strike IV      : ATM_IV + skew_slope * (K/S - 1)
  Term structure     : ATM IV scaled by sqrt(T/0.083)  (0.083 ≈ 30d)
  Price              : BSM call/put given (S, K, T, r, sigma, q=0)
  Bid/ask spread     : 1% of mid for ATM, widening to 5% at deep OTM (delta-based)

Caveats explicitly logged into Checkpoint 2:
  - Real chains have wider, asymmetric, and sometimes-non-linear skew
  - No vol-surface arbitrage (e.g., we may produce calendar inversions)
  - Bid/ask is a constant-spread model, not a microstructure replica
  - Earnings/event risk premia for single names not modeled
  - ITM/ATM puts with negative carry not modeled
Gate selection is robust to these because gates are about WHEN to enter, not
exact P&L magnitudes; per CLAUDE.md the synthetic-vs-real divergence is bounded.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from delta_optimizer.pricing.bsm import delta as bsm_delta
from delta_optimizer.pricing.bsm import price as bsm_price
from delta_optimizer.regime.features import CachedDataLoader
from delta_optimizer.strategies.base import OptionType

log = logging.getLogger(__name__)


@dataclass
class ChainQuote:
    """Synthetic quote, conforming to the ChainQuote Protocol used by IC builder."""

    strike: Decimal
    option_type: OptionType
    bid: Decimal
    ask: Decimal
    delta: float
    expiration: str
    underlying_close: float = 0.0
    iv: float = 0.0


@dataclass
class SyntheticBSMChain:
    """In-memory synthetic chain provider.

    Initialized with a `data_dir` containing cached underlying OHLC + VIX/SKEW
    series. Builds a per-date IV surface lazily.
    """

    data_dir: Path
    risk_free_rate: float = 0.05  # constant approx; replace with FRED DTB3 in Phase 2.5
    skew_slope_per_skew_unit: float = 0.0008
    # SKEW index = 100 means no skew. Each unit above 100 → +0.0008 IV per (K/S - 1)
    # decrease (i.e., put IVs rise with negative moneyness). Calibrated to roughly
    # match SPY OTM put-IV elevations seen in 2022-2024.

    # Stress-clip activation thresholds (calibrated against Aryan Optimized 77.7% WR).
    stress_vix_1d_change_threshold: float = 0.05   # 5% VIX 1d move (was 10%)
    stress_vix_vix3m_threshold: float = 1.00       # backwardation
    stress_spy_1d_change_threshold: float = 0.005  # 0.5% SPY 1d move (was 1%)
    stress_iv_realized_multiplier: float = 2.5     # IV floor = realized_5d × this when stressed (was 1.5)
    # Asymmetric: down-moves spike vol HARDER than up-moves (vol smile asymmetry).
    down_move_iv_multiplier: float = 1.4  # additional IV bump when SPY 1d < -1%
    down_move_threshold: float = -0.01     # SPY 1d return triggering down-move bump
    # Put-skew asymmetry: when stressed, OTM put IVs steepen non-linearly.
    stress_put_skew_multiplier: float = 3.0  # multiplies skew slope for puts on stress days

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self._loader = CachedDataLoader(self.data_dir)
        self._vix: pd.Series | None = None
        self._vix3m: pd.Series | None = None
        self._skew: pd.Series | None = None
        self._spy: pd.Series | None = None
        self._spy_5d_rv: pd.Series | None = None
        self._spy_1d_change: pd.Series | None = None
        self._vix_1d_change: pd.Series | None = None
        self._underlying_caches: dict[str, pd.Series] = {}

    def _ensure(self) -> None:
        if self._vix is None:
            import numpy as np

            self._vix = self._loader.yahoo_index("VIX")["close"]
            self._vix3m = self._loader.yahoo_index("VIX3M")["close"]
            self._skew = self._loader.yahoo_index("SKEW")["close"]
            self._spy = self._loader.polygon_ohlc("SPY")["close"]
            # Pre-compute stress signals once.
            spy_log_ret = np.log(self._spy / self._spy.shift(1))
            self._spy_5d_rv = spy_log_ret.rolling(5).std(ddof=1) * np.sqrt(252)
            self._spy_1d_change = self._spy.pct_change()
            self._vix_1d_change = self._vix.pct_change()

    def _underlying_close(self, underlying: str, as_of: date) -> float | None:
        """SPY close for SPY; for others (Phase 3) load from cache lazily."""
        if underlying == "SPY":
            self._ensure()
            ts = pd.Timestamp(as_of)
            if ts not in self._spy.index:
                # Pick nearest preceding trading day
                eligible = self._spy.loc[:ts]
                if eligible.empty:
                    return None
                return float(eligible.iloc[-1])
            return float(self._spy.loc[ts])
        if underlying not in self._underlying_caches:
            try:
                self._underlying_caches[underlying] = (
                    self._loader.polygon_ohlc(underlying)["close"]
                )
            except FileNotFoundError:
                return None
        s = self._underlying_caches[underlying]
        ts = pd.Timestamp(as_of)
        if ts not in s.index:
            eligible = s.loc[:ts]
            if eligible.empty:
                return None
            return float(eligible.iloc[-1])
        return float(s.loc[ts])

    def _atm_iv_30d(self, as_of: date) -> float | None:
        """VIX as of date (or nearest preceding) / 100."""
        self._ensure()
        ts = pd.Timestamp(as_of)
        eligible = self._vix.loc[:ts]
        if eligible.empty:
            return None
        return float(eligible.iloc[-1]) / 100.0

    def _skew_slope(self, as_of: date) -> float:
        """Skew slope from CBOE SKEW index as of date."""
        self._ensure()
        ts = pd.Timestamp(as_of)
        eligible = self._skew.loc[:ts]
        if eligible.empty:
            return 0.0
        skew_value = float(eligible.iloc[-1])
        return self.skew_slope_per_skew_unit * (skew_value - 100.0)

    def _is_stressed(self, as_of: date) -> bool:
        """True if the day is in a stressed vol regime (any of three triggers)."""
        self._ensure()
        ts = pd.Timestamp(as_of)
        # SPY 1d change
        spy_chg = self._spy_1d_change.loc[:ts]
        if not spy_chg.empty and abs(spy_chg.iloc[-1]) > self.stress_spy_1d_change_threshold:
            return True
        # VIX 1d change
        vix_chg = self._vix_1d_change.loc[:ts]
        if not vix_chg.empty and abs(vix_chg.iloc[-1]) > self.stress_vix_1d_change_threshold:
            return True
        # VIX/VIX3M backwardation
        vix_today = self._vix.loc[:ts]
        vix3m_today = self._vix3m.loc[:ts]
        if not vix_today.empty and not vix3m_today.empty:
            ratio = float(vix_today.iloc[-1]) / float(vix3m_today.iloc[-1])
            if ratio > self.stress_vix_vix3m_threshold:
                return True
        return False

    def _stressed_iv_floor(self, as_of: date) -> float:
        """When stressed, IV floor = SPY 5d realized × multiplier. Captures the
        IV-realized divergence on shock days that pure VIX (forward-looking)
        misses. Returns 0.0 if no realized data."""
        self._ensure()
        ts = pd.Timestamp(as_of)
        rv = self._spy_5d_rv.loc[:ts]
        if rv.empty or pd.isna(rv.iloc[-1]):
            return 0.0
        return float(rv.iloc[-1]) * self.stress_iv_realized_multiplier

    def iv_for(
        self, as_of: date, S: float, K: float, T: float,
        option_type: OptionType | None = None,
    ) -> float:
        """IV for a given (date, spot, strike, T-years). Term-scaled, skew-adjusted,
        and stress-clipped + asymmetric on shock days (calibrated to match Aryan
        Optimized's real 77.7% WR rather than the synthetic-clean 93%)."""
        atm = self._atm_iv_30d(as_of)
        if atm is None:
            raise ValueError(f"no VIX cached at {as_of}")
        # Stress clip: replace ATM IV with max(VIX, realized_5d × multiplier) on shock days.
        stressed = self._is_stressed(as_of)
        if stressed:
            floor = self._stressed_iv_floor(as_of)
            if floor > atm:
                atm = floor
        # Asymmetric: down-moves spike vol harder.
        self._ensure()
        ts = pd.Timestamp(as_of)
        spy_chg_series = self._spy_1d_change.loc[:ts]
        if not spy_chg_series.empty and not pd.isna(spy_chg_series.iloc[-1]):
            spy_chg = float(spy_chg_series.iloc[-1])
            if spy_chg < self.down_move_threshold:
                atm = atm * self.down_move_iv_multiplier
        # Term scaling: VIX is 30d. Scale by sqrt(T_days / 30).
        T_days = max(T * 365.0, 1.0)
        term_factor = math.sqrt(T_days / 30.0)
        skew = self._skew_slope(as_of)
        # Put-side skew steepens further on stress days (vol smile asymmetry).
        if stressed and option_type == OptionType.PUT:
            skew = skew * self.stress_put_skew_multiplier
        # Negative moneyness (puts OTM = K < S) gets HIGHER IV under positive skew.
        moneyness = (K - S) / S
        iv = atm * term_factor + skew * (-moneyness)
        return max(iv, 0.05)  # floor to keep BSM stable

    def quote(
        self, as_of: date, underlying: str, expiration: date, strike: float,
        option_type: OptionType,
    ) -> ChainQuote | None:
        """Generate a single synthetic quote at a date for a (strike, expiry, type)."""
        S = self._underlying_close(underlying, as_of)
        if S is None:
            return None
        T = max((expiration - as_of).days / 365.0, 1 / 365.0)
        if T <= 0:
            return None
        sigma = self.iv_for(as_of, S, strike, T, option_type=option_type)
        flag = "call" if option_type == OptionType.CALL else "put"
        mid = bsm_price(S, strike, T, self.risk_free_rate, sigma, flag, q=0.0)
        d = bsm_delta(S, strike, T, self.risk_free_rate, sigma, flag, q=0.0)
        # Spread: 1% at delta>=0.30 widening to 5% at delta<=0.05.
        abs_d = abs(d)
        spread_frac = 0.01 + (0.04 * (1.0 - min(abs_d / 0.30, 1.0)))
        half = mid * spread_frac / 2.0
        bid = max(mid - half, 0.01)
        ask = mid + half
        return ChainQuote(
            strike=Decimal(str(round(strike, 2))),
            option_type=option_type,
            bid=Decimal(str(round(bid, 2))),
            ask=Decimal(str(round(ask, 2))),
            delta=d,
            expiration=expiration.isoformat(),
            underlying_close=S,
            iv=sigma,
        )

    def find_by_delta(
        self,
        underlying: str,
        expiration: str,
        option_type: OptionType,
        target_delta: float,
        as_of: str | None = None,
    ) -> ChainQuote | None:
        """Locate the strike whose |delta| is closest to target_delta.

        Strategy: BSM-invert. Start from spot, step strikes outward in 1-pt
        increments (or 5-pt for SPY), evaluate delta, stop when crossing target.
        """
        if as_of is None:
            raise ValueError("SyntheticBSMChain.find_by_delta requires as_of=YYYY-MM-DD")
        as_of_d = datetime.strptime(as_of, "%Y-%m-%d").date()
        exp_d = datetime.strptime(expiration, "%Y-%m-%d").date()
        S = self._underlying_close(underlying, as_of_d)
        if S is None:
            return None

        # Use 1-point strike granularity (SPY trades 1pt strikes for short DTE).
        step = 1.0
        start_strike = round(S)
        # For calls, walk strikes UP; for puts, walk DOWN.
        direction = 1 if option_type == OptionType.CALL else -1

        best: ChainQuote | None = None
        for i in range(0, 200):
            K = start_strike + direction * i * step
            if K <= 0:
                break
            q = self.quote(as_of_d, underlying, exp_d, K, option_type)
            if q is None:
                continue
            d_abs = abs(q.delta)
            if best is None or abs(d_abs - target_delta) < abs(abs(best.delta) - target_delta):
                best = q
            # Once we've crossed below target_delta, we've gone too far OTM.
            if d_abs < target_delta * 0.5:
                break
        return best

    # --- batch helpers used by backtest engine ---

    def mark_position(self, position_legs, as_of: date) -> Decimal:
        """Return the per-share mid value (as Decimal) summing across legs.

        Conventions: positive number = current per-share mid value of the open
        position (treating it as a single instrument). Backtest engine uses this
        to compute mark-to-market P&L.
        """
        total = Decimal(0)
        for leg in position_legs:
            exp = datetime.strptime(leg.expiration, "%Y-%m-%d").date()
            S = self._underlying_close(leg.underlying, as_of)
            if S is None:
                return Decimal(0)
            T = max((exp - as_of).days / 365.0, 1 / 365.0)
            sigma = self.iv_for(as_of, S, float(leg.strike), T, option_type=leg.option_type)
            flag = "call" if leg.option_type == OptionType.CALL else "put"
            mid = bsm_price(S, float(leg.strike), T, self.risk_free_rate, sigma, flag, q=0.0)
            sign = 1 if leg.side.value == "long" else -1
            total += Decimal(str(round(mid * sign * leg.qty, 4))) * Decimal("100")
        return total
