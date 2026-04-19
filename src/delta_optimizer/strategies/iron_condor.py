"""Iron Condor strategy.

A long-strangle hedge against a short-strangle credit position:
    SHORT call (target delta), LONG further-OTM call (wing)
    SHORT put  (target delta), LONG further-OTM put  (wing)

All four legs share the same expiration. Defined-risk; max loss = wider
wing width * 100 - net credit.

The chain provider interface is abstract — strategies don't fetch chains
themselves, they accept a `Chain` whose only job is "give me the option
closest to delta D for {call,put} at expiration E".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from delta_optimizer.strategies.base import (
    OptionLeg,
    OptionType,
    Position,
    Side,
)


class ChainQuote(Protocol):
    """Anything you can build a leg from."""

    strike: Decimal
    option_type: OptionType
    bid: Decimal
    ask: Decimal
    delta: float
    expiration: str  # ISO YYYY-MM-DD


class ChainProvider(Protocol):
    """Abstract chain access. Real impl reads cached Polygon snapshots.

    Tests use a `MockChain` that just returns canned quotes — that's how the
    iron condor logic is exercised without hitting any network.
    """

    def find_by_delta(
        self,
        underlying: str,
        expiration: str,
        option_type: OptionType,
        target_delta: float,
    ) -> ChainQuote | None:
        """Return the option whose absolute delta is closest to `target_delta`.
        Sign convention: target_delta is supplied as a positive value (e.g., 0.16).
        For puts, returns the leg whose |delta| ≈ target_delta.
        """
        ...


@dataclass
class IronCondorParams:
    """Construction parameters for an iron condor at a given trade date."""

    short_call_delta: float   # e.g., 0.18
    long_call_delta: float    # e.g., 0.06
    short_put_delta: float    # e.g., 0.18  (positive value; we abs() before matching)
    long_put_delta: float     # e.g., 0.06
    qty_per_leg: int = 1
    use_mid: bool = True      # True: enter at mid (bid+ask)/2; False: market

    def validate(self) -> None:
        if not (0 < self.long_call_delta < self.short_call_delta < 0.50):
            raise ValueError(
                f"call leg ordering invalid: long {self.long_call_delta} short "
                f"{self.short_call_delta}; require 0 < long < short < 0.50"
            )
        if not (0 < self.long_put_delta < self.short_put_delta < 0.50):
            raise ValueError(
                f"put leg ordering invalid: long {self.long_put_delta} short "
                f"{self.short_put_delta}; require 0 < long < short < 0.50"
            )
        if self.qty_per_leg <= 0:
            raise ValueError(f"qty_per_leg must be > 0; got {self.qty_per_leg}")


def _quote_to_leg_price(q: ChainQuote, use_mid: bool) -> Decimal:
    if use_mid:
        return (q.bid + q.ask) / Decimal(2)
    return q.ask  # conservative: pay/receive worse side


def build_iron_condor(
    underlying: str,
    entry_date: str,
    expiration: str,
    chain: ChainProvider,
    params: IronCondorParams,
) -> Position | None:
    """Build an iron condor by selecting four legs at target deltas.

    Returns None if any leg can't be sourced (chain too thin at the target deltas).
    """
    params.validate()

    sc = chain.find_by_delta(underlying, expiration, OptionType.CALL, params.short_call_delta)
    lc = chain.find_by_delta(underlying, expiration, OptionType.CALL, params.long_call_delta)
    sp = chain.find_by_delta(underlying, expiration, OptionType.PUT, params.short_put_delta)
    lp = chain.find_by_delta(underlying, expiration, OptionType.PUT, params.long_put_delta)
    if any(q is None for q in (sc, lc, sp, lp)):
        return None

    # Sanity: long strikes must be further OTM than shorts.
    if not (lc.strike > sc.strike):
        raise ValueError(
            f"long call strike {lc.strike} must be > short call strike {sc.strike}"
        )
    if not (lp.strike < sp.strike):
        raise ValueError(
            f"long put strike {lp.strike} must be < short put strike {sp.strike}"
        )

    legs = (
        OptionLeg(
            underlying=underlying,
            expiration=expiration,
            strike=Decimal(sc.strike),
            option_type=OptionType.CALL,
            side=Side.SHORT,
            qty=params.qty_per_leg,
            entry_price=_quote_to_leg_price(sc, params.use_mid),
        ),
        OptionLeg(
            underlying=underlying,
            expiration=expiration,
            strike=Decimal(lc.strike),
            option_type=OptionType.CALL,
            side=Side.LONG,
            qty=params.qty_per_leg,
            entry_price=_quote_to_leg_price(lc, params.use_mid),
        ),
        OptionLeg(
            underlying=underlying,
            expiration=expiration,
            strike=Decimal(sp.strike),
            option_type=OptionType.PUT,
            side=Side.SHORT,
            qty=params.qty_per_leg,
            entry_price=_quote_to_leg_price(sp, params.use_mid),
        ),
        OptionLeg(
            underlying=underlying,
            expiration=expiration,
            strike=Decimal(lp.strike),
            option_type=OptionType.PUT,
            side=Side.LONG,
            qty=params.qty_per_leg,
            entry_price=_quote_to_leg_price(lp, params.use_mid),
        ),
    )

    return Position(
        legs=legs,
        structure="iron_condor",
        entry_date=entry_date,
        metadata={
            "short_call_delta": params.short_call_delta,
            "long_call_delta": params.long_call_delta,
            "short_put_delta": params.short_put_delta,
            "long_put_delta": params.long_put_delta,
        },
    )


def call_wing_width(position: Position) -> Decimal:
    """Difference between long and short call strikes. Positive."""
    legs_call = [
        leg for leg in position.legs if leg.option_type == OptionType.CALL
    ]
    short = next(leg for leg in legs_call if leg.side == Side.SHORT)
    long = next(leg for leg in legs_call if leg.side == Side.LONG)
    return long.strike - short.strike


def put_wing_width(position: Position) -> Decimal:
    legs_put = [leg for leg in position.legs if leg.option_type == OptionType.PUT]
    short = next(leg for leg in legs_put if leg.side == Side.SHORT)
    long = next(leg for leg in legs_put if leg.side == Side.LONG)
    return short.strike - long.strike
