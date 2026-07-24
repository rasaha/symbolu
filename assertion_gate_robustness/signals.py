"""Signal model (Phase 2). Each signal carries value + confidence + provenance + timestamp, and
explicit missing/conflict behavior. No signal is authoritative for ALLOW; only entailment=
contradicts (high confidence) may independently drive REJECT. Deterministic; stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
HIGH_RISK = ("high", "critical")


@dataclass
class Grounding:
    support: float                      # [0,1]
    confidence: float = 1.0
    provenance: str = "unknown"

    def bucket(self) -> str:
        s = self.support
        return "none" if s < 0.15 else "weak" if s < 0.4 else "partial" if s < 0.7 else "strong"


@dataclass
class Entailment:
    label: str = "neutral"              # supports | contradicts | neutral
    confidence: float = 1.0


@dataclass
class EvidenceMeta:
    adequacy: float = 1.0               # [0,1]
    age_days: float = 0.0
    required_recency_days: float = 3650.0
    authority: str = "authorized"       # authorized | unauthorized | unknown
    conflict: str = "none"              # none | minor | major
    provenance_present: bool = True

    def is_stale(self) -> bool:
        return self.age_days > self.required_recency_days


@dataclass
class SignalBundle:
    """The full noisy input to the gate for one claim unit."""
    grounding: Grounding
    entailment: Entailment
    evidence: EvidenceMeta
    risk_class: str = "medium"
    # per-signal calibration (reliability of the producing component)
    grounding_calibration: float = 1.0
    entailment_calibration: float = 1.0
    risk_calibration: float = 1.0

    def high_risk(self) -> bool:
        return self.risk_class in HIGH_RISK

    def effective_support(self) -> float:
        """Support discounted by grounding confidence*calibration, authority, and staleness."""
        s = self.grounding.support * self.grounding.confidence * self.grounding_calibration
        if self.evidence.authority == "unauthorized":
            s *= 0.5
        elif self.evidence.authority == "unknown":
            s *= 0.8
        if self.evidence.is_stale():
            s *= 0.6
        return max(0.0, min(1.0, s))

    def uncertainty(self) -> float:
        """Aggregate uncertainty in the signal bundle (0=certain .. 1=very uncertain)."""
        parts = [1 - self.grounding.confidence * self.grounding_calibration,
                 1 - self.entailment.confidence * self.entailment_calibration,
                 1 - self.risk_calibration,
                 1 - self.evidence.adequacy,
                 0.5 if self.evidence.conflict == "major" else 0.2 if self.evidence.conflict == "minor" else 0.0,
                 0.4 if self.evidence.is_stale() else 0.0,
                 0.3 if not self.evidence.provenance_present else 0.0]
        return max(0.0, min(1.0, sum(parts) / len(parts) * 2))
