"""OA-DSL compatibility validator (C1) — exhaustive coverage of forbidden
structures, allowed structures, and per-bot caps."""

from __future__ import annotations

from decimal import Decimal

import pytest

from delta_optimizer.strategies.base import (
    OptionLeg,
    OptionType,
    Position,
    Side,
)
from delta_optimizer.strategies.iron_condor import IronCondorParams, build_iron_condor
from delta_optimizer.validate.oa_compat import (
    ALLOWED_ENTRY_FILTERS,
    ALLOWED_EXIT_TYPES,
    BotSpec,
    assert_oa_compatible,
    validate_bot_spec,
    validate_position_structure,
)


def _leg(strike, otype, side, price="1.00", exp="2024-02-16", qty=1) -> OptionLeg:
    return OptionLeg(
        underlying="SPY", expiration=exp, strike=Decimal(str(strike)),
        option_type=otype, side=side, qty=qty, entry_price=Decimal(price),
    )


def _ic_position() -> Position:
    return Position(
        legs=(
            _leg(425, OptionType.CALL, Side.SHORT, "1.20"),
            _leg(435, OptionType.CALL, Side.LONG, "0.30"),
            _leg(415, OptionType.PUT, Side.SHORT, "1.30"),
            _leg(405, OptionType.PUT, Side.LONG, "0.40"),
        ),
        structure="iron_condor",
        entry_date="2024-01-15",
    )


