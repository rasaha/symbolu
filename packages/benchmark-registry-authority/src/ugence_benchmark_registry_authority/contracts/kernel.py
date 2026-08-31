"""BR-2B's non-authoritative lifecycle-kernel contracts. **Nothing here occurs.**

D-01 as amended 2026-08-20 fixes the boundary this module sits on: *BR-2B may
determine what transition would be valid; BR-2D is the first phase permitted to
assert that a transition occurred.* Three contracts carry that distinction in
the type system rather than in prose.

* :class:`BenchmarkRegistrySnapshotAssertion` — what a caller **asserts** the
  current registry state to be. BR-2B holds no store, so it never observes
  state; it reasons only about state it is told about, and the type is named so
  that nobody can mistake the telling for an observation.
* :class:`BenchmarkTransitionPlan` — a move that **would be** admissible against
  exactly that assertion. Constructing one for an inadmissible move is
  impossible, not merely refused.
* :class:`BenchmarkTransitionRefusal` — a move that would not be, with one
  stable typed code from the BR-2 vocabulary saying why.

Why the plan nests the assertion instead of its digest
-------------------------------------------------------
A plan that carried only a verdict would be the Boolean problem in a larger
costume: a caller could obtain a plan against one asserted state and apply it
against another, and nothing in the type would notice. The plan therefore
**nests the exact assertion object it was computed from**, and derives
:attr:`~BenchmarkTransitionPlan.snapshot_digest` from it by recomputation. A
consumer that intends to act on a plan can compare that digest against the state
it actually holds; a consumer that does not compare has not been given an excuse
by the contract.

No clock, no store, no verifier
--------------------------------
D-11 as amended: **BR-2A and BR-2B read no clock; the authoritative clock
arrives at BR-2D.** So no contract in this module carries
``declared_recorded_at``, and none may acquire one. A registry event is stamped
by the authority that recorded it, and there is no such authority here — a plan
is a statement about a move that has not happened, and stamping it with a time
would be the first half of pretending it had.

Likewise there is no store to read, no verifier to consult and no log to append
to. The one fact the closed transition relation cannot express — that
``ADMITTED → REJECTED`` is permitted only while no registration record has been
appended — is supplied by the caller as
:class:`~.enums.BenchmarkRegistrationRecordPresence` on the assertion, and the
plan's constructor enforces it. BR-2A left that gate to "BR-2B's append path";
under the amended subdivision BR-2B has no append path either, so the gate is
enforced against the **asserted** presence and the append itself is BR-2D's.

What a plan is still not
-------------------------
Every contract here carries §09's five permanently-``False`` authority
derivations, exactly as every BR-2A payload does. A plan is caller-constructible,
so a plan is worth precisely what the assertion behind it is worth, which is
nothing until an authority that can observe state says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ugence_benchmark_registry import BenchmarkCoordinate

from ._authority import permanently_unverified_authority
from ._validation import require_enum_member, require_exact_type
from .binding import bound_payload_for_transition
from .canonical import (
    BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN,
    _register_contract_type,
    canonical_digest,
)
from .enums import (
    BenchmarkRegistrationRecordPresence,
    BenchmarkRegistrationState,
)
from .errors import BenchmarkRegistryLifecycleError
from .lifecycle import is_valid_registration_transition
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "BenchmarkRegistrySnapshotAssertion",
    "BenchmarkTransitionPlan",
    "BenchmarkTransitionRefusal",
]

_S = BenchmarkRegistrationState
_P = BenchmarkRegistrationRecordPresence


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkRegistrySnapshotAssertion:
    """What a caller **asserts** the registry currently holds for one locator.

    Not a reading. BR-2B has no store to read, and this type exists so that the
    absence is visible in every signature that consumes it rather than buried in
    a docstring. Every field is ``asserted_`` for the same reason: a reviewer
    scanning a call site sees claims, not observations.

    ``asserted_current_state`` is :data:`None` when the caller asserts the exact
    locator is **unoccupied** — the only state from which the initial
    ``— → SUBMITTED`` move is admissible. When it is :data:`None`, the caller
    must also assert no registration record, because a locator that holds
    nothing cannot carry one; the constructor refuses that inconsistency rather
    than silently preferring one field.

    **No asserted event digest.** An earlier draft carried the digest of the
    last appended event so a plan could state what to chain from. The chain-
    integrity gate refused it, and correctly: a digest of something inside this
    package's own graph is never a field, always a derived property recomputed
    from a nested object. The chaining requirement needs no assertion anyway —
    the payload type bound to the transition already enforces it structurally
    through its own recomputed ``prev_event_digest``. Asserting it here would
    have reintroduced exactly the caller-supplied-digest hole BR-2A closed.
    """

    #: The exact BR-1 locator this assertion is about. One coordinate; the
    #: version lives inside it and is not re-spelled here.
    coordinate: BenchmarkCoordinate

    #: The registration state the caller asserts the locator currently holds,
    #: or :data:`None` for an unoccupied locator.
    asserted_current_state: Optional[BenchmarkRegistrationState]

    #: Whether a registration record has been appended, as the caller asserts
    #: it. A closed enum rather than a Boolean: D-15 retires flippable Boolean
    #: capability fields, and this one gates the ``ADMITTED → REJECTED`` arrow.
    asserted_registration_record_presence: BenchmarkRegistrationRecordPresence

    def __post_init__(self) -> None:
        require_exact_type(self.coordinate, BenchmarkCoordinate, "coordinate")
        require_enum_member(
            self.asserted_registration_record_presence,
            BenchmarkRegistrationRecordPresence,
            "asserted_registration_record_presence",
        )
        if self.asserted_current_state is not None:
            require_enum_member(
                self.asserted_current_state,
                BenchmarkRegistrationState,
                "asserted_current_state",
            )
            return

        # Unoccupied: the record assertion must agree, or the assertion
        # describes no reachable registry state at all.
        if self.asserted_registration_record_presence is not _P.NO_RECORD_APPENDED:
            error = BenchmarkRegistryLifecycleError(
                "asserted_current_state is None, so the locator is asserted "
                "unoccupied, but a registration record is asserted present; an "
                "unoccupied locator carries no record"
            )
            error.reason = BenchmarkRegistryRefusalReason.STALE_REGISTRY_SNAPSHOT
            raise error

    @property
    def asserts_unoccupied_locator(self) -> bool:
        """Whether the caller asserts this exact locator holds nothing.

        Derived from :attr:`asserted_current_state`, never stored: a second
        spelling of "unoccupied" is a second thing that can disagree.
        """

        return self.asserted_current_state is None


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkTransitionPlan:
    """A move that **would be** admissible against exactly the nested assertion.

    Unconstructible for an inadmissible move. The constructor consults the
    closed relation in :mod:`.lifecycle` and the ``ADMITTED → REJECTED``
    precondition, and raises rather than producing a plan a consumer would have
    to re-check. There is no "invalid plan" object, because a plan that might be
    invalid is a refusal wearing the wrong type.

    It says nothing happened. It says nothing *will* happen. It says that if the
    registry really is in the asserted state, this one move is the move the
    closed relation admits, and this is the payload shape bound to it.
    """

    #: The exact assertion this plan was computed from. Nested, not digested:
    #: the plan is bound to the whole claim, and the digest is recomputed.
    snapshot: BenchmarkRegistrySnapshotAssertion

    #: The successor state the plan is for.
    planned_to_state: BenchmarkRegistrationState

    def __post_init__(self) -> None:
        require_exact_type(
            self.snapshot, BenchmarkRegistrySnapshotAssertion, "snapshot"
        )
        require_enum_member(
            self.planned_to_state,
            BenchmarkRegistrationState,
            "planned_to_state",
        )
        predecessor = self.snapshot.asserted_current_state

        if predecessor is None:
            if self.planned_to_state is not _S.SUBMITTED:
                error = BenchmarkRegistryLifecycleError(
                    "an unoccupied locator admits only the initial "
                    f"— -> SUBMITTED move, not — -> "
                    f"{self.planned_to_state.value}"
                )
                error.reason = (
                    BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
                )
                raise error
            return

        if not is_valid_registration_transition(
            predecessor, self.planned_to_state
        ):
            error = BenchmarkRegistryLifecycleError(
                f"{predecessor.value} -> {self.planned_to_state.value} "
                "is not an admissible BR-2 registration transition, so no plan "
                "represents it; the relation is closed, has no reverse arrow "
                "and no self-transition, and a terminal state admits nothing"
            )
            error.reason = BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION
            raise error

        # The one gate the closed relation cannot express (see the module
        # docstring): ADMITTED -> REJECTED only while nothing is registered.
        if (
            predecessor is _S.ADMITTED
            and self.planned_to_state is _S.REJECTED
            and self.snapshot.asserted_registration_record_presence
            is not _P.NO_RECORD_APPENDED
        ):
            error = BenchmarkRegistryLifecycleError(
                "ADMITTED -> REJECTED is permitted only while no registration "
                "record has been appended, and the assertion says one has; the "
                "closed relation cannot express this condition because it is a "
                "fact about the log, not about the state pair"
            )
            error.reason = BenchmarkRegistryRefusalReason.LIFECYCLE_CONFLICT
            raise error

    @property
    def planned_predecessor_state(self) -> Optional[BenchmarkRegistrationState]:
        """Derived through the nested assertion. No second spelling."""

        return self.snapshot.asserted_current_state

    @property
    def planned_payload_type_name(self) -> str:
        """The name of the one payload shape bound to this transition.

        The **name**, not the class: a class object is not a canonicalizable
        value, and a plan that carried one would be carrying something the
        encoder cannot render into bytes.
        """

        bound = bound_payload_for_transition(
            self.planned_predecessor_state, self.planned_to_state
        )
        return bound[0].__name__

    @property
    def snapshot_digest(self) -> str:
        """Independently recomputed digest of the nested assertion.

        This is what binds the plan to the exact state it was computed against.
        A consumer applying a plan compares this against the state it actually
        holds; a consumer that skips the comparison is not doing so because the
        contract left it ambiguous.
        """

        return canonical_digest(self.snapshot)

    @property
    def is_terminal(self) -> bool:
        """Whether the planned successor state admits nothing after it."""

        return self.planned_to_state in (_S.REVOKED, _S.REJECTED)


@permanently_unverified_authority
@dataclass(frozen=True)
class BenchmarkTransitionRefusal:
    """A move that would **not** be admissible, with one typed reason.

    Every member of :class:`~.reasons.BenchmarkRegistryRefusalReason` is a
    refusal, including ``IDEMPOTENT_DUPLICATE`` — a consumer holding one of
    these has not obtained a registration and has not obtained a plan.

    Like a plan, it nests the exact assertion it was computed from, so a refusal
    cannot be quoted against a state it was never computed for.
    """

    #: The exact assertion this refusal was computed from.
    snapshot: BenchmarkRegistrySnapshotAssertion

    #: The successor state that was refused.
    refused_to_state: BenchmarkRegistrationState

    #: One stable typed code from the BR-2 vocabulary saying what refused it.
    declared_refusal_reason: BenchmarkRegistryRefusalReason

    def __post_init__(self) -> None:
        require_exact_type(
            self.snapshot, BenchmarkRegistrySnapshotAssertion, "snapshot"
        )
        require_enum_member(
            self.refused_to_state,
            BenchmarkRegistrationState,
            "refused_to_state",
        )
        require_enum_member(
            self.declared_refusal_reason,
            BenchmarkRegistryRefusalReason,
            "declared_refusal_reason",
        )

    @property
    def refused_predecessor_state(self) -> Optional[BenchmarkRegistrationState]:
        """Derived through the nested assertion. No second spelling."""

        return self.snapshot.asserted_current_state

    @property
    def snapshot_digest(self) -> str:
        """Independently recomputed digest of the nested assertion."""

        return canonical_digest(self.snapshot)

    @property
    def is_terminal(self) -> bool:
        """Always ``True``. A refusal appends no successor and plans nothing."""

        return True


for _cls, _domain in (
    (
        BenchmarkRegistrySnapshotAssertion,
        BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    ),
    (BenchmarkTransitionPlan, BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN),
    (BenchmarkTransitionRefusal, BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN),
):
    _register_contract_type(_cls, _domain, root_canonicalizable=True)
del _cls, _domain
