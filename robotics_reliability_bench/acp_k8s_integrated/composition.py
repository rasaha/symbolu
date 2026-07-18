"""Deterministic ActionGate x ACP composition for Kubernetes (V2.1 §5).

Composes a **real** ActionGate outcome with a **real** ACP operational-safety
result for one identity-bound Kubernetes operation, into one of eight closed
composition classes. The two decision schemas are NOT merged — this consumes each
layer's own verdict and never recomputes the other.

Ownership model (unchanged from V2 `BOUNDARY_CLEAN`):
* ActionGate owns authorization; its DENY can never be overridden.
* ACP owns operational safety; it can never grant authorization.
* ActionGate ALLOW does not override an ACP hard operational hold.
* Execution is hypothetically eligible only when BOTH layers pass.

Precedence (non-compensatory, evaluated top-down):
1. `COMPOSITION_IDENTITY_MISMATCH` — the layers are not bound to the same action.
2. `SHADOW_ERROR` — an evaluator failed (ACP `EVALUATOR_FAILED` or a raised exc).
3. authorization DENY + ACP hard hold  -> `BLOCKED_BY_BOTH`
4. authorization DENY                   -> `BLOCKED_BY_AUTHORIZATION`
5. authorization not final (needs evidence/sim/human) -> `REQUEST_MORE_EVIDENCE`
6. authorized + ACP state stale/missing -> `REQUEST_FRESH_OPERATIONAL_STATE`
7. authorized + ACP hard hold           -> `HELD_BY_OPERATIONAL_SAFETY`
8. authorized + ACP operationally safe  -> `AUTHORIZED_AND_OPERATIONALLY_SAFE`
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from symbolu_robotics.autonomous_control_plane.cloud import (
    CloudRecommendation,
    CloudValidity,
    is_permissive,
)


class CompositionClass(str, Enum):
    AUTHORIZED_AND_OPERATIONALLY_SAFE = "AUTHORIZED_AND_OPERATIONALLY_SAFE"
    BLOCKED_BY_AUTHORIZATION = "BLOCKED_BY_AUTHORIZATION"
    HELD_BY_OPERATIONAL_SAFETY = "HELD_BY_OPERATIONAL_SAFETY"
    BLOCKED_BY_BOTH = "BLOCKED_BY_BOTH"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    REQUEST_FRESH_OPERATIONAL_STATE = "REQUEST_FRESH_OPERATIONAL_STATE"
    COMPOSITION_IDENTITY_MISMATCH = "COMPOSITION_IDENTITY_MISMATCH"
    SHADOW_ERROR = "SHADOW_ERROR"


# ACP evidence validities that mean "cannot determine safety; need fresh state".
_STALE_MISSING = frozenset({CloudValidity.STALE, CloudValidity.MISSING})


@dataclass(frozen=True)
class CompositionOutcome:
    """Immutable composed result. Carries both layers' verdicts, not a merge."""
    composition_class: CompositionClass
    authorization_outcome: Optional[str]        # real ActionGate outcome string
    acp_recommendation: Optional[str]           # real ACP CloudRecommendation
    acp_validity: Optional[str]                 # real ACP evidence validity
    rationale: str

    @property
    def hypothetically_eligible(self) -> bool:
        """Execution is hypothetically eligible ONLY when both layers pass."""
        return (self.composition_class
                is CompositionClass.AUTHORIZED_AND_OPERATIONALLY_SAFE)

    @property
    def acp_was_decisive(self) -> bool:
        return self.composition_class in (
            CompositionClass.HELD_BY_OPERATIONAL_SAFETY,
            CompositionClass.REQUEST_FRESH_OPERATIONAL_STATE)


def compose(
    *,
    identity_bound: bool,
    identity_reason: str,
    authorization_outcome: Optional[str],
    is_authorized: bool,
    is_denied: bool,
    is_pending: bool,
    acp_recommendation: Optional[CloudRecommendation],
    acp_validity: Optional[CloudValidity],
    shadow_error: bool = False,
    error_kind: str = "",
) -> CompositionOutcome:
    """Compose one ActionGate + one ACP verdict into a CompositionClass."""
    ao = authorization_outcome
    ar = acp_recommendation.value if acp_recommendation is not None else None
    av = acp_validity.value if acp_validity is not None else None

    def out(cls: CompositionClass, why: str) -> CompositionOutcome:
        return CompositionOutcome(cls, ao, ar, av, why)

    # 1. identity binding is a hard precondition — fail closed.
    if not identity_bound:
        return out(CompositionClass.COMPOSITION_IDENTITY_MISMATCH,
                   f"layers not bound to one operation: {identity_reason}")

    # 2. any evaluator failure -> shadow error (fail closed, never proceed).
    if shadow_error or acp_validity is CloudValidity.EVALUATOR_FAILED:
        return out(CompositionClass.SHADOW_ERROR,
                   f"evaluator failure: {error_kind or 'ACP_EVALUATOR_FAILED'}")

    acp_hard_hold = (acp_validity is CloudValidity.VALID
                     and acp_recommendation is not None
                     and not is_permissive(acp_recommendation))
    acp_needs_fresh = (acp_validity in _STALE_MISSING
                       or acp_recommendation is CloudRecommendation.REOBSERVE)

    # 3-4. an authorization DENY is final and never overridden.
    if is_denied:
        if acp_hard_hold:
            return out(CompositionClass.BLOCKED_BY_BOTH,
                       "ActionGate DENY and ACP operational hold both block")
        return out(CompositionClass.BLOCKED_BY_AUTHORIZATION,
                   "ActionGate DENY is final; ACP cannot override it")

    # 5. authorization not final (SIMULATE_AND_RETRY / REQUEST_MORE_EVIDENCE /
    #    ESCALATE_TO_HUMAN) — ACP cannot authorize; the gate must resolve first.
    if is_pending:
        return out(CompositionClass.REQUEST_MORE_EVIDENCE,
                   f"ActionGate {ao} is not a final authorization")

    # authorized (ALLOW / ALLOW_WITH_CONSTRAINTS) from here on.
    if is_authorized:
        # 6. ACP cannot judge safety on stale/missing operational state.
        if acp_needs_fresh:
            return out(CompositionClass.REQUEST_FRESH_OPERATIONAL_STATE,
                       f"authorized, but ACP needs fresh operational state "
                       f"(validity={av}, rec={ar})")
        # 7. ACP hard operational hold — authorized but unsafe now.
        if acp_hard_hold:
            return out(CompositionClass.HELD_BY_OPERATIONAL_SAFETY,
                       "authorized by ActionGate but ACP operational hold")
        # 8. both layers pass.
        return out(CompositionClass.AUTHORIZED_AND_OPERATIONALLY_SAFE,
                   "authorized AND operationally safe now — hypothetically eligible")

    # defensive: unknown authorization state fails closed.
    return out(CompositionClass.SHADOW_ERROR,
               f"unhandled authorization outcome {ao}; failing closed")
