"""R-12 — the carried instants must be coherent with each other (5B-2, Phase 5A).

Coherence is not freshness
---------------------------
Phase 5B's gate 13 reconciles each carried instant against the verifier's ``as_of``. It cannot
see a candidate that is internally impossible, because every instant can sit correctly relative
to ``as_of`` while contradicting the others — an attestation issued a decade before the
recommendation it attests, say. The builder holds all six, so this is where the relationship is
checkable, and it is checkable **without a clock**: these compare carried facts against each
other, never against now.

That distinction is what keeps Phase 5A's authority boundary intact. ``test_time_authority.py``
still proves no clock is consulted; its illustration moved to a candidate that is coherent and
ancient, because the one it used before was also internally impossible.

Only relationships the upstream contracts support
--------------------------------------------------
* ``valid_from <= asserted_at <= valid_until`` — Risk Authority's own seam contract enforces
  exactly this, inclusive, at ``evaluation_contracts.py:880``.
* ``evaluated_at <= expires_at`` — a **newly ratified candidate-coherence invariant**, not an
  upstream one. The decision's own contract does not bound its ttl; the ground is the sibling
  principle at ``controls.py:64``, which refuses a control result whose ``valid_until``
  precedes its ``evaluated_at`` as "a negative freshness window".
* ``asserted_at <= attestation_issued_at <= valid_until`` — ratified for R-12: a producer
  cannot attest a recommendation before it exists, and an attestation first issued after that
  recommendation expired must not make it usable again.

No total order is assumed, and one relationship is deliberately **absent**:
``decision_evaluated_at`` is not required to fall inside the subject window. The adapter checks
its trusted clock against that window and then asserts ``request.evaluation_time is None``
rather than forwarding it (``adapter.py:239-270``), so the decision's instant is stamped by a
different clock *by design*. Identity is disproven, not merely unproven.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from conftest import (
    build_attestation,
    build_decision,
    build_policy_binding,
    build_projection,
    build_target_scope,
    coordinate_for,
)
from ugence_cloud_scaling_authorization_contracts import (
    AuthorizationCandidateRejectionReason as Reason,
)
from ugence_cloud_scaling_authorization_contracts import (
    CanonicalFieldError,
    ReconciliationError,
    TemporalOrderingError,
    build_capacity_authorization_candidate,
)

MICROSECOND = timedelta(microseconds=1)


def _build(projection=None, decision=None, attestation=None):
    projection = projection if projection is not None else build_projection()
    decision = decision if decision is not None else build_decision(projection)
    attestation = attestation if attestation is not None else build_attestation(
        recommendation_digest=projection.recommendation_digest
    )
    scope = build_target_scope(projection)
    binding = build_policy_binding(scope)
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        target_scope=scope,
        policy_binding=binding,
        policy_coordinate_binding=coordinate_for(binding),
    )


def _forged_projection(projection, **overrides):
    """A projection carrying subject instants the seam would never have produced.

    Two upstream protections stand in front of the subject ordering, and both had to be
    bypassed to reach the builder's guard at all — which is itself the measurement:

    * Risk Authority's ``SubjectContext.__post_init__`` enforces
      ``valid_from <= asserted_at <= valid_until`` and raises ``SeamContractError``;
    * the projection carries a ``context_digest`` over its context, so ``dataclasses.replace``
      on the context is refused as a digest mismatch before construction is reached.

    So the builder's subject guard is **defence in depth**, not a check that catches realistic
    drift: a well-formed projection cannot violate it. It exists because the builder should not
    assume its inputs were produced by the seam, and this helper constructs precisely the input
    that assumption would let through.
    """

    context = object.__new__(type(projection.context))
    for field in dataclasses.fields(projection.context):
        object.__setattr__(context, field.name, getattr(projection.context, field.name))
    for name, value in overrides.items():
        object.__setattr__(context, name, value)

    forged = object.__new__(type(projection))
    for field in dataclasses.fields(projection):
        object.__setattr__(forged, field.name, getattr(projection, field.name))
    object.__setattr__(forged, "context", context)
    # Third protection: Phase 5A's own reconcile_phase4 re-derives the context digest and
    # refuses a mismatch. Recomputed here so the forgery reaches the builder's guard rather
    # than dying at the digest — which is what a forger with the canonicaliser would do.
    object.__setattr__(forged, "context_digest", context.digest())
    return forged


# ======================================================================================
# The genuine chain, and the equality boundaries
# ======================================================================================
def test_the_genuine_chain_is_coherent():
    candidate = _build()
    assert (
        candidate.subject_valid_from_fact
        <= candidate.subject_asserted_at_fact
        <= candidate.subject_valid_until_fact
    )
    assert candidate.decision_evaluated_at_fact <= candidate.decision_expires_at_fact
    assert (
        candidate.subject_asserted_at_fact
        <= candidate.attestation_issued_at_fact
        <= candidate.subject_valid_until_fact
    )


def test_the_fixture_chain_already_sits_on_two_of_the_boundaries():
    """Equality is valid, and the fixtures depend on it — worth stating, not assuming.

    ``valid_from == asserted_at`` because the projection sets both from
    ``recommendation_time``, and the fixture attestation is issued at that same instant. A
    strict comparison anywhere here would refuse the genuine chain.
    """

    candidate = _build()
    assert candidate.subject_valid_from_fact == candidate.subject_asserted_at_fact
    assert candidate.attestation_issued_at_fact == candidate.subject_asserted_at_fact


def test_the_subject_ordering_guard_is_unreachable_and_that_is_the_finding():
    """**Ruling 1's guard cannot fire, and this pins why rather than hiding it.**

    Four independent protections stand in front of it, and a seam-violating subject context
    dies at each in turn:

    1. ``SubjectContext.__post_init__`` enforces ``valid_from <= asserted_at <= valid_until``
       and raises ``SeamContractError`` — so the seam never emits one;
    2. the projection carries a ``context_digest``, so replacing the context is a mismatch;
    3. ``reconcile_phase4`` re-checks that digest;
    4. and — decisively — it re-derives the digest from the **request** via
       ``validate_subject_binding``, independently of the projection's carried context, so
       recomputing the forged digest does not help either.

    Measured: even with the context forged *and* its digest recomputed, construction is refused
    by reconciliation, never by the builder's own ordering guard. The guard is therefore dead
    code as the pipeline stands.

    It is kept because the owner ratified it and because the builder should not assume its
    inputs came from the seam — but "defence in depth" is the honest description, not
    "load-bearing". Whether to keep or drop it is an open decision recorded in the PR.
    """

    projection = build_projection()
    broken = _forged_projection(
        projection,
        subject_valid_from=projection.context.subject_asserted_at + MICROSECOND,
    )
    with pytest.raises(ReconciliationError) as exc:
        _build(projection=broken)
    assert exc.value.reason is Reason.CONTEXT_DIGEST_MISMATCH
    assert "context_digest" in str(exc.value)
    # Specifically NOT the builder's ordering reason — that is the whole point.
    assert exc.value.reason is not Reason.SUBJECT_TEMPORAL_ORDERING


def test_the_seam_itself_refuses_the_ordering_the_builder_also_checks():
    """The upstream contract the builder's guard mirrors, measured at its own boundary."""

    from risk_authority.integrations.evaluation_contracts import SeamContractError

    projection = build_projection()
    with pytest.raises(SeamContractError) as exc:
        dataclasses.replace(
            projection.context,
            subject_valid_from=projection.context.subject_asserted_at + MICROSECOND,
        )
    assert "subject_valid_from <= subject_asserted_at <= subject_valid_until" in str(exc.value)


