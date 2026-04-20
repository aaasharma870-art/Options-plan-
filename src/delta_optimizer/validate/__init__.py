"""Validation suite: Synthetic MC, CPCV, DSR, PBO.

Pure stats. Copied verbatim from optuna-screener/apex/validation/ in Phase 0;
only the import paths were rewritten.
"""

from delta_optimizer.validate.cpcv import cpcv_split
from delta_optimizer.validate.dsr import (
    _expected_max_sr,
    deflated_sharpe_ratio,
    deflated_sharpe_z,
)
from delta_optimizer.validate.pbo import probability_of_backtest_overfitting
from delta_optimizer.validate.synthetic_mc import passes_synthetic_gate, synthetic_price_mc

__all__ = [
    "_expected_max_sr",
    "cpcv_split",
    "deflated_sharpe_ratio",
    "passes_synthetic_gate",
    "probability_of_backtest_overfitting",
    "synthetic_price_mc",
]
