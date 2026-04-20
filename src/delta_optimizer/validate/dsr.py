"""Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014)."""

import math

from scipy.stats import norm

EULER_MASCHERONI = 0.5772156649


def _expected_max_sr(sr_variance: float, n_trials: int) -> float:
    """Expected maximum Sharpe ratio under the null hypothesis.

    Formula::

        E[max(SR)] = sqrt(V) * ((1 - gamma) * Z(1 - 1/N)
                                + gamma * Z(1 - 1/(N*e)))

    where *gamma* is the Euler-Mascheroni constant, *V* is the variance of
    individual Sharpe ratios, and *Z* is the standard normal quantile.
    """
    if n_trials <= 1:
        return 0.0
    std = math.sqrt(max(sr_variance, 1e-12))
    gamma = EULER_MASCHERONI
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return std * ((1.0 - gamma) * z1 + gamma * z2)


def deflated_sharpe_ratio(observed_sr: float, n_trials: int,
                          sr_variance: float, skew: float, kurtosis: float,
                          n_samples: int) -> float:
    """Compute the Deflated Sharpe Ratio (PROBABILITY form).

    Returns the probability (0..1) that the observed Sharpe ratio exceeds
    the expected maximum under the null, after adjusting for non-normality.

    NOTE on naming/semantics: the underlying Bailey-López de Prado formula
    has two equivalent reporting conventions: (a) the probability returned
    by this function, and (b) the Z-score (observed_sr - expected_max) /
    SE_of_sr — see :func:`deflated_sharpe_z` below. PROJECT_BRIEF.md's
    "DSR > 1.0" threshold refers to the Z-score (b), not the probability.
    Use ``deflated_sharpe_z`` for production gating; this probability form
    is kept for reporting and for the original test fixtures copied from
    optuna-screener.
    """
    sr0 = _expected_max_sr(sr_variance, n_trials)
    if n_samples <= 1:
        return 0.5

    # Adjusted standard error of the Sharpe ratio
    sr_sq = observed_sr * observed_sr
    denom = (1.0
             - skew * observed_sr
             + (kurtosis - 3.0) / 4.0 * sr_sq)
    denom = max(denom, 1e-12)
    se = math.sqrt(denom / (n_samples - 1.0))

    if se < 1e-15:
        return 1.0 if observed_sr > sr0 else 0.0

    z = (observed_sr - sr0) / se
    return float(norm.cdf(z))


def deflated_sharpe_z(observed_sr: float, n_trials: int,
                      sr_variance: float, skew: float, kurtosis: float,
                      n_samples: int) -> float:
    """Z-score form of DSR — the production gating metric.

    Returns ``(observed_sr - expected_max_sr) / se_of_sr``. PROJECT_BRIEF.md
    C2 gate is ``deflated_sharpe_z > 1.0`` — i.e., the observed Sharpe is
    more than one standard error above what max-of-N random Sharpes would be.

    Returns ``-inf`` if not computable (insufficient samples).
    """
    if n_samples <= 1:
        return float("-inf")
    sr0 = _expected_max_sr(sr_variance, n_trials)
    sr_sq = observed_sr * observed_sr
    denom = (1.0 - skew * observed_sr + (kurtosis - 3.0) / 4.0 * sr_sq)
    denom = max(denom, 1e-12)
    se = math.sqrt(denom / (n_samples - 1.0))
    if se < 1e-15:
        return float("inf") if observed_sr > sr0 else float("-inf")
    return float((observed_sr - sr0) / se)