def test_a_decision_that_expires_exactly_when_evaluated_is_admitted():
    """Equality is valid: a zero-length decision window is degenerate, not impossible."""

    projection = build_projection()
    decision = build_decision(projection)
    at_once = dataclasses.replace(decision, expires_at=decision.evaluated_at)
    candidate = _build(projection=projection, decision=at_once)
    assert candidate.decision_expires_at_fact == candidate.decision_evaluated_at_fact


# ======================================================================================
# One microsecond the wrong side of each boundary
# ======================================================================================
def test_a_decision_expiring_one_microsecond_before_evaluation_is_refused():
    projection = build_projection()
    decision = build_decision(projection)
    broken = dataclasses.replace(
        decision, expires_at=decision.evaluated_at - MICROSECOND
    )
    with pytest.raises(TemporalOrderingError) as exc:
        _build(projection=projection, decision=broken)
    assert exc.value.reason is Reason.DECISION_TEMPORAL_ORDERING
    assert "not a window" in str(exc.value)


def test_an_attestation_one_microsecond_before_the_recommendation_is_refused():
    projection = build_projection()
    early = build_attestation(
        recommendation_digest=projection.recommendation_digest,
        issued_at=projection.context.subject_asserted_at - MICROSECOND,
    )
    with pytest.raises(TemporalOrderingError) as exc:
        _build(projection=projection, attestation=early)
    assert exc.value.reason is Reason.ATTESTATION_TEMPORAL_ORDERING
    assert "before it exists" in str(exc.value)


