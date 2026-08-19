"""One structural representation per transition, shipped as an asserted mapping.

Six transitions, six bindings, and the binding is **data**, not a convention::

    initial              → SUBMITTED    BenchmarkSubmissionRecordPayload
    SUBMITTED → ADMITTED               BenchmarkAdmissionDecisionPayload (ADMITTED)
    SUBMITTED → REJECTED               BenchmarkAdmissionDecisionPayload (REJECTED)
    ADMITTED  → REJECTED               BenchmarkPostAdmissionRejectionEventPayload
    ADMITTED  → REGISTERED             BenchmarkRegistrationEventPayload
    REGISTERED→ REVOKED                BenchmarkRevocationEventPayload

**No payload type may serve a transition it is not bound to, and no transition
may accept a second payload type.** Both halves are asserted by
``tests/contract/test_transition_binding.py``, and the mapping is immutable.

Why the admission decision appears twice
-----------------------------------------
:class:`~.chain.BenchmarkAdmissionDecisionPayload` is bound to two transitions
because both leave the **same predecessor state** (``SUBMITTED``) and nest the
**same predecessor objects**. They are distinguished by ``declared_outcome``,
which is a digest-participating field of the payload — so the binding names the
required outcome, and a payload whose outcome disagrees is not the
representation of that transition.

``ADMITTED → REJECTED`` is deliberately **not** a third use of that type: it
leaves a different predecessor state and nests a different predecessor object,
so a single type serving it could not enforce either predecessor gate. It has
its own type, and that is what the state-machine correction added.

:class:`~.chain.BenchmarkConflictRecordPayload` is bound to **nothing**. It
records a refused attempt outside the linear chain and appends no successor, so
it represents no transition — and a lookup for it returns nothing rather than
guessing.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

from ._validation import require_enum_member
from .chain import (
    BenchmarkAdmissionDecisionPayload,
    BenchmarkConflictRecordPayload,
    BenchmarkPostAdmissionRejectionEventPayload,
    BenchmarkRegistrationEventPayload,
    BenchmarkRevocationEventPayload,
    BenchmarkSubmissionRecordPayload,
)
from .enums import BenchmarkAdmissionOutcome, BenchmarkRegistrationState
from .errors import BenchmarkRegistryLifecycleError
from .lifecycle import BENCHMARK_REGISTRATION_TRANSITIONS
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "BENCHMARK_TRANSITION_PAYLOAD_BINDING",
    "BENCHMARK_UNBOUND_PAYLOAD_TYPES",
    "bound_payload_for_transition",
    "require_bound_payload_for_transition",
]

_S = BenchmarkRegistrationState
_O = BenchmarkAdmissionOutcome

#: ``(predecessor_state | None, successor_state)`` → ``(payload class, required
#: declared_outcome | None)``.
#:
#: The ``None`` predecessor is the initial ``— → SUBMITTED`` transition, which
#: has no predecessor state at all — the only entry for which that is true, and
#: the only payload whose ``prev_event_digest`` is ``None``.
BENCHMARK_TRANSITION_PAYLOAD_BINDING: MappingProxyType = MappingProxyType(
    {
        (None, _S.SUBMITTED): (BenchmarkSubmissionRecordPayload, None),
        (_S.SUBMITTED, _S.ADMITTED): (
            BenchmarkAdmissionDecisionPayload,
            _O.ADMITTED,
        ),
        (_S.SUBMITTED, _S.REJECTED): (
            BenchmarkAdmissionDecisionPayload,
            _O.REJECTED,
        ),
        (_S.ADMITTED, _S.REJECTED): (
            BenchmarkPostAdmissionRejectionEventPayload,
            None,
        ),
        (_S.ADMITTED, _S.REGISTERED): (BenchmarkRegistrationEventPayload, None),
        (_S.REGISTERED, _S.REVOKED): (BenchmarkRevocationEventPayload, None),
    }
)

#: Payload types deliberately bound to no transition. Published so "this type
#: represents no lifecycle move" is machine-readable rather than an omission a
#: reader has to notice.
BENCHMARK_UNBOUND_PAYLOAD_TYPES: tuple = (BenchmarkConflictRecordPayload,)

# Every non-initial binding key must name a transition the closed relation
# actually admits, and the relation must have no arrow the binding cannot
# represent. Asserted at import, in both directions, so the two can never drift.
for _key in BENCHMARK_TRANSITION_PAYLOAD_BINDING:
    _from, _to = _key
    if _from is None:
        continue
    if _to not in BENCHMARK_REGISTRATION_TRANSITIONS[_from]:
        raise BenchmarkRegistryLifecycleError(  # pragma: no cover
            f"the binding names {_from.value} -> {_to.value}, which the closed "
            "transition relation does not admit"
        )
for _from, _successors in BENCHMARK_REGISTRATION_TRANSITIONS.items():
    for _to in _successors:
        if (_from, _to) not in BENCHMARK_TRANSITION_PAYLOAD_BINDING:
            raise BenchmarkRegistryLifecycleError(  # pragma: no cover
                f"the closed relation admits {_from.value} -> {_to.value} but "
                "no structural representation is bound to it; every admissible "
                "arrow has exactly one payload shape"
            )
del _key, _from, _to, _successors


def bound_payload_for_transition(
    from_state: Optional[BenchmarkRegistrationState],
    to_state: BenchmarkRegistrationState,
):
    """Return ``(payload class, required declared_outcome | None)``, or ``None``.

    ``None`` for ``from_state`` means the initial transition into ``SUBMITTED``.
    Returns :data:`None` for a pair the binding does not name — an unbound
    transition has no representation, and inventing one would be exactly the
    "alternate binding contract" §14 prohibits.
    """

    if from_state is not None:
        require_enum_member(from_state, BenchmarkRegistrationState, "from_state")
    require_enum_member(to_state, BenchmarkRegistrationState, "to_state")
    return BENCHMARK_TRANSITION_PAYLOAD_BINDING.get((from_state, to_state))


def require_bound_payload_for_transition(
    from_state: Optional[BenchmarkRegistrationState],
    to_state: BenchmarkRegistrationState,
    payload: object,
) -> None:
    """Raise unless ``payload`` is exactly the representation bound to the transition.

    Three independent gates, in order:

    1. the transition must be bound at all;
    2. ``type(payload)`` must **be** the bound class — exact identity, so a
       subclass and a same-named foreign class are both refused;
    3. where the binding names a required ``declared_outcome``, the payload's
       must match it.

    Pure validation. It moves nothing, appends nothing and records nothing; a
    payload passing all three gates has been shown to be the right *shape* for a
    transition, which is not the same as the transition having occurred.
    """

    binding = bound_payload_for_transition(from_state, to_state)
    origin = "initial" if from_state is None else from_state.value
    if binding is None:
        error = BenchmarkRegistryLifecycleError(
            f"{origin} -> {to_state.value} has no bound structural "
            "representation; no payload type may serve a transition it is not "
            "bound to"
        )
        error.reason = BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
        raise error
    expected_cls, required_outcome = binding
    if type(payload) is not expected_cls:
        error = BenchmarkRegistryLifecycleError(
            f"{origin} -> {to_state.value} is represented by exactly "
            f"{expected_cls.__name__} (got {type(payload).__name__}); no "
            "transition accepts a second payload type, and a subclass or "
            "same-named lookalike is not the bound type"
        )
        error.reason = BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
        raise error
    if required_outcome is not None:
        actual = getattr(payload, "declared_outcome", None)
        if actual is not required_outcome:
            error = BenchmarkRegistryLifecycleError(
                f"{origin} -> {to_state.value} requires declared_outcome="
                f"{required_outcome.value}; this payload carries "
                f"{getattr(actual, 'value', actual)!r}"
            )
            error.reason = (
                BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
            )
            raise error
