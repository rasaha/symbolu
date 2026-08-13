"""Domain and geography as *modifiers* on the spine's terms.

Domain sets the natural value unit and the error asymmetry; geography moves the
denominator (TCO) more than the numerator. Neither is a separate framework —
each only reshapes terms the spine already has.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .enums import DomainKind, ValueSource
from .rates import ONE, nonneg_multiplier, unit_ratio

__all__ = ["DomainProfile", "GeographyProfile"]


@dataclass(frozen=True)
class DomainProfile:
    """Domain modifier: the natural unit, the dominant source, the error floor.

    ``min_severity`` operationalizes error asymmetry: in high-consequence
    domains (health, legal, credit) a wrong action's severity cannot be priced
    below a floor, so an under-priced error term is caught rather than allowed
    to flatter the ROI. That is the whole argument for measuring at the point of
    authorization rather than at the point of output.
    """

    kind: DomainKind
    natural_unit: str
    dominant_source: ValueSource
    min_severity: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if self.min_severity is not None:
            object.__setattr__(
                self, "min_severity", unit_ratio(self.min_severity, "min_severity")
            )


@dataclass(frozen=True)
class GeographyProfile:
    """Geography modifier: two of its three effects land on the denominator.

    - ``regulatory_load_minor_units`` — EU AI Act tiering, DPDP, sectoral rules
      add to TCO *and* raise avoided-loss value simultaneously. The scorer adds
      it to TCO and emits an advisory to also count the avoided-loss side; it
      must not be silently netted.
    - ``residency_inference_multiplier`` — data residency / sovereign hosting
      change inference cost per action (scales the inference TCO line only).
    - ``locale_realization_rate`` — language / locale performance change the
      *realization* rate, not the theoretical value (scales the numerator).
    """

    label: str
    currency: str
    regulatory_load_minor_units: int = 0
    residency_inference_multiplier: Decimal = ONE
    locale_realization_rate: Decimal = ONE

    def __post_init__(self) -> None:
        if not isinstance(self.regulatory_load_minor_units, int) or isinstance(
            self.regulatory_load_minor_units, bool
        ):
            raise ValueError("regulatory_load_minor_units must be an int")
        if self.regulatory_load_minor_units < 0:
            raise ValueError("regulatory_load_minor_units must be >= 0")
        object.__setattr__(
            self,
            "residency_inference_multiplier",
            nonneg_multiplier(
                self.residency_inference_multiplier, "residency_inference_multiplier"
            ),
        )
        object.__setattr__(
            self,
            "locale_realization_rate",
            unit_ratio(self.locale_realization_rate, "locale_realization_rate"),
        )
