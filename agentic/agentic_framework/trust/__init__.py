"""
Trust-Observable layer (Phase 1, product).

The explicit, typed formalization of the Agentic Framework's PROVEN governance signals
— raw entropy, the confidence-risk gap, tool/action risk, tool validity, approvals,
budget — combined by an asymmetric, staged, weakest-link decision model into
ALLOW / CONFIRM / BLOCK with an auditable driver trail.

This module adds NO new ML and NO CG research features. CG-state read-outs
(vritti/guna/kosha/JEPA/Bhava/CSR) are declared RESEARCH and never affect the decision.
See AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md and ./README.md.

Typical use::

    from agentic.agentic_framework.trust import observe_tool_call, decide
    obs = observe_tool_call(tool_risk_level="write", raw_entropy=0.9,
                            verbalized_safety_confidence=0.95)
    outcome = decide(obs)        # TrustDecision.CONFIRM
    audit = outcome.to_audit()   # which observable drove it
"""

from agentic.agentic_framework.trust.decision import TrustOutcome, decide
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    TRUST_CLAIM_SAFE,
    TRUST_DOUBT,
    TrustDecision,
    Verdict,
)
from agentic.agentic_framework.trust.registry import (
    CG_RESEARCH_OBSERVABLES,
    PRODUCT_OBSERVABLES,
    observe_tool_call,
)

__all__ = [
    "ObservableType", "EvidenceStatus", "Verdict", "TrustDecision", "Observation",
    "TRUST_DOUBT", "TRUST_CLAIM_SAFE",
    "decide", "TrustOutcome",
    "observe_tool_call", "PRODUCT_OBSERVABLES", "CG_RESEARCH_OBSERVABLES",
    "TrustMode",
]


def __getattr__(name):  # lazy: keep the decision core importable without parity deps
    if name == "TrustMode":
        from agentic.agentic_framework.trust.parity import TrustMode
        return TrustMode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
