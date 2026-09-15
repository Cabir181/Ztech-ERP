"""Decimal money helpers.

All monetary arithmetic happens on the server in :class:`decimal.Decimal`.
Floating point is never used for money anywhere in this application, and
monetary values cross the API as JSON strings (DRF is configured with
``COERCE_DECIMAL_TO_STRING``) so that a JavaScript client cannot silently lose
precision by parsing them as IEEE-754 doubles.

Precision is a property of the currency, not a constant: the Omani rial has
three decimal places, most currencies have two, and a few have none.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation

# Working precision for intermediate results, before the value is rounded to the
# currency's precision. Kept deliberately wider than any supported currency so
# that a chain of operations does not accumulate rounding error.
CALCULATION_PRECISION = 6
CALCULATION_QUANTIZER = Decimal(1).scaleb(-CALCULATION_PRECISION)

ROUNDING_MODES = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
}

DEFAULT_ROUNDING = "half_up"

# Quantity and percentage precision. Percentages are held to four places so that
# a discount such as 12.3456% survives a round trip unchanged.
QUANTITY_PRECISION = 4
PERCENT_PRECISION = 4
UNIT_PRICE_PRECISION = 6


def to_decimal(value: object) -> Decimal:
    """Coerce a value to Decimal without ever passing through float."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Guard rather than silently accept: a float has already lost precision
        # by the time it reaches here.
        raise TypeError("Monetary values must not be passed as float; use Decimal or str.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{value!r} is not a valid decimal number.") from exc


def quantizer(decimal_places: int) -> Decimal:
    return Decimal(1).scaleb(-decimal_places)


def round_money(value: object, decimal_places: int, rounding: str = DEFAULT_ROUNDING) -> Decimal:
    """Round ``value`` to a currency's precision.

    ``decimal_places`` comes from the currency record (3 for OMR, 2 for USD,
    0 for JPY) and ``rounding`` from the currency's configured rounding mode.
    """
    mode = ROUNDING_MODES.get(rounding)
    if mode is None:
        raise ValueError(f"Unknown rounding mode {rounding!r}; expected one of {sorted(ROUNDING_MODES)}.")
    return to_decimal(value).quantize(quantizer(decimal_places), rounding=mode)


def round_calculation(value: object) -> Decimal:
    """Round an intermediate result to the shared working precision."""
    return to_decimal(value).quantize(CALCULATION_QUANTIZER, rounding=ROUND_HALF_UP)


def format_money(value: object, decimal_places: int) -> str:
    """Render a monetary value as a fixed-precision string for documents and JSON."""
    return f"{round_money(value, decimal_places):.{decimal_places}f}"


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
