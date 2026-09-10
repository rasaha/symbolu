"""Eligibility states, condition verdicts, criticality classes, and evidence.

Deterministic and dependency-free. `now` is always passed in (never read from the
system clock) so decisions are replayable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .reason_codes import ReasonCode
from .version import POLICY_VERSION, SUPPORTED_POLICY_VERSIONS


class UnsupportedPolicyVersionError(ValueError):
    """A stored decision names a policy version this code cannot replay.

    Raised on read, never on write. It covers both an unknown version and a *newer* one
    written by a future release: in either case this code does not know the semantics the
    record was produced under, and reconstructing it would be asserting an equivalence
    nobody established. Refusing is the only honest answer.
    """

    def __init__(self, policy_version: object) -> None:
        super().__init__(
            f"cannot replay a decision stamped {policy_version!r}; this build reads "
            f"{list(SUPPORTED_POLICY_VERSIONS)}")
        self.policy_version = policy_version


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
    policy_version: str = POLICY_VERSION
    evaluated_at: float = 0.0
    ttl_seconds: float = 0.0     # min TTL across cited evidence -> decision freshness

    @property
    def selectable(self) -> bool:
        return self.state in (EligibilityState.ELIGIBLE, EligibilityState.CONDITIONALLY_ELIGIBLE)

    @classmethod
    def from_dict(cls, data: dict) -> "EligibilityDecision":
        """Reconstruct a stored decision record, for replay and verification.

        The inverse of :meth:`to_dict`, and the reason a policy-version bump costs
        historical records nothing: a record stamped with any version in
        ``SUPPORTED_POLICY_VERSIONS`` is read back exactly as it was written, including
        its own stamp, its condition list and its evidence. A v1 record has fifteen
        conditions and no ``quality_within_floor``; that is not a defect to repair, it is
        what a v1 decision was, and it round-trips unchanged.

        Nothing is recomputed and nothing is upgraded. This reads a record; it does not
        re-decide it, and it never re-stamps one with the current version.
        """
        version = data.get("policy_version")
        if version not in SUPPORTED_POLICY_VERSIONS:
            raise UnsupportedPolicyVersionError(version)

        conditions = [
            ConditionResult(
                condition=c["condition"],
                verdict=Verdict(c["verdict"]),
                reason=ReasonCode(c["reason"]),
                criticality=Criticality(c["criticality"]),
                evidence=Evidence(
                    source=EvidenceSource(c["evidence"]["source"]),
                    timestamp=c["evidence"]["timestamp"],
                    confidence=c["evidence"]["confidence"],
                    ttl_seconds=c["evidence"]["ttl_seconds"],
                    raw_signal=c["evidence"].get("raw_signal"),
                ),
                detail=c.get("detail", ""),
            )
            for c in data.get("conditions", [])
        ]
        return cls(
            provider=data["provider"],
            model_id=data["model_id"],
            state=EligibilityState(data["state"]),
            reasons=[ReasonCode(r) for r in data.get("reasons", [])],
            conditions=conditions,
            policy_version=version,
            evaluated_at=data.get("evaluated_at", 0.0),
            ttl_seconds=data.get("ttl_seconds", 0.0),
        )

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
