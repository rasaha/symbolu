"""The ratified evidence lifecycle transition relation (ADR §28).

ADR §28 draws the evidence lifecycle as a fixed sequence of stages with two
terminal exits. This module encodes exactly those arrows as a **closed
relation** — nothing else is admissible, and a transition outside it is a
fail-closed refusal with a stable typed reason (E-9), never a warning and never
a silent apply.

The arrows, and where each comes from
-------------------------------------
=========================  ===========================================
Arrow                      ADR §28 source
=========================  ===========================================
``PRODUCED -> SUBMITTED``  "produce evidence -> collect / submit"
``SUBMITTED -> RETAINED``  "register / retain" follows submission
``* -> EXPIRED``           §11 row 10 — evidence becomes stale/expired
``* -> REVOKED``           §11 row 15 / §28 "revoke evidence"
=========================  ===========================================

``EXPIRED`` and ``REVOKED`` are **terminal**. Nothing leaves ``REVOKED``:
§17.11's discipline is that revocation is verified *before* denial is applied,
so an un-revoke would be an unsigned authority decision of exactly the kind
§26.9 prohibits. Nothing leaves ``EXPIRED`` either — evidence does not become
un-stale; a fresher observation is *new evidence* with its own identity and its
own digest.

There is no self-transition: ``PRODUCED -> PRODUCED`` is not a transition and is
refused, so "no change" can never be recorded as lifecycle movement.

There is no supersession arrow
------------------------------
The ratified *evidence* lifecycle has none. Supersession appears only in the
*benchmark* lifecycle (§29) and is deferred there to DD-4. This module does not
invent an evidence analogue, and :mod:`.reasons` ships no evidence-supersession
code to pair with one.

Verification is not a lifecycle state
-------------------------------------
§28 places verification *outside* the artifact's own state: TAP verifies and
issues a **signed receipt** (E-11), which is a separate artifact, not a word the
evidence applies to itself. There is therefore no ``VERIFIED`` node in this
relation, and no arrow into one.
"""

from __future__ import annotations

from types import MappingProxyType

from .enums import EvidenceLifecycleState
from .errors import TrustedEvidenceLifecycleError

__all__ = [
    "EVIDENCE_LIFECYCLE_TRANSITIONS",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
]

_S = EvidenceLifecycleState

#: The closed transition relation of ADR §28: current state -> admissible next
#: states, as an immutable mapping of immutable frozensets.
#:
#: Exposed as a read-only :class:`~types.MappingProxyType` over frozensets so a
#: caller cannot widen the relation after import — a mutable relation would let
#: any consumer authorize a transition the ADR does not ratify.
EVIDENCE_LIFECYCLE_TRANSITIONS = MappingProxyType(
    {
        _S.PRODUCED: frozenset({_S.SUBMITTED, _S.EXPIRED, _S.REVOKED}),
        _S.SUBMITTED: frozenset({_S.RETAINED, _S.EXPIRED, _S.REVOKED}),
        _S.RETAINED: frozenset({_S.EXPIRED, _S.REVOKED}),
        _S.EXPIRED: frozenset(),
        _S.REVOKED: frozenset(),
    }
)


def _require_state(value: object, name: str) -> EvidenceLifecycleState:
    if type(value) is not EvidenceLifecycleState:
        raise TrustedEvidenceLifecycleError(
            f"{name} must be exactly an EvidenceLifecycleState "
            f"(got {type(value).__name__}); a lookalike carrying a matching "
            "value is refused because the relation is closed over this type"
        )
    return value


def is_valid_lifecycle_transition(
    current: EvidenceLifecycleState, proposed: EvidenceLifecycleState
) -> bool:
    """Return whether ``current -> proposed`` is a ratified ADR §28 arrow.

    A pure predicate over the closed relation. It reads no clock and consults no
    external state, and it establishes **nothing** about trust: a valid
    transition is still only a statement the artifact makes about itself
    (ADR §10.2).
    """

    _require_state(current, "current")
    _require_state(proposed, "proposed")
    return proposed in EVIDENCE_LIFECYCLE_TRANSITIONS[current]


def require_valid_lifecycle_transition(
    current: EvidenceLifecycleState, proposed: EvidenceLifecycleState
) -> None:
    """Raise :class:`TrustedEvidenceLifecycleError` unless the arrow is ratified.

    The raised error carries
    ``reason == TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION``, so a caller
    that refuses on it reports the same stable typed code an admission-time
    refusal would.
    """

    if not is_valid_lifecycle_transition(current, proposed):
        admissible = sorted(
            s.value for s in EVIDENCE_LIFECYCLE_TRANSITIONS[current]
        )
        raise TrustedEvidenceLifecycleError(
            f"{current.value} -> {proposed.value} is not a ratified evidence "
            f"lifecycle transition (ADR §28); admissible next states from "
            f"{current.value}: {admissible or 'none — terminal state'}"
        )
