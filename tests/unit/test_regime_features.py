"""Phase 1 regime feature math — known-answer tests on synthetic series."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from delta_optimizer.regime.features import (
    daily_pct_change,
    forward_max_drawdown,
    forward_realized_vol,
    percentile_rank_rolling,
    realized_vol_annualized,
    rolling_n_day_high,
    vix_vix3m_ratio,
)


class TestRealizedVol:

    def test_constant_series_zero_vol(self) -> None:
        s = pd.Series([100.0] * 30)
        rv = realized_vol_annualized(s, window=20)
        # Last value should be exactly 0 (all log returns are 0).
        assert rv.iloc[-1] == 0.0

    def test_known_answer_two_returns(self) -> None:
        # Ten-day series with constant +1% daily move. Log return = ln(1.01) ≈ 0.00995.
        # Sample stddev of 9 identical values is 0; annualized RV = 0.
        s = pd.Series([100 * (1.01 ** i) for i in range(10)])
        rv = realized_vol_annualized(s, window=9)
        assert rv.iloc[-1] == pytest.approx(0.0, abs=1e-12)

    def test_alternating_returns_known_stddev(self) -> None:
        # Series alternating ±1% daily for 21 bars => 20 returns of magnitude
        # |ln(1.01)| or |ln(0.99)|, signs alternating.
        prices = [100.0]
        for i in range(20):
            prices.append(prices[-1] * (1.01 if i % 2 == 0 else 0.99))
        s = pd.Series(prices)
        rv = realized_vol_annualized(s, window=20)
        # Hand: log returns alternate +0.00995, -0.01005. Mean ≈ -0.00005.
        # Stddev ≈ 0.01000. Annualized ≈ 0.01 * sqrt(252) ≈ 0.1587.
        assert rv.iloc[-1] == pytest.approx(0.1587, abs=0.005)


class TestRollingNDayHigh:

    def test_known_answer(self) -> None:
        s = pd.Series([1, 3, 2, 5, 4, 6, 1])
        h = rolling_n_day_high(s, n=3)
        # Rolling max with window 3:
        #   idx 2: max(1,3,2) = 3
        #   idx 3: max(3,2,5) = 5
        #   idx 6: max(6,1,...) wait window=3 -> max(4,6,1)=6
        assert h.iloc[2] == 3
        assert h.iloc[3] == 5
        assert h.iloc[6] == 6


class TestDailyPctChange:

    def test_known(self) -> None:
        s = pd.Series([100.0, 110.0, 99.0])
        c = daily_pct_change(s)
        assert c.iloc[1] == pytest.approx(0.10)
        assert c.iloc[2] == pytest.approx(-0.10)


class TestPercentileRankRolling:

    def test_uniform_series_50th(self) -> None:
        # In an ascending sequence, the LAST value is the max => 100th percentile
        # (fraction <= current = 1.0).
        s = pd.Series(list(range(1, 11)))
        p = percentile_rank_rolling(s, window=10)
        assert p.iloc[-1] == 100.0

    def test_min_in_window_10th(self) -> None:
        # Window where current is the smallest => only itself qualifies => 1/10 = 10%.
        s = pd.Series([5, 4, 3, 2, 1, 6, 7, 8, 9, 10, 0])
        p = percentile_rank_rolling(s, window=10)
        # Window for last row = [4,3,2,1,6,7,8,9,10,0]; current=0 is the min.
        # Fraction <= 0 in that window = 1/10 = 10%.
        assert p.iloc[-1] == 10.0

    def test_nan_until_window_full(self) -> None:
        s = pd.Series(range(20))
        p = percentile_rank_rolling(s, window=10)
        assert p.iloc[8] != p.iloc[8]  # NaN check
        assert not np.isnan(p.iloc[9])


class TestVixVix3MRatio:

    def test_known(self) -> None:
        vix = pd.Series([20.0, 15.0])
        vix3m = pd.Series([25.0, 15.0])
        r = vix_vix3m_ratio(vix, vix3m)
        assert r.iloc[0] == pytest.approx(0.8)
        assert r.iloc[1] == pytest.approx(1.0)


class TestForwardLooking:

    def test_forward_realized_vol_constant_returns(self) -> None:
        # Geometric series with constant +1% daily. Log returns are constant
        # so stddev over any future window is 0.
        s = pd.Series([100.0 * (1.01 ** i) for i in range(20)])
        fwd = forward_realized_vol(s, horizon_days=5)
        # Most rows where 5 future returns exist should be ~0.
        # The last 5 rows lose data and become NaN.
        assert fwd.iloc[5] == pytest.approx(0.0, abs=1e-9)

    def test_forward_max_drawdown_monotone_up(self) -> None:
        # Strictly rising series — forward max DD should be > 0 (next bar > peak).
        s = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0])
        dd = forward_max_drawdown(s, horizon_days=3)
        # At index 0 (price 100), next 3 prices are 101,102,103 all > 100 →
        # min/peak - 1 = 101/100 - 1 = +0.01.
        assert dd.iloc[0] == pytest.approx(0.01)

    def test_forward_max_drawdown_with_decline(self) -> None:
        s = pd.Series([100.0, 95.0, 90.0, 85.0, 80.0])
        dd = forward_max_drawdown(s, horizon_days=3)
        # At index 0 (100), next 3 prices are 95,90,85; min=85; 85/100 - 1 = -0.15.
        assert dd.iloc[0] == pytest.approx(-0.15)
