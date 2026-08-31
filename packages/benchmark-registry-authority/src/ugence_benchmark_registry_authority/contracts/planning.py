"""BR-2B's pure planning functions. **Total, and incapable of causing anything.**

Every function here has the same shape: exact contracts in, a
:class:`~.kernel.BenchmarkTransitionPlan` or a
:class:`~.kernel.BenchmarkTransitionRefusal` out. There is no third outcome, no
success channel that is not one of those two types, and no argument that is a
raw digest or a raw byte string.

Why the signatures take contracts and never digests or bytes
-------------------------------------------------------------
A caller who can pass a digest can pass *any* digest, and a function that
compares two caller-supplied digests has verified that the caller can type. So
these functions accept the exact payload objects and **recompute canonical bytes
themselves** through the one encoder. D-06 requires idempotence to compare
canonical **bytes**, not digests alone; :func:`is_byte_identical_resubmission`
does exactly that, and it derives both sides rather than accepting either.

Total functions, not raising ones
----------------------------------
:class:`~.kernel.BenchmarkTransitionPlan` refuses to *exist* for an inadmissible
move — that is the constructor's job and it raises. These functions are the
total layer over it: they catch that refusal and return a typed
:class:`~.kernel.BenchmarkTransitionRefusal` carrying the same reason, so a
caller branches on a returned type rather than on an exception. Nothing is
softened; the plan is still unconstructible, and the refusal is still a refusal.

Everything is asserted, nothing is authoritative
-------------------------------------------------
Every value reaching these functions is a caller's claim. The snapshot is
asserted; the "occupant" record is a record the caller says occupies the slot;
the record presence is asserted. BR-2B observes nothing, so a plan computed here
is worth exactly what the assertion behind it was worth. The five permanently-
``False`` authority derivations ride on every returned object and say so.

Fail closed, always
--------------------
An assertion that describes no reachable registry state — an unoccupied locator
handed an occupant, an occupied one handed none, an occupant sitting at a
different locator than the snapshot names — is **refused**, never repaired and
never guessed past. Those are ``STALE_REGISTRY_SNAPSHOT``: the caller's picture
of the registry is inconsistent with itself, and inventing the missing half
would be manufacturing state.

What is deliberately absent
----------------------------
No verifier, no clock, no store, no append, no mutation of anything, and no
authority-issued result. **No function accepts a plan.** A plan is an output of
this module and an input to nothing in it — there is no ``apply``, ``commit``,
``append``, ``admit``, ``register``, ``revoke`` or ``resolve``, and
``tests/packaging/test_milestone_boundary.py`` asserts that no exported callable
takes a :class:`~.kernel.BenchmarkTransitionPlan` as a parameter at all. That is
what keeps "BR-2B may determine what transition would be valid" from drifting
into "BR-2B performs it".

Confusable coordinates stay rejection-only
--------------------------------------------
BR-2B computes **no** confusability. D-06 forbids claiming a complete Unicode
algorithm until one is specified, versioned and tested, and none is ratified, so
none is written here: :data:`~.confusable.BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT`
still reports no algorithm identifier and no Unicode version.

What :func:`plan_submission_outcome` does is narrower and honest. When a caller
routes two records together as an occupancy collision and their exact locators
are **not equal**, the only ratified outcome is rejection — ``CONFUSABLE_COORDINATE``
— and neither locator is casefolded, NFKC-normalized, rewritten or stored. The
comparison performed is exact equality; the refusal is the whole response.
"""

from __future__ import annotations

from typing import Optional, Union

from ._validation import require_enum_member, require_exact_type
from .canonical import canonical_bytes
from .chain import BenchmarkSubmissionRecordPayload
from .enums import BenchmarkRegistrationState
from .errors import BenchmarkRegistryLifecycleError
from .kernel import (
    BenchmarkRegistrySnapshotAssertion,
    BenchmarkTransitionPlan,
    BenchmarkTransitionRefusal,
)
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "BenchmarkPlanningOutcome",
    "is_byte_identical_resubmission",
    "plan_transition",
    "plan_submission_outcome",
]

#: What every function in this module returns: a plan or a refusal, never a
#: payload, a record, a Boolean or ``None``. Published so the closed outcome set
#: is readable off the module rather than inferred from the signatures.
BenchmarkPlanningOutcome = Union[
    BenchmarkTransitionPlan, BenchmarkTransitionRefusal
]

_S = BenchmarkRegistrationState
_R = BenchmarkRegistryRefusalReason


def _refuse(
    snapshot: BenchmarkRegistrySnapshotAssertion,
    to_state: BenchmarkRegistrationState,
    reason: BenchmarkRegistryRefusalReason,
) -> BenchmarkTransitionRefusal:
    """One construction site for every refusal this module returns."""

    return BenchmarkTransitionRefusal(
        snapshot=snapshot,
        refused_to_state=to_state,
        declared_refusal_reason=reason,
    )


