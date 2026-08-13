"""Total cost of ownership — the denominator, itemized so omission is visible.

The classic failure is a TCO that is really just inference spend. Each of the
seven components is ``Optional[Money]``: ``None`` means *not accounted* (the
scorer flags it and degrades the verdict), while an explicit ``Money.zero`` is a
deliberate accounting decision that this component is genuinely nil. That
distinction is the whole point — "we forgot monitoring" and "monitoring is free"
must not look identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .money import Money
from .rates import ONE

__all__ = ["CostToServe", "COST_COMPONENTS"]

# The seven components a defensible TCO must speak to.
COST_COMPONENTS = (
    "inference",
    "retries",
    "evals",
    "monitoring",
    "human_in_loop_review",
    "incident_remediation",
    "model_migration",
)


@dataclass(frozen=True)
class CostToServe:
    currency: str
    inference: Optional[Money] = None
    retries: Optional[Money] = None
    evals: Optional[Money] = None
    monitoring: Optional[Money] = None
    human_in_loop_review: Optional[Money] = None
    incident_remediation: Optional[Money] = None
    model_migration: Optional[Money] = None

    def __post_init__(self) -> None:
        for name in COST_COMPONENTS:
            component: Optional[Money] = getattr(self, name)
            if component is not None and component.currency != self.currency:
                raise ValueError(
                    f"cost component {name!r} currency {component.currency} "
                    f"!= {self.currency}"
                )

    def missing_components(self) -> tuple[str, ...]:
        """Components left unaccounted (``None``) — a TCO-completeness signal."""

        return tuple(n for n in COST_COMPONENTS if getattr(self, n) is None)

    def total(self, *, inference_multiplier: Decimal = ONE) -> Money:
        """Sum accounted components.

        ``inference_multiplier`` scales the inference line only — data-residency
        / sovereign hosting changes inference cost per action (geography), and
        nothing else in the TCO.
        """

        acc = Money.zero(self.currency)
        for name in COST_COMPONENTS:
            component: Optional[Money] = getattr(self, name)
            if component is None:
                continue
            if name == "inference" and inference_multiplier != ONE:
                component = component.scaled(inference_multiplier)
            acc = acc + component
        return acc
