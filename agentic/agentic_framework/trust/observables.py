"""
observables.py — the trust-observable taxonomy (Phase 1, product).

This formalizes the vocabulary the Agentic Framework already governs by, making the
distinction between *what the model claims* and *what an independent check infers*
explicit and typed. It introduces NO new ML and NO CG research features; it is the
type layer the proven gateway signals (raw entropy, confidence-risk gap, tool/action
risk, approvals) are mapped onto in `registry.py` and combined in `decision.py`.

Two orthogonal axes classify every observable:

  ObservableType — its ROLE in the decision
    HARD_VETO     a deterministic correctness check; UNSAFE → BLOCK (no override)
    VALIDATOR     an independent inferred check; can cap trust (CONFIRM) or block
    TRUST_SIGNAL  something the MODEL emits/claims; ASYMMETRIC — admitted doubt may
                  lower trust, a confident claim can NEVER raise it (claims are free)
    ADVISORY      surfaced for a human / logged; may escalate to CONFIRM, never blocks

  EvidenceStatus — how much AUTHORITY it has earned
    PROVEN        cleared the promotion gate; may act at its ObservableType authority
    PROVISIONAL   some evidence; capped at CONFIRM (advise/log) — never blocks
    RESEARCH      unproven (e.g. CG-state read-outs); RECORDED but NEVER affects the
                  decision, regardless of ObservableType

A `Verdict` is what one observation reports (SAFE / UNSURE / UNSAFE); a `TrustDecision`
is the gateway-facing outcome (ALLOW / CONFIRM / BLOCK).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class ObservableType(Enum):
    HARD_VETO = "hard_veto"
    VALIDATOR = "validator"
    TRUST_SIGNAL = "trust_signal"
    ADVISORY = "advisory"


class EvidenceStatus(Enum):
    PROVEN = "proven"
    PROVISIONAL = "provisional"
    RESEARCH = "research"


class Verdict(Enum):
    """What a single observation reports about the action."""
    SAFE = "safe"
    UNSURE = "unsure"
    UNSAFE = "unsafe"


class TrustDecision(Enum):
    """The gateway-facing outcome of combining observations."""
    ALLOW = "allow"
    CONFIRM = "confirm"   # requires human confirmation / escalation
    BLOCK = "block"


# Direction for TRUST_SIGNAL observations (drives the asymmetry rule).
TRUST_DOUBT = "doubt"          # model admits uncertainty/refuses → may LOWER trust
TRUST_CLAIM_SAFE = "claim_safe"  # model claims safe/confident → may NOT raise trust


@dataclass(frozen=True)
class Observation:
    """One reading from one observable.

    `severity` (0..1) does not change the discrete decision; it orders audit drivers
    (highest first) and is the seam a future fitted/calibrated score would consume.
    `direction` is only meaningful for TRUST_SIGNAL observations.
    """
    name: str
    otype: ObservableType
    evidence: EvidenceStatus
    verdict: Verdict
    severity: float = 0.0
    reason: str = ""
    direction: Optional[str] = None
    detail: Dict[str, object] = field(default_factory=dict)

    def to_audit(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "type": self.otype.value,
            "evidence": self.evidence.value,
            "verdict": self.verdict.value,
            "severity": round(float(self.severity), 4),
            "reason": self.reason,
            "direction": self.direction,
            **({"detail": self.detail} if self.detail else {}),
        }