def plan_transition(
    snapshot: BenchmarkRegistrySnapshotAssertion,
    to_state: BenchmarkRegistrationState,
) -> BenchmarkPlanningOutcome:
    """Plan one registration transition against an **asserted** snapshot.

    Returns a :class:`~.kernel.BenchmarkTransitionPlan` when the closed relation
    admits ``asserted_current_state → to_state`` and the
    ``ADMITTED → REJECTED`` record-presence precondition holds, and a
    :class:`~.kernel.BenchmarkTransitionRefusal` otherwise. Total over the
    vocabulary: every ordered pair of states produces one or the other, and
    neither branch appends, admits, registers, revokes or resolves anything.

    Both arguments must be the exact types. A bare string that spells a state is
    refused rather than coerced — a ``str``-valued enum compares equal to its own
    value, and a closed vocabulary that accepts strings is not closed.
    """

    require_exact_type(
        snapshot, BenchmarkRegistrySnapshotAssertion, "snapshot"
    )
    require_enum_member(to_state, BenchmarkRegistrationState, "to_state")
    try:
        return BenchmarkTransitionPlan(
            snapshot=snapshot, planned_to_state=to_state
        )
    except BenchmarkRegistryLifecycleError as refused:
        return _refuse(
            snapshot,
            to_state,
            getattr(refused, "reason", _R.UNAUTHORIZED_TRANSITION),
        )


def is_byte_identical_resubmission(
    proposed_record: BenchmarkSubmissionRecordPayload,
    occupant_record: BenchmarkSubmissionRecordPayload,
) -> bool:
    """Whether two submission records canonicalize to **identical bytes**.

    D-06 requires idempotence to compare canonical bytes rather than digests
    alone, so this recomputes both sides through the one encoder and compares
    the byte sequences. Neither side may be supplied as bytes or as a digest:
    the arguments are the exact payload objects, and a caller who wanted to
    claim two records match has to hand over both records.

    Returning :data:`True` reports that nothing new would be registered. It is
    not a success: :attr:`~.reasons.BenchmarkRegistryRefusalReason.IDEMPOTENT_DUPLICATE`
    is a member of the refusal vocabulary precisely because a consumer that
    receives it has obtained no registration.
    """

    require_exact_type(
        proposed_record,
        BenchmarkSubmissionRecordPayload,
        "proposed_record",
    )
    require_exact_type(
        occupant_record,
        BenchmarkSubmissionRecordPayload,
        "occupant_record",
    )
    return canonical_bytes(proposed_record) == canonical_bytes(occupant_record)


def plan_submission_outcome(
    snapshot: BenchmarkRegistrySnapshotAssertion,
    proposed_record: BenchmarkSubmissionRecordPayload,
    occupant_record: Optional[BenchmarkSubmissionRecordPayload] = None,
) -> BenchmarkPlanningOutcome:
    """Plan a submission against an asserted slot, including conflict outcomes.

    The whole of D-05 and D-06's calculation, and none of their consequences:

    * **Unoccupied** and no occupant supplied → the initial ``— → SUBMITTED``
      plan.
    * **Occupied**, byte-identical resubmission → ``IDEMPOTENT_DUPLICATE``.
    * **Occupied**, same exact locator, different bytes →
      ``COORDINATE_SLOT_CONFLICT``. Last-writer-wins is not an outcome here,
      because it is not an outcome anywhere.
    * **Occupied**, different locator, same declared identity digest →
      ``DIGEST_ALREADY_BOUND``. The same content addressed two ways.
    * **Occupied**, different locator, different digest → ``CONFUSABLE_COORDINATE``,
      rejection-only. Nothing is normalized, rewritten or stored.

    Anything self-inconsistent fails closed with ``STALE_REGISTRY_SNAPSHOT``:
    an unoccupied locator handed an occupant, an occupied one handed none, or an
    occupant recorded at a locator the snapshot does not name. The caller's
    picture disagrees with itself, and choosing which half to believe would be
    manufacturing registry state.
    """

    require_exact_type(
        snapshot, BenchmarkRegistrySnapshotAssertion, "snapshot"
    )
    require_exact_type(
        proposed_record,
        BenchmarkSubmissionRecordPayload,
        "proposed_record",
    )
    if occupant_record is not None:
        require_exact_type(
            occupant_record,
            BenchmarkSubmissionRecordPayload,
            "occupant_record",
        )

    if snapshot.asserts_unoccupied_locator:
        if occupant_record is not None:
            return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)
        return plan_transition(snapshot, _S.SUBMITTED)

    if occupant_record is None:
        return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)

    occupant_envelope = occupant_record.publisher_submission_envelope
    proposed_envelope = proposed_record.publisher_submission_envelope

    # The occupant must sit at the locator the snapshot is about, or the two
    # halves of the caller's claim are not about the same slot.
    if occupant_envelope.coordinate != snapshot.coordinate:
        return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)

    if proposed_envelope.coordinate != occupant_envelope.coordinate:
        # Routed together as a collision, but the exact locators are not equal.
        # Rejection-only in both branches: neither locator is rewritten.
        if (
            proposed_envelope.benchmark_identity_digest
            == occupant_envelope.benchmark_identity_digest
        ):
            return _refuse(snapshot, _S.SUBMITTED, _R.DIGEST_ALREADY_BOUND)
        return _refuse(snapshot, _S.SUBMITTED, _R.CONFUSABLE_COORDINATE)

    if is_byte_identical_resubmission(proposed_record, occupant_record):
        return _refuse(snapshot, _S.SUBMITTED, _R.IDEMPOTENT_DUPLICATE)
    return _refuse(snapshot, _S.SUBMITTED, _R.COORDINATE_SLOT_CONFLICT)
