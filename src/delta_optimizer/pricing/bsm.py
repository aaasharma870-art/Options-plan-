"""Black-Scholes-Merton pricer + Greeks.

Float-only implementation (per CLAUDE.md: float allowed inside vectorized
BSM kernels; Decimal lives in P&L aggregation). Cross-validated against
py_vollib in tests; put-call parity enforced as Hypothesis property test.

Conventions:
  S: spot price
  K: strike
  T: time to expiration in YEARS (e.g., 30/365 for 30 calendar days)
  r: continuously-compounded risk-free rate (decimal, e.g., 0.05)
  sigma: implied vol (annualized, decimal, e.g., 0.20 for 20%)
  q: continuous dividend yield (decimal). Defaults to 0.

All Greeks are per ONE share, not per contract. Multiply by 100 for option
contracts unless caller has already done so.
"""

from __future__ import annotations

import math
from typing import Literal

from scipy.stats import norm

OptionType = Literal["call", "put"]

SQRT_2PI = math.sqrt(2.0 * math.pi)


def _validate(S: float, K: float, T: float, sigma: float) -> None:
    if S <= 0:
        raise ValueError(f"S must be > 0; got {S}")
    if K <= 0:
        raise ValueError(f"K must be > 0; got {K}")
    if T < 0:
        raise ValueError(f"T must be >= 0; got {T}")
    if sigma < 0:
        raise ValueError(f"sigma must be >= 0; got {sigma}")


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    """Standard d1, d2. Defined when T > 0 and sigma > 0; caller must guard."""
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return d1, d2


# --- Price ---


def price(
    S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType, q: float = 0.0
) -> float:
    """Black-Scholes-Merton European option price.

    Edge cases:
      T == 0: returns intrinsic value, max(S-K, 0) for calls, max(K-S, 0) for puts.
      sigma == 0: returns discounted intrinsic at expiry.
    """
    _validate(S, K, T, sigma)
    if T == 0:
        if option_type == "call":
            return max(S - K, 0.0)
        return max(K - S, 0.0)
    if sigma == 0:
        # Discounted forward intrinsic.
        fwd = S * math.exp(-q * T)
        kpv = K * math.exp(-r * T)
        if option_type == "call":
            return max(fwd - kpv, 0.0)
        return max(kpv - fwd, 0.0)

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def price_call(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return price(S, K, T, r, sigma, "call", q)


def price_put(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return price(S, K, T, r, sigma, "put", q)


# --- Greeks ---


def delta(
    S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType, q: float = 0.0
) -> float:
    """Delta: dPrice/dS. Range [0, 1] for calls, [-1, 0] for puts."""
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0:
        # Step function at strike.
        if option_type == "call":
            return 1.0 if S > K else (0.5 if S == K else 0.0)
        return -1.0 if S < K else (-0.5 if S == K else 0.0)
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    disc = math.exp(-q * T)
    if option_type == "call":
        return disc * norm.cdf(d1)
    return disc * (norm.cdf(d1) - 1.0)


def gamma(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Gamma: d2Price/dS2. Same for calls and puts."""
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0 or S == 0:
        return 0.0
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Vega: dPrice/dSigma. Per 1.00 change in vol; divide by 100 for per-1%-change."""
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0:
        return 0.0
    d1, _ = _d1_d2(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)


def theta(
    S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType, q: float = 0.0
) -> float:
    """Theta: dPrice/dT (negative of calendar decay). Per 1 YEAR;
    divide by 365 for per-day."""
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0:
        return 0.0
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    sqrt_T = math.sqrt(T)
    common = -(S * math.exp(-q * T) * norm.pdf(d1) * sigma) / (2.0 * sqrt_T)
    if option_type == "call":
        return (
            common
            + q * S * math.exp(-q * T) * norm.cdf(d1)
            - r * K * math.exp(-r * T) * norm.cdf(d2)
        )
    return (
        common
        - q * S * math.exp(-q * T) * norm.cdf(-d1)
        + r * K * math.exp(-r * T) * norm.cdf(-d2)
    )


def rho(
    S: float, K: float, T: float, r: float, sigma: float, option_type: OptionType, q: float = 0.0
) -> float:
    """Rho: dPrice/dR. Per 1.00 change in rate; divide by 100 for per-1%-change."""
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0:
        return 0.0
    _, d2 = _d1_d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return K * T * math.exp(-r * T) * norm.cdf(d2)
    return -K * T * math.exp(-r * T) * norm.cdf(-d2)


# --- Implied volatility ---


def implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
    *,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float:
    """Solve for sigma given an observed option price (Newton-Raphson + bisection fallback).

    Returns NaN if the market price is below intrinsic (no real IV exists).
    """
    intrinsic = max(
        (S * math.exp(-q * T) - K * math.exp(-r * T)) if option_type == "call"
        else (K * math.exp(-r * T) - S * math.exp(-q * T)),
        0.0,
    )
    if market_price < intrinsic - 1e-12:
        return float("nan")

    # Newton-Raphson with sigma in [1e-6, 5.0].
    sigma = 0.30  # reasonable initial guess
    for _ in range(max_iter):
        p = price(S, K, T, r, sigma, option_type, q)
        v = vega(S, K, T, r, sigma, q)
        if v < 1e-12:
            break
        diff = p - market_price
        if abs(diff) < tol:
            return sigma
        sigma -= diff / v
        if sigma <= 0 or sigma > 5.0:
            sigma = max(min(sigma, 5.0), 1e-6)

    # Bisection fallback over [1e-6, 5.0].
    lo, hi = 1e-6, 5.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        p = price(S, K, T, r, mid, option_type, q)
        if abs(p - market_price) < tol:
            return mid
        if p > market_price:
            hi = mid
        else:
            lo = mid
    return mid
