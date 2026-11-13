"""A money value type.

Amounts are ``Decimal`` values held at the currency's number of minor units
(2 for USD, 0 for JPY, 3 for KWD). Every operation that has to round uses
banker's rounding (round half to even). Arithmetic and comparison between
different currencies raise :class:`CurrencyMismatch`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation

__all__ = ["MINOR_UNITS", "CurrencyMismatch", "Money", "sum_money"]

MINOR_UNITS: dict[str, int] = {
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CHF": 2,
    "JPY": 0,
    "KWD": 3,
}


class CurrencyMismatch(ValueError):
    pass


def _exponent(currency: str) -> Decimal:
    return Decimal(1).scaleb(-MINOR_UNITS[currency])


@dataclass(frozen=True, order=False)
class Money:
    amount: Decimal
    currency: str

    @classmethod
    def of(cls, amount: Decimal | int | str, currency: str) -> Money:
        """Build a Money value, rounding ``amount`` to the currency's minor units."""
        code = currency.upper()
        if code not in MINOR_UNITS:
            raise ValueError(f"unknown currency {currency!r}")
        if isinstance(amount, float):
            raise TypeError("use str or Decimal amounts, not float")
        try:
            value = Decimal(amount)
        except InvalidOperation:
            raise ValueError(f"invalid amount {amount!r}") from None
        return cls(value.quantize(_exponent(code), rounding=ROUND_HALF_EVEN), code)

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls.of(0, currency)

    def _check(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise TypeError(f"expected Money, got {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")
        return other

    def __add__(self, other: Money) -> Money:
        return Money(self.amount + self._check(other).amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        return Money(self.amount - self._check(other).amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: int | Decimal | str) -> Money:
        if isinstance(factor, (float, Money)):
            raise TypeError("multiply by an int, str or Decimal")
        raw = self.amount * Decimal(factor)
        return Money(raw.quantize(_exponent(self.currency), rounding=ROUND_HALF_UP), self.currency)

    __rmul__ = __mul__

    def __lt__(self, other: Money) -> bool:
        return self.amount < self._check(other).amount

    def __le__(self, other: Money) -> bool:
        return self.amount <= self._check(other).amount

    def is_zero(self) -> bool:
        return self.amount == 0

    def allocate(self, ratios: Sequence[int]) -> list[Money]:
        """Split into parts proportional to ``ratios`` without losing a minor unit.

        Leftover minor units go one each to the first parts.
        """
        if not ratios or any(r < 0 for r in ratios) or sum(ratios) == 0:
            raise ValueError("ratios must be non-negative and not all zero")
        unit = _exponent(self.currency)
        total_units = int(self.amount / unit)
        total = sum(ratios)
        shares = [total_units * r // total for r in ratios]
        remainder = total_units - sum(shares)
        for i in range(remainder):
            shares[i] += 1
        return [Money(Decimal(s) * unit, self.currency) for s in shares]

    def amount_str(self, *, thousands: bool = False) -> str:
        """The amount alone, e.g. ``1234.50`` (``1,234.50`` with ``thousands``)."""
        grouping = "," if thousands else ""
        return f"{self.amount:{grouping}.{MINOR_UNITS[self.currency]}f}"

    def format(self) -> str:
        """Human-readable form with thousands separators, e.g. ``USD 1,234.50``."""
        return f"{self.currency} {self.amount_str(thousands=True)}"

    def __str__(self) -> str:
        return self.format()


def sum_money(items: Iterable[Money], currency: str | None = None) -> Money:
    """Add up ``items``. ``currency`` is required when ``items`` may be empty."""
    total: Money | None = Money.zero(currency) if currency else None
    for item in items:
        total = item if total is None else total + item
    if total is None:
        raise ValueError("cannot sum an empty sequence without a currency")
    return total
