"""Decimal money arithmetic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ztech_sales.core.money import format_money, round_calculation, round_money, to_decimal


def test_float_is_rejected_outright():
    # A float has already lost precision by the time it reaches the helper, so
    # accepting one would hide the defect rather than prevent it.
    with pytest.raises(TypeError):
        to_decimal(1000.10)


def test_strings_and_decimals_are_accepted():
    assert to_decimal("1000.105") == Decimal("1000.105")
    assert to_decimal(Decimal("2.5")) == Decimal("2.5")
    assert to_decimal(7) == Decimal("7")


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        ("900", 3, "900.000"),
        ("45", 3, "45.000"),
        ("945", 3, "945.000"),
        ("1000.1005", 3, "1000.101"),  # half up
        ("1000.1004", 3, "1000.100"),
        ("12.345", 2, "12.35"),
        ("1234.56", 0, "1235"),
    ],
)
def test_round_money_uses_currency_precision(value, places, expected):
    assert format_money(value, places) == expected


def test_half_even_is_available_for_currencies_that_require_it():
    assert round_money("2.345", 2, "half_even") == Decimal("2.34")
    assert round_money("2.345", 2, "half_up") == Decimal("2.35")


def test_unknown_rounding_mode_is_refused():
    with pytest.raises(ValueError, match="Unknown rounding mode"):
        round_money("1.005", 2, "banker")


def test_intermediate_results_keep_more_precision_than_the_currency():
    # Working precision is wider than any supported currency so a chain of
    # operations does not accumulate rounding error before the final rounding.
    assert round_calculation(Decimal("1") / Decimal("3")) == Decimal("0.333333")


def test_omr_uses_three_decimal_places():
    # The fixture currency for this product is the Omani rial.
    assert format_money("945", 3) == "945.000"
    assert format_money("0.0005", 3) == "0.001"
