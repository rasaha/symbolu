"""Exact minor-unit money.

Money is stored as an integer count of *minor units* (cents, paise, …) plus an
ISO-ish currency code. Arithmetic is exact; scaling by a ratio rounds once,
half-to-even, so results are deterministic and reproducible across platforms.
Cross-currency arithmetic fails closed — a portfolio must supply an explicit FX
step, never let two currencies add silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

from .errors import CurrencyMismatchError, GovernedValueError

__all__ = ["Money"]


@dataclass(frozen=True, order=False)
class Money:
    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.minor_units, int) or isinstance(self.minor_units, bool):
            raise GovernedValueError("minor_units must be an int (minor currency units)")
        if not self.currency or not self.currency.strip():
            raise GovernedValueError("currency must be a non-empty code")

    # -- constructors ----------------------------------------------------
    @staticmethod
    def zero(currency: str) -> "Money":
        return Money(0, currency)

    # -- guards ----------------------------------------------------------
    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"currency mismatch: {self.currency} vs {other.currency}"
            )

    # -- arithmetic ------------------------------------------------------
    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.minor_units + other.minor_units, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.minor_units - other.minor_units, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.minor_units, self.currency)

    def scaled(self, ratio: Decimal) -> "Money":
        """Multiply by a Decimal ratio, rounding once to the nearest minor unit."""

        scaled = (Decimal(self.minor_units) * ratio).quantize(
            Decimal(1), rounding=ROUND_HALF_EVEN
        )
        return Money(int(scaled), self.currency)

    # -- comparison (same currency only) ---------------------------------
    def __lt__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.minor_units < other.minor_units

    def __le__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.minor_units <= other.minor_units

    def __gt__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.minor_units > other.minor_units

    def __ge__(self, other: "Money") -> bool:
        self._same_currency(other)
        return self.minor_units >= other.minor_units

    @property
    def is_negative(self) -> bool:
        return self.minor_units < 0

    def __str__(self) -> str:
        return f"{self.minor_units} {self.currency} (minor units)"
