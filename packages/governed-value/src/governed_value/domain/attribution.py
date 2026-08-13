"""Attribution evidence — flags only, never monetary multipliers.

In a POST_DEPLOYMENT_VALUE calculation the benefit is *already realized and
already attributable* (that is the caller's contract). This kernel therefore
applies **no** realization / attribution / decay / locale multiplier to money —
doing so would discount realized benefit a second time. What remains here is
purely evidentiary: signals about whether the reported figure is defensible,
consumed by the scorer as scorability inputs, not as haircuts.

Realization rates, decay and locale performance are FORECAST concerns and are
deferred (GV-3f); they are intentionally absent from this stage.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["AttributionEvidence"]


@dataclass(frozen=True)
class AttributionEvidence:
    baseline_captured: bool
    holdout_or_staged: bool = False
    concurrent_changes: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.concurrent_changes, int) or isinstance(
            self.concurrent_changes, bool
        ):
            raise ValueError("concurrent_changes must be an int")
        if self.concurrent_changes < 0:
            raise ValueError("concurrent_changes must be >= 0")
