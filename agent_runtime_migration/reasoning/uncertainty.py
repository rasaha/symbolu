"""Advisory uncertainty — may RAISE scrutiny, never authorize or lower scrutiny."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class UncertaintyNote:
    score: float          # [0,1], higher = more uncertain
    detail: str = ""

    @property
    def raises_scrutiny(self) -> bool:
        return self.score >= 0.7

    # Deliberately NO method that returns allow/deny. Uncertainty is advisory only.
