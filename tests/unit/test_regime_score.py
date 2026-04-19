"""Phase 1 regime score — boundary tests at every threshold."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from delta_optimizer.regime.score import (
    RegimeBucket,
    ScoreThresholds,
    bucket_for_score,
    composite_score_row,
    score_dataframe,
    score_iv_percentile,
    score_vix_level,
    score_vix_vix3m,
)


class TestVixLevel:
    """Default thresholds: <17 → 0, 17-22 → 1, >22 → 2."""

    @pytest.mark.parametrize("vix,expected", [
        (10.0, 0),
        (16.99, 0),
        (17.0, 1),    # boundary inclusive on yellow side
        (20.0, 1),
        (22.0, 1),    # 22 is still yellow (<= vix_high)
        (22.01, 2),
        (50.0, 2),
    ])
    def test_score(self, vix: float, expected: int) -> None:
        assert score_vix_level(vix) == expected

    def test_nan_returns_minus1(self) -> None:
        assert score_vix_level(float("nan")) == -1


class TestIVPercentile:
    """Defaults: <30 or >90 → 2, 30-50 or 80-90 → 1, 50-80 → 0."""

    @pytest.mark.parametrize("ivp,expected", [
        (0.0, 2),
        (29.99, 2),
        (30.0, 1),    # 30 is yellow
        (45.0, 1),
        (50.0, 0),    # 50 is green
        (75.0, 0),
        (80.0, 0),    # 80 is still green (<= ivp_high_yellow)
        (80.01, 1),
        (90.0, 1),
        (90.01, 2),
        (100.0, 2),
    ])
    def test_score(self, ivp: float, expected: int) -> None:
        assert score_iv_percentile(ivp) == expected


class TestVixVix3M:
    """Defaults: <0.95 → 0, 0.95-1.00 → 1, >1.00 → 2."""

    @pytest.mark.parametrize("ratio,expected", [
        (0.80, 0),
        (0.949999, 0),
        (0.95, 1),
        (1.00, 1),
        (1.0001, 2),
        (1.10, 2),
    ])
    def test_score(self, ratio: float, expected: int) -> None:
        assert score_vix_vix3m(ratio) == expected


class TestComposite:

    def test_all_green(self) -> None:
        # vix=10 (0), ivp=60 (0), ratio=0.85 (0)
        assert composite_score_row(10.0, 60.0, 0.85) == 0

    def test_all_red(self) -> None:
        # vix=30 (2), ivp=95 (2), ratio=1.05 (2)
        assert composite_score_row(30.0, 95.0, 1.05) == 6

    def test_mixed(self) -> None:
        # vix=20 (1), ivp=85 (1), ratio=0.96 (1) = 3 (yellow boundary)
        assert composite_score_row(20.0, 85.0, 0.96) == 3

    def test_nan_propagates(self) -> None:
        assert composite_score_row(float("nan"), 60.0, 0.85) == -1


class TestBucket:

    @pytest.mark.parametrize("score,bucket", [
        (0, RegimeBucket.GREEN),
        (1, RegimeBucket.GREEN),
        (2, RegimeBucket.YELLOW),
        (3, RegimeBucket.YELLOW),
        (4, RegimeBucket.ORANGE),
        (5, RegimeBucket.ORANGE),
        (6, RegimeBucket.RED),
        (7, RegimeBucket.RED),
    ])
    def test_known(self, score: int, bucket: RegimeBucket) -> None:
        assert bucket_for_score(score) == bucket

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            bucket_for_score(-1)


class TestScoreDataFrame:

    def test_full_pipeline_synthetic(self) -> None:
        df = pd.DataFrame({
            "vix_close": [10.0, 20.0, 30.0],
            "vix_ivp_252d": [60.0, 85.0, 95.0],
            "vix_vix3m": [0.85, 0.96, 1.05],
        })
        out = score_dataframe(df)
        assert list(out["regime_score"]) == [0, 3, 6]
        assert list(out["regime_bucket"]) == ["GREEN", "YELLOW", "RED"]

    def test_nan_row_marked_invalid(self) -> None:
        df = pd.DataFrame({
            "vix_close": [10.0, float("nan"), 30.0],
            "vix_ivp_252d": [60.0, 85.0, 95.0],
            "vix_vix3m": [0.85, 0.96, 1.05],
        })
        out = score_dataframe(df)
        assert out["regime_score"].iloc[1] == -1
        # pandas may coerce None to NaN inside an object column with strings.
        assert pd.isna(out["regime_bucket"].iloc[1])

    def test_threshold_override(self) -> None:
        # Tighten VIX-low so 18 becomes red.
        t = ScoreThresholds(vix_low=15.0, vix_high=17.0)
        df = pd.DataFrame({
            "vix_close": [18.0],
            "vix_ivp_252d": [60.0],
            "vix_vix3m": [0.85],
        })
        out = score_dataframe(df, t)
        # vix=18 > vix_high(17) → score 2; ivp=60 → 0; ratio=0.85 → 0; total=2 → YELLOW
        assert out["regime_score"].iloc[0] == 2
        assert out["regime_bucket"].iloc[0] == "YELLOW"
