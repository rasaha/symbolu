"""ActionGate x ACP composition (V2 §3, §13).

Two layers answer two **different** questions about a cloud operation:

* **ActionGate** — *"is this operation authorized?"* Owns identity, RBAC,
  privilege monotonicity, separation-of-duties, approver quorum, nonce
  single-use, manifest-digest / action-hash binding, resourceVersion CAS, and
  policy operators (incl. ``MAX_BLAST_RADIUS`` over a *pre-supplied* fact). Its
  verdict is one of six outcomes.
* **ACP** — *"is this operation operationally safe against the live cluster
  right now?"* Owns readiness, live blast-radius, capacity/availability,
  rollback-available-now, freeze windows. Its verdict is a ``CloudRecommendation``.

This module does **not** reimplement ActionGate. It consumes the gate's already-
computed verdict as an opaque input token (``AuthorizationVerdict``, mirroring the
gate's six outcomes) and composes it with ACP's recommendation under two
non-negotiable safety invariants (§13):

1. **An ActionGate denial is never overridden by ACP.** ``DENY`` ⇒
   ``BLOCKED_BY_AUTHORIZATION`` regardless of what ACP found.
2. **An ACP hold cannot mint authorization.** ACP is shadow-only; it never emits
   an execution token. A permissive ACP result on a denied/pending action does
   nothing.

An operation may proceed **iff both layers pass**: the gate authorizes AND ACP
finds it operationally safe.

Stdlib-only. No ActionGate import — the gate's verdict is passed in.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .outcomes import CloudRecommendation, is_permissive


class AuthorizationVerdict(str, Enum):
    """Mirror of ActionGate's six outcomes (severity order per the reference).

    Passed in as the gate's already-computed decision. ACP never computes this.
    """
    DENY = "DENY"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    SIMULATE_AND_RETRY = "SIMULATE_AND_RETRY"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    ALLOW = "ALLOW"


# The gate has finally authorized only on these two outcomes.
_AUTHORIZES = frozenset({AuthorizationVerdict.ALLOW,
                         AuthorizationVerdict.ALLOW_WITH_CONSTRAINTS})
# Non-final gate states: the gate has neither denied nor authorized yet.
_PENDING = frozenset({AuthorizationVerdict.REQUEST_MORE_EVIDENCE,
                      AuthorizationVerdict.SIMULATE_AND_RETRY,
                      AuthorizationVerdict.ESCALATE_TO_HUMAN})


class CombinedOutcome(str, Enum):
    """The composed decision of both layers."""
    PROCEED = "PROCEED"                                # both layers pass
    BLOCKED_BY_AUTHORIZATION = "BLOCKED_BY_AUTHORIZATION"  # gate denied (ACP irrelevant)
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"    # gate not final
    HELD_BY_ACP = "HELD_BY_ACP"                        # authorized, but ACP unsafe-now


@dataclass(frozen=True)
class CompositionResult:
    """Immutable record of composing one gate verdict with one ACP recommendation."""
    authorization: AuthorizationVerdict
    acp_recommendation: CloudRecommendation
    combined: CombinedOutcome
    rationale: str

    @property
    def would_proceed(self) -> bool:
        return self.combined is CombinedOutcome.PROCEED

    @property
    def acp_was_decisive(self) -> bool:
        """True iff the gate authorized but ACP is what stopped it (HELD_BY_ACP)."""
        return self.combined is CombinedOutcome.HELD_BY_ACP


def compose(
    authorization: AuthorizationVerdict,
    acp_recommendation: CloudRecommendation,
) -> CompositionResult:
    """Compose a gate verdict with an ACP recommendation (§13 invariants).

    Precedence is deliberate and non-compensatory:
    1. gate ``DENY``          -> ``BLOCKED_BY_AUTHORIZATION`` (ACP cannot override)
    2. gate pending           -> ``PENDING_AUTHORIZATION``    (ACP cannot authorize)
    3. gate authorized + ACP permissive -> ``PROCEED``
    4. gate authorized + ACP not permissive -> ``HELD_BY_ACP``
    """
    if authorization is AuthorizationVerdict.DENY:
        return CompositionResult(
            authorization, acp_recommendation,
            CombinedOutcome.BLOCKED_BY_AUTHORIZATION,
            "ActionGate DENY is final; ACP cannot override an authorization denial")

    if authorization in _PENDING:
        return CompositionResult(
            authorization, acp_recommendation,
            CombinedOutcome.PENDING_AUTHORIZATION,
            f"ActionGate {authorization.value} is not a final authorization; "
            f"ACP is advisory until the gate resolves")

    # gate authorized (ALLOW / ALLOW_WITH_CONSTRAINTS)
    if authorization in _AUTHORIZES:
        if is_permissive(acp_recommendation):
            return CompositionResult(
                authorization, acp_recommendation, CombinedOutcome.PROCEED,
                "both layers pass: authorized AND operationally safe now")
        return CompositionResult(
            authorization, acp_recommendation, CombinedOutcome.HELD_BY_ACP,
            f"authorized by ActionGate but ACP {acp_recommendation.value}: "
            f"operationally unsafe against live cluster state")

    # defensive: unknown verdict fails closed
    return CompositionResult(  # pragma: no cover
        authorization, acp_recommendation, CombinedOutcome.HELD_BY_ACP,
        "unknown authorization verdict; failing closed")
