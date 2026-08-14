"""Optional advisory composite record (ADR §5 D-5).

A composite is **advisory only**: it may compare systems within a tier but can
**never** determine, elevate, or change a readiness tier, override a mandatory
failure, or override missing required evidence. It uses ``Decimal`` (never binary
float), carries an explicit scale and a declared calculation/model version, and
references the component results it summarizes.

There is **no** default weight and **no** ``Intelligence × Capability × Adoption``
formula — if no versioned method is supplied the composite is simply absent
rather than fabricated. It is non-financial and is never multiplied into ROI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ._util import canonical_digest, normalize_tokens, require_decimal, require_nonempty, require_tzaware
from .errors import ReadinessContractError

__all__ = ["AdvisoryComposite"]


@dataclass(frozen=True)
class AdvisoryComposite:
    """An advisory, non-financial composite over component readiness results."""

    method_id: str
    method_version: str
    score: Decimal
    scale_min: Decimal
    scale_max: Decimal
    component_result_refs: tuple[str, ...]
    is_advisory: bool = True
    computed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_nonempty(self.method_id, "AdvisoryComposite.method_id")
        require_nonempty(self.method_version, "AdvisoryComposite.method_version")
        score = require_decimal(self.score, "AdvisoryComposite.score")
        lo = require_decimal(self.scale_min, "AdvisoryComposite.scale_min")
        hi = require_decimal(self.scale_max, "AdvisoryComposite.scale_max")
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "scale_min", lo)
        object.__setattr__(self, "scale_max", hi)
        if not lo < hi:
            raise ReadinessContractError("AdvisoryComposite.scale_min must be < scale_max")
        if not (lo <= score <= hi):
            raise ReadinessContractError("AdvisoryComposite.score must lie within [scale_min, scale_max]")
        if self.is_advisory is not True:
            raise ReadinessContractError(
                "AdvisoryComposite.is_advisory must be True — a composite can never determine a tier (D-5)"
            )
        refs = normalize_tokens(self.component_result_refs, "AdvisoryComposite.component_result_refs")
        if not refs:
            raise ReadinessContractError("AdvisoryComposite requires component_result_refs")
        object.__setattr__(self, "component_result_refs", refs)
        if self.computed_at is not None:
            require_tzaware(self.computed_at, "AdvisoryComposite.computed_at")

    def canonical_digest(self) -> str:
        return canonical_digest(self)
