"""The ratified benchmark lifecycle transition relation (ADR §29).

ADR §29 draws the benchmark lifecycle as a fixed progression with one terminal
exit. This module encodes exactly those arrows as a **closed relation** —
nothing else is admissible, and a transition outside it is a fail-closed refusal
with a stable typed reason (B-7 — "no partial state, no silent fallback"), never
a warning and never a silent apply.

The arrows, and where each comes from
-------------------------------------
==============================  ==============================================
Arrow                           ADR §29 source
==============================  ==============================================
``AUTHORED -> APPROVED``        "author benchmark content" -> "approve the
                                EXACT digest (external governance)"
``APPROVED -> REGISTERED``      "verify approval" / "verify publisher
                                signature" -> "register exact version
                                (append-only)"
``REGISTERED -> REVOKED``       "revoke version (signed, entitled, verified
                                before denial)"
==============================  ==============================================

Three arrows, four states, one terminal state. The relation is a chain because
§29's diagram is one: there is no branch, no rework loop, and no state a
benchmark version can return to. That is not a simplification of a richer model
— it is the model §29 draws, and B-10's append-only rule is why: a version that
needed to move backwards would be a *new version*, with its own coordinate, its
own content digest and its own identity.

What this relation is **not**
-----------------------------
It is **not** the ADR §16.2 six-stage registration ordering. Those six stages —
structural validation, canonical digest verification, external approval
verification, publisher/signature verification, lifecycle/effectivity validation,
exact append-only registration — are the ordered *checks a registry performs*,
and ADR §30 assigns them to **BR-2** ("admission ordering (§16.2)"). BR-1
implements none of them and mints no vocabulary for them. Confusing the two would
put a registry's admission sequence inside a contract package.

It is also not a CRUD lifecycle. There is no create/update/delete, no draft-edit
cycle and no reinstatement: B-10 makes registration append-only and §17.12 makes
supersession structured-successor-only.

No self-transition
------------------
``REGISTERED -> REGISTERED`` is not a transition and is refused, so "no change"
can never be recorded as lifecycle movement — which matters because B-10's
byte-identical idempotence (BR-2) is about *re-registering identical bytes*, not
about a state moving to itself.

No clock
--------
Nothing here reads a clock, and no arrow fires with the passage of time. Expiry
is deliberately not a state (see :class:`~.enums.BenchmarkLifecycleState`); it is
a question asked of the declared effective period at a caller-supplied instant.
"""

from __future__ import annotations

from types import MappingProxyType

from .enums import BenchmarkLifecycleState
from .errors import BenchmarkLifecycleError

__all__ = [
    "BENCHMARK_LIFECYCLE_TRANSITIONS",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
]

_S = BenchmarkLifecycleState

#: The closed transition relation of ADR §29: current state -> admissible next
#: states, as an immutable mapping of immutable frozensets.
#:
#: Exposed as a read-only :class:`~types.MappingProxyType` over frozensets so a
#: caller cannot widen the relation after import — a mutable relation would let
#: any consumer authorize a transition the ADR does not ratify.
#:
#: Every state is a key, including the terminal one, so a lookup never raises
#: ``KeyError`` and "terminal" is expressed as an empty admissible set rather
#: than as a missing entry.
BENCHMARK_LIFECYCLE_TRANSITIONS = MappingProxyType(
    {
        _S.AUTHORED: frozenset({_S.APPROVED}),
        _S.APPROVED: frozenset({_S.REGISTERED}),
        _S.REGISTERED: frozenset({_S.REVOKED}),
        _S.REVOKED: frozenset(),
    }
)


def _require_state(value: object, name: str) -> BenchmarkLifecycleState:
    if type(value) is not BenchmarkLifecycleState:
        raise BenchmarkLifecycleError(
            f"{name} must be exactly a BenchmarkLifecycleState "
            f"(got {type(value).__name__}); a lookalike carrying a matching "
            "value is refused because the relation is closed over this type"
        )
    return value


def is_valid_lifecycle_transition(
    current: BenchmarkLifecycleState, proposed: BenchmarkLifecycleState
) -> bool:
    """Return whether ``current -> proposed`` is a ratified ADR §29 arrow.

    A pure predicate over the closed relation. It reads no clock and consults no
    external state, and it establishes **nothing** about trust: a valid
    transition is still only a statement an artifact makes about itself (B-5).
    """

    _require_state(current, "current")
    _require_state(proposed, "proposed")
    return proposed in BENCHMARK_LIFECYCLE_TRANSITIONS[current]


def require_valid_lifecycle_transition(
    current: BenchmarkLifecycleState, proposed: BenchmarkLifecycleState
) -> None:
    """Raise :class:`BenchmarkLifecycleError` unless the arrow is ratified.

    The raised error carries
    ``reason == BENCHMARK_INVALID_LIFECYCLE_TRANSITION``, so a caller that
    refuses on it reports the same stable typed code an admission-time refusal
    would (§16.3).
    """

    if not is_valid_lifecycle_transition(current, proposed):
        admissible = sorted(
            state.value for state in BENCHMARK_LIFECYCLE_TRANSITIONS[current]
        )
        detail = ", ".join(admissible) if admissible else "none — terminal state"
        raise BenchmarkLifecycleError(
            f"{current.value} -> {proposed.value} is not a ratified benchmark "
            f"lifecycle transition (ADR §29); admissible next states from "
            f"{current.value}: {detail}"
        )
