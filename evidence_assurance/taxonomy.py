"""EvidenceAssurance disposition vocabulary (Phase 11 enum; formal freeze doc in VOCABULARY_V1.md).
These are EVIDENCE-STATE dispositions, kept separate from AssertionGate DELIVERY dispositions.
"""
from __future__ import annotations

from enum import Enum


class EvidenceState(str, Enum):
    VERIFIED = "VERIFIED"                              # supported by aligned, independent, authoritative, fresh evidence
    VERIFIED_WITH_LIMITATIONS = "VERIFIED_WITH_LIMITATIONS"  # supported but with a caveat (e.g. single-source, narrower scope)
    CONFLICTED = "CONFLICTED"                          # credible counterevidence / authoritative conflict
    INSUFFICIENT = "INSUFFICIENT"                      # not enough independent support
    STALE = "STALE"                                    # evidence outdated / superseded
    MISALIGNED = "MISALIGNED"                          # cited passage does not support THIS claim (scope/population/time/juris)
    DEPENDENT = "DEPENDENT"                            # apparent corroboration is not independent
    AUTHORITY_MISMATCH = "AUTHORITY_MISMATCH"          # source not authoritative for the domain/decision
    INDETERMINATE = "INDETERMINATE"                    # cannot decide (unknown provenance / missing metadata)
    REJECT_EVIDENCE_STATE = "REJECT_EVIDENCE_STATE"    # evidence contradicts the claim / fabricated
    ESCALATE = "ESCALATE"                              # needs human/external verification


# AssertionGate DELIVERY effect implied by an evidence state (adapter contract, Phase 14).
# high_risk raises INSUFFICIENT/STALE/DEPENDENT toward ESCALATE.
DELIVERY_EFFECT = {
    EvidenceState.VERIFIED: "ALLOW",
    EvidenceState.VERIFIED_WITH_LIMITATIONS: "QUALIFY",
    EvidenceState.CONFLICTED: "ESCALATE",
    EvidenceState.INSUFFICIENT: "INDETERMINATE",
    EvidenceState.STALE: "QUALIFY",
    EvidenceState.MISALIGNED: "REJECT",
    EvidenceState.DEPENDENT: "QUALIFY",                # claim may be fine, but corroboration is single-source
    EvidenceState.AUTHORITY_MISMATCH: "ESCALATE",
    EvidenceState.INDETERMINATE: "INDETERMINATE",
    EvidenceState.REJECT_EVIDENCE_STATE: "REJECT",
    EvidenceState.ESCALATE: "ESCALATE",
}

# states that must NOT be delivered as a positive supported claim (escape = ALLOW here)
UNSUPPORTED_STATES = {EvidenceState.CONFLICTED.value, EvidenceState.INSUFFICIENT.value,
                      EvidenceState.MISALIGNED.value, EvidenceState.AUTHORITY_MISMATCH.value,
                      EvidenceState.REJECT_EVIDENCE_STATE.value, EvidenceState.ESCALATE.value,
                      EvidenceState.INDETERMINATE.value}

# conservativeness order for adjudication (higher = more restrictive)
CONSERVATISM = {
    EvidenceState.VERIFIED.value: 0, EvidenceState.VERIFIED_WITH_LIMITATIONS.value: 1,
    EvidenceState.DEPENDENT.value: 2, EvidenceState.STALE.value: 2,
    EvidenceState.INSUFFICIENT.value: 3, EvidenceState.INDETERMINATE.value: 3,
    EvidenceState.MISALIGNED.value: 4, EvidenceState.AUTHORITY_MISMATCH.value: 4,
    EvidenceState.CONFLICTED.value: 4, EvidenceState.ESCALATE.value: 5,
    EvidenceState.REJECT_EVIDENCE_STATE.value: 5,
}


def delivered_as_supported(state: str) -> bool:
    """True if this evidence state would deliver the claim as a positive supported statement."""
    return state in (EvidenceState.VERIFIED.value, EvidenceState.VERIFIED_WITH_LIMITATIONS.value)


def more_conservative(a: str, b: str) -> str:
    return a if CONSERVATISM[a] >= CONSERVATISM[b] else b
