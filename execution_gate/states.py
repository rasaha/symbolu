"""Eligibility states, condition verdicts, criticality classes, and evidence.

Deterministic and dependency-free. `now` is always passed in (never read from the
system clock) so decisions are replayable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from execution_gate.reason_codes import ReasonCode


class EligibilityState(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    CONDITIONALLY_ELIGIBLE = "CONDITIONALLY_ELIGIBLE"
    INDETERMINATE = "INDETERMINATE"


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Criticality(str, Enum):
    CRITICAL_GOV = "CRITICAL_GOV"     # governance/compliance/legal -> always fail-closed
    CRITICAL_OP = "CRITICAL_OP"       # correctness/spend safety -> fail-closed by default
    OPERATIONAL = "OPERATIONAL"       # transient/QoS -> configurable


class EvidenceSource(str, Enum):
    LIVE_PROBE = "live_probe"
    TELEMETRY = "telemetry"
    CACHE = "cache"
    CONFIG = "config"
    PROVIDER_DECLARED = "provider_declared"


# fixed conflict-resolution precedence (higher wins)
SOURCE_PRECEDENCE = {
    EvidenceSource.LIVE_PROBE: 5, EvidenceSource.TELEMETRY: 4, EvidenceSource.CACHE: 3,
    EvidenceSource.CONFIG: 2, EvidenceSource.PROVIDER_DECLARED: 1,
}


@dataclass
class Evidence:
    source: EvidenceSource
    timestamp: float          # epoch seconds (passed in; never system clock)
    confidence: float         # [0,1]
    ttl_seconds: float
    raw_signal: Optional[str] = None   # raw provider string retained for audit ONLY

    def is_stale(self, now: float) -> bool:
        return (now - self.timestamp) > self.ttl_seconds


@dataclass
class ConditionResult:
    condition: str
    verdict: Verdict
    reason: ReasonCode
    criticality: Criticality
    evidence: Evidence
    detail: str = ""


@dataclass
class EligibilityDecision:
    provider: str
    model_id: str
    state: EligibilityState
    reasons: List[ReasonCode] = field(default_factory=list)
    conditions: List[ConditionResult] = field(default_factory=list)
    policy_version: str = "exec_gate_v1"
    evaluated_at: float = 0.0
    ttl_seconds: float = 0.0     # min TTL across cited evidence -> decision freshness

    @property
    def selectable(self) -> bool:
        return self.state in (EligibilityState.ELIGIBLE, EligibilityState.CONDITIONALLY_ELIGIBLE)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider, "model_id": self.model_id, "state": self.state.value,
            "reasons": [r.value for r in self.reasons], "policy_version": self.policy_version,
            "evaluated_at": self.evaluated_at, "ttl_seconds": self.ttl_seconds,
            "conditions": [{"condition": c.condition, "verdict": c.verdict.value,
                            "reason": c.reason.value, "criticality": c.criticality.value,
                            "evidence": {"source": c.evidence.source.value,
                                         "timestamp": c.evidence.timestamp,
                                         "confidence": c.evidence.confidence,
                                         "ttl_seconds": c.evidence.ttl_seconds,
                                         "raw_signal": c.evidence.raw_signal},
                            "detail": c.detail} for c in self.conditions],
        }