class TestPositionValidation:

    def test_valid_iron_condor(self) -> None:
        r = validate_position_structure(_ic_position())
        assert r.ok is True
        assert r.errors == []

    def test_iron_condor_wrong_leg_count(self) -> None:
        p = Position(
            legs=(
                _leg(425, OptionType.CALL, Side.SHORT, "1.20"),
                _leg(435, OptionType.CALL, Side.LONG, "0.30"),
            ),
            structure="iron_condor",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is False
        assert any("4 legs" in e for e in r.errors)

    def test_iron_condor_wrong_strike_order(self) -> None:
        # Long call strike INSIDE short call — invalid.
        p = Position(
            legs=(
                _leg(425, OptionType.CALL, Side.SHORT, "1.20"),
                _leg(420, OptionType.CALL, Side.LONG, "1.50"),  # bad: < short
                _leg(415, OptionType.PUT, Side.SHORT, "1.30"),
                _leg(405, OptionType.PUT, Side.LONG, "0.40"),
            ),
            structure="iron_condor",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is False
        assert any("long call strike" in e for e in r.errors)

    def test_iron_butterfly_body_strike(self) -> None:
        # Body short call & put must share strike.
        p = Position(
            legs=(
                _leg(420, OptionType.CALL, Side.SHORT, "2.00"),
                _leg(430, OptionType.CALL, Side.LONG, "0.50"),
                _leg(420, OptionType.PUT, Side.SHORT, "2.00"),
                _leg(410, OptionType.PUT, Side.LONG, "0.50"),
            ),
            structure="iron_butterfly",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is True

        p_bad = Position(
            legs=(
                _leg(420, OptionType.CALL, Side.SHORT, "2.00"),
                _leg(430, OptionType.CALL, Side.LONG, "0.50"),
                _leg(415, OptionType.PUT, Side.SHORT, "2.00"),  # mismatched body
                _leg(410, OptionType.PUT, Side.LONG, "0.50"),
            ),
            structure="iron_butterfly",
            entry_date="2024-01-15",
        )
        r2 = validate_position_structure(p_bad)
        assert r2.ok is False
        assert any("body must share strike" in e for e in r2.errors)

    def test_forbidden_structure_calendar(self) -> None:
        # Even before reaching the validator, Position rejects multi-expiry.
        # So we test by passing a single-expiry position labelled 'calendar'.
        p = Position(
            legs=(
                _leg(420, OptionType.CALL, Side.SHORT, "1"),
                _leg(420, OptionType.CALL, Side.LONG, "0.5"),
            ),
            structure="calendar",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is False
        assert any("forbidden" in e.lower() or "not in allowed" in e.lower()
                   for e in r.errors)

    def test_unknown_structure_rejected(self) -> None:
        p = Position(
            legs=(_leg(420, OptionType.CALL, Side.LONG, "1"),),
            structure="weird_thing",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is False

    def test_vertical_credit_call(self) -> None:
        p = Position(
            legs=(
                _leg(420, OptionType.CALL, Side.SHORT, "1.20"),  # closer to ATM
                _leg(425, OptionType.CALL, Side.LONG, "0.50"),
            ),
            structure="vertical_credit",
            entry_date="2024-01-15",
        )
        assert validate_position_structure(p).ok

    def test_vertical_credit_put(self) -> None:
        p = Position(
            legs=(
                _leg(415, OptionType.PUT, Side.SHORT, "1.20"),
                _leg(410, OptionType.PUT, Side.LONG, "0.50"),
            ),
            structure="vertical_credit",
            entry_date="2024-01-15",
        )
        assert validate_position_structure(p).ok

    def test_vertical_strike_order_wrong(self) -> None:
        # vertical_credit on calls but with short ABOVE long → rejected.
        p = Position(
            legs=(
                _leg(425, OptionType.CALL, Side.SHORT, "0.50"),
                _leg(420, OptionType.CALL, Side.LONG, "1.20"),
            ),
            structure="vertical_credit",
            entry_date="2024-01-15",
        )
        r = validate_position_structure(p)
        assert r.ok is False

    def test_assert_oa_compatible_raises(self) -> None:
        p = Position(
            legs=(_leg(420, OptionType.CALL, Side.LONG, "1"),),
            structure="weird_thing",
            entry_date="2024-01-15",
        )
        with pytest.raises(ValueError, match="OA DSL"):
            assert_oa_compatible(p)


class TestBotSpec:

    def test_valid_spec(self) -> None:
        spec = BotSpec(
            bot_id="ic_spy_green",
            structure="iron_condor",
            underlyings=["SPY"],
            entry_filter_types=["delta", "dte", "vix_level", "regime_score_max"],
            exit_types=["profit_target_pct", "stop_loss_pct", "dte_exit"],
            n_scanner_automations=2,
            max_concurrent=3,
        )
        assert validate_bot_spec(spec).ok

    def test_too_many_symbols(self) -> None:
        spec = BotSpec(
            bot_id="x",
            structure="iron_condor",
            underlyings=[f"T{i}" for i in range(30)],  # >25
            entry_filter_types=["delta"],
            exit_types=["profit_target_pct"],
            n_scanner_automations=1,
            max_concurrent=1,
        )
        r = validate_bot_spec(spec)
        assert r.ok is False
        assert any("Symbol count" in e for e in r.errors)

    def test_too_many_scanners(self) -> None:
        spec = BotSpec(
            bot_id="x", structure="iron_condor", underlyings=["SPY"],
            entry_filter_types=["delta"], exit_types=["profit_target_pct"],
            n_scanner_automations=10, max_concurrent=1,
        )
        r = validate_bot_spec(spec)
        assert any("Scanner automations" in e for e in r.errors)

    def test_too_many_concurrent(self) -> None:
        spec = BotSpec(
            bot_id="x", structure="iron_condor", underlyings=["SPY"],
            entry_filter_types=["delta"], exit_types=["profit_target_pct"],
            n_scanner_automations=1, max_concurrent=50,
        )
        r = validate_bot_spec(spec)
        assert any("max_concurrent" in e for e in r.errors)

    def test_unknown_filter(self) -> None:
        spec = BotSpec(
            bot_id="x", structure="iron_condor", underlyings=["SPY"],
            entry_filter_types=["delta", "ml_signal_42"],  # invented filter
            exit_types=["profit_target_pct"],
            n_scanner_automations=1, max_concurrent=1,
        )
        r = validate_bot_spec(spec)
        assert r.ok is False
        assert any("not in OA DSL" in e for e in r.errors)

    def test_unknown_exit(self) -> None:
        spec = BotSpec(
            bot_id="x", structure="iron_condor", underlyings=["SPY"],
            entry_filter_types=["delta"], exit_types=["telepathic_close"],
            n_scanner_automations=1, max_concurrent=1,
        )
        assert validate_bot_spec(spec).ok is False

    def test_assert_oa_compatible_botspec_raises(self) -> None:
        spec = BotSpec(
            bot_id="x", structure="diagonal",  # forbidden structure
            underlyings=["SPY"], entry_filter_types=["delta"],
            exit_types=["profit_target_pct"],
            n_scanner_automations=1, max_concurrent=1,
        )
        with pytest.raises(ValueError, match="OA DSL"):
            assert_oa_compatible(spec)


class TestAllowedSets:
    """Sanity: the canonical lists in PROJECT_BRIEF.md are reflected in code."""

    def test_iron_butterfly_in_structures(self) -> None:
        from delta_optimizer.validate.oa_compat import ALLOWED_STRUCTURES
        assert "iron_butterfly" in ALLOWED_STRUCTURES

    def test_strangle_not_in_structures(self) -> None:
        from delta_optimizer.validate.oa_compat import ALLOWED_STRUCTURES
        assert "strangle" not in ALLOWED_STRUCTURES

    def test_orb_in_filters(self) -> None:
        assert "orb" in ALLOWED_ENTRY_FILTERS

    def test_trailing_stop_in_exits(self) -> None:
        assert "trailing_stop" in ALLOWED_EXIT_TYPES
