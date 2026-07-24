"""Domain-risk policy (Phase 8). Thresholds + policy version. Fail-closed on version mismatch."""
from __future__ import annotations

from dataclasses import dataclass

POLICY_VERSION = "agr_policy_v1"


@dataclass(frozen=True)
class GatePolicy:
    version: str = POLICY_VERSION
    allow_gap: float = 0.12          # gap <= this may ALLOW
    escalate_gap: float = 0.38       # high-risk overclaim >= this -> ESCALATE
    adequacy_floor: float = 0.40     # below -> not ALLOW
    uncertainty_ceiling: float = 0.35  # above -> uncertainty-driven withhold
    support_floor: float = 0.15      # below with no relation -> NOT_SUPPORTED

    def compatible(self, requested_version: str) -> bool:
        return requested_version == self.version
