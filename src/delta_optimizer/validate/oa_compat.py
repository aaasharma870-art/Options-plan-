"""Option Alpha decision-tree DSL compatibility validator (Hard Constraint C1).

A bot config / Position is OA-buildable iff:
  - structure ∈ {long_stock, short_stock, long_option, short_option,
                 vertical_credit, vertical_debit, iron_condor, iron_butterfly}
  - all option legs share the same expiration (no calendars/diagonals)
  - structure type matches the actual leg layout (no IF labeled as IC, etc.)
  - entry filters use only OA-allowed conditions
  - exits use only OA-allowed exit types
  - per-bot limits respected: ≤ 5 scanner automations, ≤ 25 symbols,
    ≤ 25 concurrent positions

Anything outside that is rejected. No "warnings" — invalid configs are not
written to data/results/phase_3/accepted/.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from delta_optimizer.strategies.base import OptionType, Position, Side

# --- allowed sets (master prompt § C1) ---

ALLOWED_STRUCTURES = frozenset({
    "long_stock", "short_stock",
    "long_option", "short_option",
    "vertical_credit", "vertical_debit",
    "iron_condor", "iron_butterfly",
})

FORBIDDEN_STRUCTURES = frozenset({
    "calendar", "diagonal", "strangle", "straddle", "ratio",
    "butterfly_long", "condor_long",  # symmetric long structures aren't on the list
})

ALLOWED_ENTRY_FILTERS = frozenset({
    "delta", "dte", "iv_rank", "iv_percentile",
    "vix_level", "vix_vix3m", "vix_10d_high", "vix_velocity",
    "rsi", "macd", "ema", "adx", "bollinger", "keltner", "cci",
    "net_gex", "max_gex_strikes",
    "earnings_calendar", "fomc_cpi_nfp_calendar",
    "orb",  # only for OA's 10 supported tickers
    "regime_score_max",  # delta-optimizer's composite — counts as a derived filter
})

ALLOWED_EXIT_TYPES = frozenset({
    "profit_target_pct",
    "stop_loss_pct",
    "stop_loss_dollar",
    "trailing_stop",
    "dte_exit",
    "itm_close",
    "pdt_1day_wait",
    "regime_flip_exit",
})

# Per-bot caps (master prompt § C1)
MAX_SCANNERS_PER_BOT = 5
MAX_SYMBOLS_PER_BOT = 25
MAX_CONCURRENT_PER_BOT = 25


@dataclass
class CompatReport:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def __bool__(self) -> bool:
        return self.ok


# --- Structure validation (against an actual Position object) ---


def validate_position_structure(position: Position) -> CompatReport:
    """Verify a Position's actual leg layout matches its declared structure
    AND that the structure is OA-buildable."""
    errors: list[str] = []
    warnings: list[str] = []

    if position.structure not in ALLOWED_STRUCTURES:
        if position.structure in FORBIDDEN_STRUCTURES:
            errors.append(
                f"Structure '{position.structure}' is forbidden by C1 "
                f"(not in OA's decision-tree DSL)."
            )
        else:
            errors.append(
                f"Structure '{position.structure}' not in allowed set: "
                f"{sorted(ALLOWED_STRUCTURES)}"
            )
        return CompatReport(ok=False, errors=errors, warnings=warnings)

    # Position.__post_init__ already enforces single-expiry; double-check.
    expirations = {leg.expiration for leg in position.legs}
    if len(expirations) > 1:
        errors.append(f"Multi-expiry positions forbidden (got {expirations}).")

    # Structure-specific checks.
    if position.structure == "iron_condor":
        errors.extend(_check_iron_condor(position))
    elif position.structure == "iron_butterfly":
        errors.extend(_check_iron_butterfly(position))
    elif position.structure in ("vertical_credit", "vertical_debit"):
        errors.extend(_check_vertical(position, position.structure))
    elif position.structure in ("long_option", "short_option"):
        errors.extend(_check_single_option(position, position.structure))
    elif position.structure in ("long_stock", "short_stock"):
        errors.extend(_check_stock(position, position.structure))

    return CompatReport(ok=not errors, errors=errors, warnings=warnings)


def _check_iron_condor(p: Position) -> list[str]:
    errs: list[str] = []
    if len(p.legs) != 4:
        errs.append(f"iron_condor must have 4 legs; got {len(p.legs)}")
        return errs
    counts = Counter((leg.option_type, leg.side) for leg in p.legs)
    expected = Counter({
        (OptionType.CALL, Side.SHORT): 1,
        (OptionType.CALL, Side.LONG): 1,
        (OptionType.PUT, Side.SHORT): 1,
        (OptionType.PUT, Side.LONG): 1,
    })
    if counts != expected:
        errs.append(
            f"iron_condor leg layout invalid; expected 1 of each "
            f"(SC,LC,SP,LP), got {dict(counts)}"
        )
    # Strike ordering: long call > short call, long put < short put.
    sc = next(leg for leg in p.legs if leg.option_type == OptionType.CALL and leg.side == Side.SHORT)
    lc = next(leg for leg in p.legs if leg.option_type == OptionType.CALL and leg.side == Side.LONG)
    sp = next(leg for leg in p.legs if leg.option_type == OptionType.PUT and leg.side == Side.SHORT)
    lp = next(leg for leg in p.legs if leg.option_type == OptionType.PUT and leg.side == Side.LONG)
    if not (lc.strike > sc.strike):
        errs.append(f"iron_condor: long call strike ({lc.strike}) must be > short ({sc.strike})")
    if not (lp.strike < sp.strike):
        errs.append(f"iron_condor: long put strike ({lp.strike}) must be < short ({sp.strike})")
    return errs


def _check_iron_butterfly(p: Position) -> list[str]:
    errs: list[str] = []
    if len(p.legs) != 4:
        errs.append(f"iron_butterfly must have 4 legs; got {len(p.legs)}")
        return errs
    counts = Counter((leg.option_type, leg.side) for leg in p.legs)
    expected = Counter({
        (OptionType.CALL, Side.SHORT): 1,
        (OptionType.CALL, Side.LONG): 1,
        (OptionType.PUT, Side.SHORT): 1,
        (OptionType.PUT, Side.LONG): 1,
    })
    if counts != expected:
        errs.append(
            f"iron_butterfly leg layout invalid; expected 1 of each (SC,LC,SP,LP), got {dict(counts)}"
        )
    # Body strikes (short call, short put) must be equal.
    sc = next(leg for leg in p.legs if leg.option_type == OptionType.CALL and leg.side == Side.SHORT)
    sp = next(leg for leg in p.legs if leg.option_type == OptionType.PUT and leg.side == Side.SHORT)
    if sc.strike != sp.strike:
        errs.append(
            f"iron_butterfly body must share strike; SC={sc.strike}, SP={sp.strike}"
        )
    return errs


def _check_vertical(p: Position, structure: str) -> list[str]:
    errs: list[str] = []
    if len(p.legs) != 2:
        errs.append(f"{structure} must have 2 legs; got {len(p.legs)}")
        return errs
    types = {leg.option_type for leg in p.legs}
    if len(types) > 1:
        errs.append(f"{structure}: both legs must be same option_type; got {types}")
    sides = {leg.side for leg in p.legs}
    if sides != {Side.SHORT, Side.LONG}:
        errs.append(f"{structure} requires one SHORT and one LONG leg; got {sides}")
    # A vertical credit has the SHORT closer to ATM than the LONG.
    short = next(leg for leg in p.legs if leg.side == Side.SHORT)
    long = next(leg for leg in p.legs if leg.side == Side.LONG)
    is_call = short.option_type == OptionType.CALL
    if structure == "vertical_credit":
        # Bull put credit: short put higher strike than long put. Bear call credit:
        # short call lower strike than long call.
        if is_call and not (short.strike < long.strike):
            errs.append(
                f"vertical_credit (call): short strike {short.strike} should be < long {long.strike}"
            )
        if not is_call and not (short.strike > long.strike):
            errs.append(
                f"vertical_credit (put): short strike {short.strike} should be > long {long.strike}"
            )
    elif structure == "vertical_debit":
        if is_call and not (short.strike > long.strike):
            errs.append(
                f"vertical_debit (call): long strike {long.strike} should be < short {short.strike}"
            )
        if not is_call and not (short.strike < long.strike):
            errs.append(
                f"vertical_debit (put): long strike {long.strike} should be > short {short.strike}"
            )
    return errs


def _check_single_option(p: Position, structure: str) -> list[str]:
    errs: list[str] = []
    if len(p.legs) != 1:
        errs.append(f"{structure} must have 1 leg; got {len(p.legs)}")
        return errs
    leg = p.legs[0]
    expected_side = Side.LONG if structure == "long_option" else Side.SHORT
    if leg.side != expected_side:
        errs.append(f"{structure} requires side={expected_side.value}; got {leg.side.value}")
    return errs


def _check_stock(p: Position, structure: str) -> list[str]:
    # Stock positions are out of scope for delta-optimizer Phase 0-3, but the
    # validator should accept them since OA supports them.
    return []


# --- Bot-level validation (entry filters, exits, caps) ---


@dataclass
class BotSpec:
    """Minimal bot spec for OA-DSL validation. Mirrors the YAML in PROJECT_BRIEF.md."""

    bot_id: str
    structure: str
    underlyings: list[str]
    entry_filter_types: list[str]   # filter names actually used
    exit_types: list[str]           # exit names actually used
    n_scanner_automations: int
    max_concurrent: int


def validate_bot_spec(spec: BotSpec) -> CompatReport:
    """Verify a BotSpec against C1's allowed lists and per-bot caps."""
    errors: list[str] = []
    warnings: list[str] = []

    if spec.structure not in ALLOWED_STRUCTURES:
        errors.append(f"Structure '{spec.structure}' not OA-buildable.")

    if len(spec.underlyings) > MAX_SYMBOLS_PER_BOT:
        errors.append(
            f"Symbol count {len(spec.underlyings)} exceeds OA max {MAX_SYMBOLS_PER_BOT}"
        )

    if spec.n_scanner_automations > MAX_SCANNERS_PER_BOT:
        errors.append(
            f"Scanner automations {spec.n_scanner_automations} exceed OA max "
            f"{MAX_SCANNERS_PER_BOT}"
        )

    if spec.max_concurrent > MAX_CONCURRENT_PER_BOT:
        errors.append(
            f"max_concurrent {spec.max_concurrent} exceeds OA max {MAX_CONCURRENT_PER_BOT}"
        )

    bad_filters = [f for f in spec.entry_filter_types if f not in ALLOWED_ENTRY_FILTERS]
    if bad_filters:
        errors.append(f"Entry filters not in OA DSL: {bad_filters}")

    bad_exits = [e for e in spec.exit_types if e not in ALLOWED_EXIT_TYPES]
    if bad_exits:
        errors.append(f"Exit types not in OA DSL: {bad_exits}")

    return CompatReport(ok=not errors, errors=errors, warnings=warnings)


def assert_oa_compatible(spec_or_position) -> None:
    """Hard-fail wrapper. Use at the boundary where accepted bots are persisted.

    Raises ValueError listing every violation. Intended to make C1 violations
    structural — you can't accidentally write a non-OA-buildable bot to disk
    if you call this just before persistence.
    """
    if isinstance(spec_or_position, Position):
        report = validate_position_structure(spec_or_position)
    elif isinstance(spec_or_position, BotSpec):
        report = validate_bot_spec(spec_or_position)
    else:
        raise TypeError(f"Unknown spec type: {type(spec_or_position)}")
    if not report.ok:
        raise ValueError("OA DSL compatibility failed:\n  " + "\n  ".join(report.errors))
