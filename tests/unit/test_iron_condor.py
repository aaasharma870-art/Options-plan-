"""Iron Condor strategy — known-answer tests on a mock chain.

P&L math is hand-verified. Position class is exercised via IC because IC is
the canonical 4-leg structure."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from delta_optimizer.strategies.base import (
    CONTRACT_MULTIPLIER,
    OptionLeg,
    OptionType,
    Position,
    Side,
)
from delta_optimizer.strategies.iron_condor import (
    IronCondorParams,
    build_iron_condor,
    call_wing_width,
    put_wing_width,
)


@dataclass
class FakeQuote:
    strike: Decimal
    option_type: OptionType
    bid: Decimal
    ask: Decimal
    delta: float
    expiration: str


class MockChain:
    """In-memory chain seeded by tests."""

    def __init__(self, quotes: list[FakeQuote], expiration: str) -> None:
        self._quotes = quotes
        self._expiration = expiration

    def find_by_delta(
        self, underlying, expiration, option_type, target_delta
    ) -> FakeQuote | None:
        candidates = [
            q for q in self._quotes
            if q.option_type == option_type and q.expiration == expiration
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda q: abs(abs(q.delta) - target_delta))


# --- OptionLeg basics ---


class TestOptionLeg:

    def test_short_credit_positive(self) -> None:
        leg = OptionLeg(
            underlying="SPY", expiration="2024-02-16",
            strike=Decimal("420"), option_type=OptionType.CALL,
            side=Side.SHORT, qty=1, entry_price=Decimal("1.20"),
        )
        # 1 contract × $1.20 × 100 = $120 credit
        assert leg.signed_cash_on_open == Decimal("120.00")

    def test_long_debit_negative(self) -> None:
        leg = OptionLeg(
            underlying="SPY", expiration="2024-02-16",
            strike=Decimal("430"), option_type=OptionType.CALL,
            side=Side.LONG, qty=1, entry_price=Decimal("0.40"),
        )
        assert leg.signed_cash_on_open == Decimal("-40.00")

    def test_intrinsic_call(self) -> None:
        leg = OptionLeg(
            underlying="SPY", expiration="2024-02-16",
            strike=Decimal("420"), option_type=OptionType.CALL,
            side=Side.SHORT, qty=1, entry_price=Decimal("1.20"),
        )
        assert leg.intrinsic_at(Decimal("425")) == Decimal("5")
        assert leg.intrinsic_at(Decimal("415")) == Decimal("0")

    def test_intrinsic_put(self) -> None:
        leg = OptionLeg(
            underlying="SPY", expiration="2024-02-16",
            strike=Decimal("400"), option_type=OptionType.PUT,
            side=Side.SHORT, qty=1, entry_price=Decimal("1.10"),
        )
        assert leg.intrinsic_at(Decimal("395")) == Decimal("5")
        assert leg.intrinsic_at(Decimal("405")) == Decimal("0")

    def test_invalid_qty(self) -> None:
        with pytest.raises(ValueError):
            OptionLeg(
                underlying="SPY", expiration="2024-02-16",
                strike=Decimal("400"), option_type=OptionType.PUT,
                side=Side.SHORT, qty=0, entry_price=Decimal("1.10"),
            )

    def test_invalid_strike(self) -> None:
        with pytest.raises(ValueError):
            OptionLeg(
                underlying="SPY", expiration="2024-02-16",
                strike=Decimal("0"), option_type=OptionType.PUT,
                side=Side.SHORT, qty=1, entry_price=Decimal("1.10"),
            )


# --- Iron Condor construction ---


def _spy_chain() -> MockChain:
    """Hand-crafted SPY chain at expiration 2024-02-16, spot ≈ 420."""
    return MockChain(
        quotes=[
            # Calls
            FakeQuote(Decimal("425"), OptionType.CALL, Decimal("1.10"), Decimal("1.30"), 0.20, "2024-02-16"),
            FakeQuote(Decimal("430"), OptionType.CALL, Decimal("0.50"), Decimal("0.70"), 0.10, "2024-02-16"),
            FakeQuote(Decimal("435"), OptionType.CALL, Decimal("0.20"), Decimal("0.40"), 0.05, "2024-02-16"),
            # Puts (delta is negative; |delta| matches target)
            FakeQuote(Decimal("415"), OptionType.PUT, Decimal("1.20"), Decimal("1.40"), -0.20, "2024-02-16"),
            FakeQuote(Decimal("410"), OptionType.PUT, Decimal("0.60"), Decimal("0.80"), -0.10, "2024-02-16"),
            FakeQuote(Decimal("405"), OptionType.PUT, Decimal("0.30"), Decimal("0.50"), -0.05, "2024-02-16"),
        ],
        expiration="2024-02-16",
    )


class TestIronCondorBuild:

    def test_picks_target_deltas(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor(
            "SPY", "2024-01-15", "2024-02-16", _spy_chain(), params
        )
        assert ic is not None
        # Verify selected strikes match target deltas.
        legs_by = {(leg.option_type, leg.side): leg for leg in ic.legs}
        assert legs_by[(OptionType.CALL, Side.SHORT)].strike == Decimal("425")
        assert legs_by[(OptionType.CALL, Side.LONG)].strike == Decimal("435")
        assert legs_by[(OptionType.PUT, Side.SHORT)].strike == Decimal("415")
        assert legs_by[(OptionType.PUT, Side.LONG)].strike == Decimal("405")

    def test_credit_calculation(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", _spy_chain(), params)
        assert ic is not None
        # Mids: SC=1.20, LC=0.30, SP=1.30, LP=0.40
        # Net credit = (1.20 - 0.30) + (1.30 - 0.40) = 0.90 + 0.90 = 1.80 / share
        # × 100 contract multiplier = $180.
        assert ic.credit == Decimal("180.00")

    def test_max_loss_equals_wing_minus_credit(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", _spy_chain(), params)
        assert ic is not None
        # Wider wing: 435-425 = 10 OR 415-405 = 10. Same width.
        # Max loss = wing × 100 - credit = 10×100 - 180 = $820.
        assert ic.max_loss == Decimal("820")
        # And max profit = credit when call+put wings are equidistant from spot.
        assert ic.max_profit == ic.credit

    def test_pnl_at_expiration_at_short_call(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", _spy_chain(), params)
        assert ic is not None
        # At spot=425 (short call strike):
        #   Short call intrinsic = 0 → keep 1.20 credit
        #   Long call intrinsic = 0 → lose 0.30 debit
        #   Short put intrinsic = 0 → keep 1.30 credit
        #   Long put intrinsic = 0 → lose 0.40 debit
        # Net = (1.20 - 0.30 + 1.30 - 0.40) × 100 = 180. Same as credit.
        assert ic.pnl_at_expiration(Decimal("425")) == Decimal("180")

    def test_pnl_at_expiration_above_long_call(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", _spy_chain(), params)
        assert ic is not None
        # At spot=440:
        #   Short call: -((440-425)*100) = -1500 (we owe), but kept 120 credit on open
        #   Long call:  +((440-435)*100) = +500, but paid 30 debit on open
        #   Short put:  0 intrinsic, kept 130 credit
        #   Long put:   0 intrinsic, paid 40 debit
        # Total = credit + sum(intrinsic_signed)
        # Credit = 180. Intrinsic signed = -1500 + 500 + 0 + 0 = -1000.
        # Total = 180 - 1000 = -820. Equals max loss (negative).
        assert ic.pnl_at_expiration(Decimal("440")) == Decimal("-820")

    def test_returns_none_if_chain_thin(self) -> None:
        # Empty chain.
        empty_chain = MockChain([], "2024-02-16")
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", empty_chain, params)
        assert ic is None

    def test_invalid_params_raise(self) -> None:
        with pytest.raises(ValueError):
            IronCondorParams(
                short_call_delta=0.05, long_call_delta=0.20,  # reversed
                short_put_delta=0.20, long_put_delta=0.05,
            ).validate()


class TestPosition:

    def test_multi_expiry_forbidden(self) -> None:
        with pytest.raises(ValueError, match="C1"):
            Position(
                legs=(
                    OptionLeg(
                        underlying="SPY", expiration="2024-02-16",
                        strike=Decimal("400"), option_type=OptionType.PUT,
                        side=Side.SHORT, qty=1, entry_price=Decimal("1"),
                    ),
                    OptionLeg(
                        underlying="SPY", expiration="2024-03-15",  # different
                        strike=Decimal("400"), option_type=OptionType.PUT,
                        side=Side.LONG, qty=1, entry_price=Decimal("0.5"),
                    ),
                ),
                structure="calendar",
                entry_date="2024-01-15",
            )

    def test_multi_underlying_forbidden(self) -> None:
        with pytest.raises(ValueError, match="underlying"):
            Position(
                legs=(
                    OptionLeg(
                        underlying="SPY", expiration="2024-02-16",
                        strike=Decimal("400"), option_type=OptionType.PUT,
                        side=Side.SHORT, qty=1, entry_price=Decimal("1"),
                    ),
                    OptionLeg(
                        underlying="QQQ", expiration="2024-02-16",
                        strike=Decimal("400"), option_type=OptionType.PUT,
                        side=Side.LONG, qty=1, entry_price=Decimal("0.5"),
                    ),
                ),
                structure="pair",
                entry_date="2024-01-15",
            )


class TestWingWidths:

    def test_known_widths(self) -> None:
        params = IronCondorParams(
            short_call_delta=0.20, long_call_delta=0.05,
            short_put_delta=0.20, long_put_delta=0.05,
        )
        ic = build_iron_condor("SPY", "2024-01-15", "2024-02-16", _spy_chain(), params)
        assert ic is not None
        assert call_wing_width(ic) == Decimal("10")
        assert put_wing_width(ic) == Decimal("10")
