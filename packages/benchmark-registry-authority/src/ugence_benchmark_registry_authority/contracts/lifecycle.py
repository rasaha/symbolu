"""The closed BR-2 registration transition relation.

Five states, five arrows, and nothing else::

    SUBMITTED ──▶ ADMITTED ──▶ REGISTERED ──▶ REVOKED   (terminal)
        │             │
        ▼             ▼
     REJECTED      REJECTED   ← permitted ONLY while no registration
     (terminal)    (terminal)    record has been appended

**No reverse transition exists. No self-transition is admissible.** A reversible
state would be a denial an unsigned assertion could lift, which defeats
verify-before-deny; a self-transition would be an event that changed nothing
while still appending to an append-only log.

Terminal states are expressed as an **empty admissible set rather than a missing
key**, so a lookup never raises — BR-1's pattern, reproduced rather than
re-derived. ``BENCHMARK_REGISTRATION_TRANSITIONS[REVOKED]`` is
``frozenset()``, not a :class:`KeyError`, because "nothing may follow this" is an
answer and "I have no idea" is not.

The ``ADMITTED → REJECTED`` precondition
-----------------------------------------
That arrow is permitted **only while no registration record has been appended**.
The relation cannot express that condition, because it is a fact about the
*log*, not about the state pair — and BR-2A holds no log. The relation therefore
admits the arrow, and the condition is enforced elsewhere. BR-2B's
:class:`~.kernel.BenchmarkTransitionPlan` enforces it against the **asserted**
:class:`~.enums.BenchmarkRegistrationRecordPresence` a caller supplies, because
BR-2B holds no log either; BR-2D, which does hold one, enforces it against the
observed log. What BR-2A makes structural instead is that
:class:`~.chain.BenchmarkPostAdmissionRejectionEventPayload` requires its nested
predecessor's ``declared_outcome`` to be exactly ``ADMITTED``.

This relation is not authority
------------------------------
Membership here says a move is *representable*, never that it *happened* or that
a caller may cause it. Nothing in BR-2A can perform a transition: there is no
engine, no log and no store. :func:`require_valid_registration_transition` is
pure validation over a frozen mapping.
"""

from __future__ import annotations

from types import MappingProxyType

from ._validation import require_enum_member
from .enums import (
    BENCHMARK_TERMINAL_REGISTRATION_STATES,
    BenchmarkRegistrationState,
)
from .errors import BenchmarkRegistryLifecycleError
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "BENCHMARK_REGISTRATION_TRANSITIONS",
    "is_valid_registration_transition",
    "require_valid_registration_transition",
]

_S = BenchmarkRegistrationState

#: The closed transition relation: **every** state is a key, and a terminal
#: state maps to an empty :class:`frozenset` rather than being absent.
BENCHMARK_REGISTRATION_TRANSITIONS: MappingProxyType = MappingProxyType(
    {
        _S.SUBMITTED: frozenset({_S.ADMITTED, _S.REJECTED}),
        _S.ADMITTED: frozenset({_S.REGISTERED, _S.REJECTED}),
        _S.REGISTERED: frozenset({_S.REVOKED}),
        _S.REVOKED: frozenset(),
        _S.REJECTED: frozenset(),
    }
)

# Structural invariants, asserted at import so they cannot regress silently.
if set(BENCHMARK_REGISTRATION_TRANSITIONS) != set(BenchmarkRegistrationState):
    raise BenchmarkRegistryLifecycleError(  # pragma: no cover
        "every registration state must be a key in the transition relation; a "
        "missing key would make a lookup raise where an empty set is the answer"
    )
for _state, _successors in BENCHMARK_REGISTRATION_TRANSITIONS.items():
    if _state in _successors:
        raise BenchmarkRegistryLifecycleError(  # pragma: no cover
            f"{_state.value} admits itself as a successor; no self-transition "
            "is admissible, because an event that changes nothing must not be "
            "appendable to an append-only log"
        )
    if _state in BENCHMARK_TERMINAL_REGISTRATION_STATES and _successors:
        raise BenchmarkRegistryLifecycleError(  # pragma: no cover
            f"{_state.value} is terminal but admits successors"
        )
del _state, _successors


def is_valid_registration_transition(
    from_state: BenchmarkRegistrationState,
    to_state: BenchmarkRegistrationState,
) -> bool:
    """Return whether ``from_state → to_state`` is in the closed relation.

    Pure and total over the vocabulary: both arguments must be exact
    :class:`~.enums.BenchmarkRegistrationState` members — a bare string that
    spells one is refused, because a ``str``-valued enum compares equal to its
    own value and a closed vocabulary that accepts strings is not closed.

    Returning :data:`True` says the move is representable. It does not say it
    happened, that a caller may cause it, or that any prerequisite was met.
    """

    require_enum_member(from_state, BenchmarkRegistrationState, "from_state")
    require_enum_member(to_state, BenchmarkRegistrationState, "to_state")
    return to_state in BENCHMARK_REGISTRATION_TRANSITIONS[from_state]


def require_valid_registration_transition(
    from_state: BenchmarkRegistrationState,
    to_state: BenchmarkRegistrationState,
) -> None:
    """Raise unless ``from_state → to_state`` is in the closed relation.

    Raises :class:`~.errors.BenchmarkRegistryLifecycleError` carrying
    :attr:`~.reasons.BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION`.
    A terminal predecessor produces the same refusal as any other unadmitted
    move: there is no separate "already finished" success path, because a
    terminal state admitting a successor is exactly the reversibility D-08
    forbids.
    """

    if not is_valid_registration_transition(from_state, to_state):
        error = BenchmarkRegistryLifecycleError(
            f"{from_state.value} -> {to_state.value} is not an admissible BR-2 "
            "registration transition; the relation is closed, has no reverse "
            "arrow and no self-transition, and a terminal state admits nothing"
        )
        error.reason = BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
        raise error