def test_an_attestation_one_microsecond_after_the_recommendation_expires_is_refused():
    """The upper bound has its own reason to exist: a late attestation must not revive."""

    projection = build_projection()
    late = build_attestation(
        recommendation_digest=projection.recommendation_digest,
        issued_at=projection.context.subject_valid_until + MICROSECOND,
    )
    with pytest.raises(TemporalOrderingError) as exc:
        _build(projection=projection, attestation=late)
    assert exc.value.reason is Reason.ATTESTATION_TEMPORAL_ORDERING
    assert "usable again" in str(exc.value)


# ======================================================================================
# Malformed input gets the malformed refusal, never an ordering one and never a bare raise
# ======================================================================================
@pytest.mark.parametrize("field", ["evaluated_at", "expires_at"])
def test_a_naive_decision_instant_is_a_canonical_field_refusal(field):
    """Not an ordering reason: the value is malformed, not validly ordered wrongly."""

    projection = build_projection()
    decision = build_decision(projection)
    naive = dataclasses.replace(
        decision, **{field: getattr(decision, field).replace(tzinfo=None)}
    )
    with pytest.raises(Exception) as exc:
        _build(projection=projection, decision=naive)
    assert not isinstance(exc.value, TypeError), "a bare TypeError is not a refusal"
    assert "temporal_ordering" not in getattr(exc.value, "reason", Reason.MALFORMED_CANONICAL_FIELD).value


def test_no_bare_exception_escapes_for_any_malformed_instant():
    """Every failure is a typed contract refusal this package declares."""

    from ugence_cloud_scaling_authorization_contracts import (
        CloudScalingAuthorizationContractError,
    )

    projection = build_projection()
    decision = build_decision(projection)
    for field in ("evaluated_at", "expires_at"):
        broken = object.__new__(type(decision))
        for f in dataclasses.fields(decision):
            object.__setattr__(broken, f.name, getattr(decision, f.name))
        object.__setattr__(broken, field, "not-a-datetime")
        with pytest.raises(CloudScalingAuthorizationContractError):
            _build(projection=projection, decision=broken)


def test_the_three_reasons_are_distinct_and_named_for_what_failed():
    assert len({
        Reason.SUBJECT_TEMPORAL_ORDERING,
        Reason.DECISION_TEMPORAL_ORDERING,
        Reason.ATTESTATION_TEMPORAL_ORDERING,
    }) == 3


def test_the_gate_reads_no_clock():
    """The whole justification for putting this in Phase 5A rather than Phase 5B."""

    import inspect

    from ugence_cloud_scaling_authorization_contracts import candidate as module

    source = inspect.getsource(module)
    for forbidden in ("datetime.now(", "datetime.utcnow(", "time.time(", "date.today("):
        assert forbidden not in source
