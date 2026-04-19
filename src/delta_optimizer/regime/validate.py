"""Phase 1 validation gate: ANOVA + Cohen's d on forward realized vol.

Master prompt requirement (Phase 1 § validation gate):
- Bucket trading days by regime score.
- Compute forward 5-day annualized realized vol per day (already in feature frame).
- One-way ANOVA across all buckets; require p < 0.01 GREEN vs RED.
- Cohen's d (GREEN vs RED); require d > 0.5.
- If gate fails, iterate thresholds within ±3 units up to 3 times. We do not
  re-tune the score CONSTRUCTION — only thresholds — per the spec.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats

from delta_optimizer.regime.score import RegimeBucket, ScoreThresholds, score_dataframe


@dataclass
class GateResult:
    passed: bool
    n_total: int
    n_per_bucket: dict[str, int]
    fwd_rv_mean_per_bucket: dict[str, float]
    fwd_rv_std_per_bucket: dict[str, float]
    anova_p: float | None
    anova_F: float | None
    cohens_d_green_vs_red: float | None
    thresholds: dict[str, float]
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's d between two samples, pooled stddev. Sign: positive when b > a."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                     / (len(a) + len(b) - 2))
    if pooled == 0:
        return float("nan")
    return float((b.mean() - a.mean()) / pooled)


def evaluate_gate(
    feature_df: pd.DataFrame,
    thresholds: ScoreThresholds = ScoreThresholds(),
    *,
    p_threshold: float = 0.01,
    d_threshold: float = 0.5,
) -> GateResult:
    """Score the feature frame, bucket by regime, and run the validation gate."""
    scored = score_dataframe(feature_df, thresholds)
    notes: list[str] = []

    valid = scored[(scored["regime_score"] >= 0) & scored["fwd_rv_5d"].notna()].copy()
    n_per_bucket = valid["regime_bucket"].value_counts().to_dict()
    fwd_mean = valid.groupby("regime_bucket")["fwd_rv_5d"].mean().to_dict()
    fwd_std = valid.groupby("regime_bucket")["fwd_rv_5d"].std(ddof=1).to_dict()

    # ANOVA across all buckets that have ≥2 samples.
    groups = []
    for b in [RegimeBucket.GREEN, RegimeBucket.YELLOW, RegimeBucket.ORANGE, RegimeBucket.RED]:
        vals = valid.loc[valid["regime_bucket"] == b.value, "fwd_rv_5d"].dropna().values
        if len(vals) >= 2:
            groups.append(vals)
        else:
            notes.append(f"bucket {b.value} has only {len(vals)} obs; excluded from ANOVA")

    anova_p: float | None = None
    anova_F: float | None = None
    if len(groups) >= 2:
        F, p = stats.f_oneway(*groups)
        anova_F = float(F)
        anova_p = float(p)
    else:
        notes.append("fewer than 2 non-trivial buckets — ANOVA not run")

    green = valid.loc[valid["regime_bucket"] == "GREEN", "fwd_rv_5d"].dropna().values
    red = valid.loc[valid["regime_bucket"] == "RED", "fwd_rv_5d"].dropna().values
    d_g_r: float | None = None
    if len(green) >= 2 and len(red) >= 2:
        d_g_r = cohens_d(green, red)
    else:
        notes.append(
            f"GREEN n={len(green)} RED n={len(red)} — Cohen's d not computed"
        )

    passed = (
        anova_p is not None
        and anova_p < p_threshold
        and d_g_r is not None
        and d_g_r > d_threshold
    )

    return GateResult(
        passed=passed,
        n_total=int(len(valid)),
        n_per_bucket={k: int(v) for k, v in n_per_bucket.items()},
        fwd_rv_mean_per_bucket={k: float(v) for k, v in fwd_mean.items()},
        fwd_rv_std_per_bucket={k: float(v) for k, v in fwd_std.items()},
        anova_p=anova_p,
        anova_F=anova_F,
        cohens_d_green_vs_red=d_g_r,
        thresholds={
            "vix_low": thresholds.vix_low,
            "vix_high": thresholds.vix_high,
            "ivp_low_red": thresholds.ivp_low_red,
            "ivp_low_yellow": thresholds.ivp_low_yellow,
            "ivp_high_yellow": thresholds.ivp_high_yellow,
            "ivp_high_red": thresholds.ivp_high_red,
            "vix_vix3m_yellow": thresholds.vix_vix3m_yellow,
            "vix_vix3m_red": thresholds.vix_vix3m_red,
            "p_threshold": p_threshold,
            "d_threshold": d_threshold,
        },
        notes=notes,
    )
