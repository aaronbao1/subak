"""Money handling: Decimal only, never float. Two decimal places, no silent rounding."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

CENT = Decimal("0.01")
MAX_DECIMALS = 2


class MoneyError(ValueError):
    """Invalid money input. `code` matches validation reason codes in the design."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_money(value: Any) -> Decimal:
    """Parse str | int | Decimal into a Decimal quantized to cents.

    Rejects floats (`float_not_allowed`), bools, NaN/Inf, and inputs with more than two decimal
    places (`too_many_decimals`). Sign is preserved; positivity is a domain rule checked elsewhere.
    """
    if isinstance(value, bool):
        raise MoneyError("invalid_amount", "booleans are not money")
    if isinstance(value, float):
        raise MoneyError("float_not_allowed", "money must be a decimal string, not a float")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise MoneyError("invalid_amount", "empty money value")
        try:
            dec = Decimal(text)
        except InvalidOperation as exc:
            raise MoneyError("invalid_amount", f"not a decimal amount: {value!r}") from exc
    else:
        raise MoneyError("invalid_amount", f"unsupported money type: {type(value).__name__}")

    if not dec.is_finite():
        raise MoneyError("invalid_amount", "money must be finite")
    exponent = dec.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -MAX_DECIMALS:
        # Strict: "1.500" is rejected too. Rounding is never applied silently.
        raise MoneyError("too_many_decimals", f"at most {MAX_DECIMALS} decimal places: {value!r}")
    return dec.quantize(CENT)


def money_str(value: Decimal) -> str:
    """Canonical wire/storage form, e.g. Decimal('60000') -> '60000.00'."""
    return format(parse_money(value), "f")


class MoneyType(TypeDecorator):
    """Stores Decimal money as a canonical string in SQLite. Binding a float raises TypeError."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("float values cannot be stored as money; use Decimal or str")
        return money_str(parse_money(value))

    def process_result_value(self, value: Any, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(value)
