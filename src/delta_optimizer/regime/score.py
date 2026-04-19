"""Composite regime score (Phase 1).

Three-factor classifier (GEX deferred until chain backfill in Phase 2):
  VIX level         : 0 if <17, 1 if 17-22, 2 if >22
  IV Percentile     : 0 if 50-80, 1 if 30-50 or 80-90, 2 if <30 or >90
  VIX/VIX3M ratio   : 0 if <0.95, 1 if 0.95-1.00, 2 if >1.00

Composite range: 0..6 (master prompt's 0..8 minus the 0..2 GEX dimension).
Buckets remain consistent with the master prompt's structure:
  0-1 GREEN, 2-3 YELLOW, 4-5 ORANGE, 6+ RED
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class RegimeBucket(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


@dataclass(frozen=True)
class ScoreThresholds:
    """All regime score thresholds. Frozen so they're a stable identity for
    tests / reports / status JSON. Adjust by constructing a new instance."""

    vix_low: float = 17.0
    vix_high: float = 22.0
    ivp_low_red: float = 30.0
    ivp_low_yellow: float = 50.0  # >= ivp_low_yellow and <= ivp_high_yellow → green
    ivp_high_yellow: float = 80.0
    ivp_high_red: float = 90.0
    vix_vix3m_yellow: float = 0.95
    vix_vix3m_red: float = 1.00


# --- per-dimension score functions ---


def score_vix_level(vix: float, t: ScoreThresholds = ScoreThresholds()) -> int:
    if np.isnan(vix):
        return -1
    if vix < t.vix_low:
        return 0
    if vix <= t.vix_high:
        return 1
    return 2


def score_iv_percentile(ivp: float, t: ScoreThresholds = ScoreThresholds()) -> int:
    if np.isnan(ivp):
        return -1
    if ivp < t.ivp_low_red or ivp > t.ivp_high_red:
        return 2
    if ivp < t.ivp_low_yellow or ivp > t.ivp_high_yellow:
        return 1
    return 0


def score_vix_vix3m(ratio: float, t: ScoreThresholds = ScoreThresholds()) -> int:
    if np.isnan(ratio):
        return -1
    if ratio < t.vix_vix3m_yellow:
        return 0
    if ratio <= t.vix_vix3m_red:
        return 1
    return 2


# --- composite ---


def composite_score_row(
    vix: float, ivp: float, vix_vix3m: float, t: ScoreThresholds = ScoreThresholds()
) -> int:
    """Composite 0..6 for a single row. Returns -1 if any input is NaN."""
    s_vix = score_vix_level(vix, t)
    s_ivp = score_iv_percentile(ivp, t)
    s_ts = score_vix_vix3m(vix_vix3m, t)
    if -1 in (s_vix, s_ivp, s_ts):
        return -1
    return s_vix + s_ivp + s_ts


def bucket_for_score(score: int) -> RegimeBucket:
    """0-1 GREEN, 2-3 YELLOW, 4-5 ORANGE, 6+ RED. -1 raises ValueError."""
    if score < 0:
        raise ValueError(f"Negative score {score} (NaN inputs)")
    if score <= 1:
        return RegimeBucket.GREEN
    if score <= 3:
        return RegimeBucket.YELLOW
    if score <= 5:
        return RegimeBucket.ORANGE
    return RegimeBucket.RED


def score_dataframe(
    df: pd.DataFrame, t: ScoreThresholds = ScoreThresholds()
) -> pd.DataFrame:
    """Apply scoring to a feature DataFrame. Returns the input + columns:
    score_vix, score_ivp, score_ts, regime_score (0..6, -1 if NaN), regime_bucket.

    Rows with -1 score have regime_bucket == None (filtered downstream).
    """
    out = df.copy()
    out["score_vix"] = out["vix_close"].apply(lambda v: score_vix_level(v, t))
    out["score_ivp"] = out["vix_ivp_252d"].apply(lambda v: score_iv_percentile(v, t))
    out["score_ts"] = out["vix_vix3m"].apply(lambda v: score_vix_vix3m(v, t))
    valid = (out["score_vix"] >= 0) & (out["score_ivp"] >= 0) & (out["score_ts"] >= 0)
    out["regime_score"] = np.where(
        valid, out["score_vix"] + out["score_ivp"] + out["score_ts"], -1
    ).astype(int)
    out["regime_bucket"] = out["regime_score"].apply(
        lambda s: bucket_for_score(s).value if s >= 0 else None
    )
    return out
