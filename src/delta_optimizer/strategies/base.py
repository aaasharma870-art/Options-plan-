"""Base types for option strategies.

Decimal-based P&L (per CLAUDE.md C9). Float lives only inside the BSM kernel.
A leg is one option contract (or share). A Position is N legs. A Strategy
emits Positions given chain data and parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

# Multiplier for standard equity option contracts (1 contract = 100 shares).
CONTRACT_MULTIPLIER = Decimal("100")


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class Side(str, Enum):
    LONG = "long"   # +1 (debit on open)
    SHORT = "short"  # -1 (credit on open)


@dataclass(frozen=True)
class OptionLeg:
    """One option leg of a multi-leg position.

    `entry_price` is the per-share premium paid (long) or received (short),
    expressed as Decimal in account currency. The `qty` is contract count
    (positive integer). Side determines sign of cashflow.
    """

    underlying: str
    expiration: str          # ISO YYYY-MM-DD
    strike: Decimal
    option_type: OptionType
    side: Side
    qty: int
    entry_price: Decimal     # per share, premium

    def __post_init__(self) -> None:
        if self.qty <= 0:
            raise ValueError(f"qty must be > 0; got {self.qty}")
        if self.entry_price < 0:
            raise ValueError(f"entry_price must be >= 0; got {self.entry_price}")
        if self.strike <= 0:
            raise ValueError(f"strike must be > 0; got {self.strike}")

    @property
    def signed_cash_on_open(self) -> Decimal:
        """Cash flow at open (negative = debit, positive = credit)."""
        cash = self.entry_price * Decimal(self.qty) * CONTRACT_MULTIPLIER
        return cash if self.side == Side.SHORT else -cash

    def intrinsic_at(self, spot: Decimal) -> Decimal:
        """Intrinsic value per share at the given spot."""
        spot = Decimal(spot)
        if self.option_type == OptionType.CALL:
            return max(spot - self.strike, Decimal(0))
        return max(self.strike - spot, Decimal(0))

    def signed_value_at(self, mark: Decimal) -> Decimal:
        """Position value at a given per-share mark.

        For SHORT legs: closing requires PAYING the mark → value is negative
        of mark × multiplier × qty (you owe it).
        For LONG legs: position is worth +mark × multiplier × qty.
        """
        mark = Decimal(mark)
        notional = mark * Decimal(self.qty) * CONTRACT_MULTIPLIER
        return notional if self.side == Side.LONG else -notional


@dataclass(frozen=True)
class Position:
    """A multi-leg option position. Constructor enforces all legs share underlying."""

    legs: tuple[OptionLeg, ...]
    structure: str  # "iron_condor", "iron_butterfly", "bull_put", "bear_call", etc.
    entry_date: str           # ISO YYYY-MM-DD
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError("Position must have at least one leg")
        underlyings = {leg.underlying for leg in self.legs}
        if len(underlyings) > 1:
            raise ValueError(f"All legs must share underlying; got {underlyings}")
        expiries = {leg.expiration for leg in self.legs}
        # Multi-expiry positions (calendars/diagonals) are FORBIDDEN per C1.
        if len(expiries) > 1:
            raise ValueError(
                f"Multi-expiry positions are forbidden by C1 (OA DSL); got {expiries}"
            )

    @property
    def underlying(self) -> str:
        return self.legs[0].underlying

    @property
    def expiration(self) -> str:
        return self.legs[0].expiration

    @property
    def credit(self) -> Decimal:
        """Net credit (>0) or debit (<0) at open. Positive == cash IN."""
        return sum((leg.signed_cash_on_open for leg in self.legs), Decimal(0))

    @property
    def max_profit(self) -> Decimal:
        """Best-case P&L. For credit spreads = credit. Caller must override
        for debit spreads (covered explicitly by structure)."""
        c = self.credit
        return c if c > 0 else Decimal(0)

    @property
    def max_loss(self) -> Decimal:
        """Worst-case P&L (returns POSITIVE number for the loss magnitude).

        For credit spreads: max_loss = wing_width * 100 - credit.
        Computed by simulating expiration P&L at each strike + extreme spots.
        """
        # Compute expiration P&L at each strike and at 0/inf.
        strikes = sorted({float(leg.strike) for leg in self.legs})
        test_spots = [Decimal("0.01"), *(Decimal(str(s)) for s in strikes),
                      Decimal(str(strikes[-1] * 10))]
        worst = Decimal(0)
        for spot in test_spots:
            pnl = self.pnl_at_expiration(spot)
            if pnl < worst:
                worst = pnl
        return -worst  # positive magnitude

    def pnl_at_expiration(self, spot: Decimal) -> Decimal:
        """P&L at expiry, given spot. Equals (intrinsic_proceeds) + (open credit)."""
        spot = Decimal(spot)
        # At expiry: each leg pays its intrinsic. SHORT pays negatively (we owe).
        intrinsic_total = Decimal(0)
        for leg in self.legs:
            intr = leg.intrinsic_at(spot) * Decimal(leg.qty) * CONTRACT_MULTIPLIER
            intrinsic_total += intr if leg.side == Side.LONG else -intr
        return self.credit + intrinsic_total
