"""Closure-audit remediation: the four canonical guards no test exercised.

The closure audit ran the canonical guard sweep to completion and found four guards that
**survived** mutation — no test in the suite failed when they were removed:

===========  ==========================  ====================================================
Finding      Canonical guard             Condition
===========  ==========================  ====================================================
H-1          26  ``reconciliation.py``   ``snapshot_tenant != p_tenant``
H-2          27  ``reconciliation.py``   ``snapshot_domain != DOMAIN_CLOUD_SCALING``
M-1           9  ``reconciliation.py``   ``p_request.digest() != p_request_digest``
L-1           3  ``reconciliation.py``   ``value.tzinfo is None or value.utcoffset() is None``
N-1          32  ``reconciliation.py``   ``tuple(p_request.evidence_references) != tuple(...)``
===========  ==========================  ====================================================

**N-1 was not in the audit.** Completing the sweep for this remediation and submitting a
direct public-builder attack against *every* survivor found a fifth guard of the same
family. It is closed here rather than waived for having been unnamed — and it is the most
reachable of the five, needing no forced construction at all.

**What was and was not true.** Each guard was independently re-attacked through the public
builder before a line was written, and **all four refused the attack**: the shipped package
admitted no invalid candidate. What the sweep measured is real and is the defect being
closed here — the guards were *unguarded by any test*, so a future edit deleting one would
have created a genuine admission silently. The admission is therefore demonstrated the only
way it honestly can be: with the guard removed, in :mod:`_mutation_support`, and each test
below carries that proof.

**No duplicate gate was added.** Every one of these four guards already reconciles against
an independent source of truth, which the tests assert rather than assume:

* guard 26 compares the snapshot's tenant to ``p_tenant``, and ``tenant_id`` participates in
  both ``request.digest()`` and the subject binding that ``validate_subject_binding``
  re-derives — so a fabricator cannot vary it and keep the re-derived digests;
* guard 27 compares the snapshot's domain to ``DOMAIN_CLOUD_SCALING``, a module constant,
  which is the D-4 ratified value and not caller-supplied at all;
* guard 9 compares the carried ``request_digest`` against ``p_request.digest()``, recomputed
  from the request object itself — not against the decision's copy, which a fabricator
  controls;
* guard 3 requires an aware timestamp, which the canonicalizer cannot supply for itself;
* guard 32 compares the projection's ``evidence_references`` to the **request's**, which
  participate in ``request.digest()`` — the projection's own copy is bound by nothing.

Adding a second gate beside any of them would make the pair mutually sibling-backed and
therefore permanently unkillable by mutation — it would *destroy* the coverage property this
remediation exists to establish. The correct remediation for a survivor that already fails
closed is a test that exercises it, and that is what this module is.
"""

from __future__ import annotations

import dataclasses
import datetime as datetime_mod
import pathlib
import tempfile
import time

import pytest

from _mutation_support import guard_condition, mutated_package
from conftest import (
    build_projection,
    build_recommendation,
    coordinate_for,
    production_subject,
)
from ugence_cloud_scaling_authorization_contracts import (
    DOMAIN_CLOUD_SCALING,
    ExactTypeError,
    canonical_digest,
    AuthorizationCandidateRejectionReason as Reason,
    CanonicalFieldError,
    CapacityAuthorizationCandidate,
    ReconciliationError,
    build_capacity_authorization_candidate,
)
from ugence_cloud_scaling_authorization_contracts.canonical import digest_of_snapshot

VICTIM_TENANT = "tenant-victim"
FOREIGN_DOMAIN = "some_other_domain"

# Guard numbers are the canonical inventory's, asserted rather than trusted: if the source
# moves and a number now names a different condition, every test here fails loudly instead
# of silently mutating the wrong line.
GUARD_TZ_AWARE = 3
GUARD_REQUEST_REDERIVATION = 10
GUARD_SNAPSHOT_TENANT = 27
GUARD_SNAPSHOT_DOMAIN = 28
GUARD_EVIDENCE_BINDING = 33
# R-12b's seven, in source order.
GUARD_SNAPSHOT_HAS_EVALUATED_AT = 35
GUARD_SNAPSHOT_HAS_EXPIRES_AT = 36
GUARD_SNAPSHOT_HAS_ISSUED_AT = 37
GUARD_OUTER_EVALUATED_AT_IS_BOUND = 39
GUARD_OUTER_EXPIRES_AT_IS_BOUND = 40
GUARD_EVALUATED_AFTER_VALID_FROM = 41
GUARD_EVALUATED_BEFORE_ISSUED = 42
# R-12's own two. Both shifted +7 when R-12b added seven guards to `reconciliation.py`,
# which the condition-text anchor below caught — which is what it is for.
GUARD_COMPARABLE_IS_DATETIME = 43
GUARD_SUBJECT_ORDERING = 46

EXPECTED_CONDITIONS = {
    GUARD_TZ_AWARE: "value.tzinfo is None or value.utcoffset() is None",
    GUARD_REQUEST_REDERIVATION: "p_request.digest() != p_request_digest",
    GUARD_SNAPSHOT_TENANT: "snapshot_tenant != p_tenant",
    GUARD_SNAPSHOT_DOMAIN: "snapshot_domain != DOMAIN_CLOUD_SCALING",
    GUARD_EVIDENCE_BINDING: (
        "tuple(p_request.evidence_references) != tuple(p_evidence_references)"
    ),
    GUARD_SNAPSHOT_HAS_EVALUATED_AT: "snapshot_evaluated_at is None",
    GUARD_SNAPSHOT_HAS_EXPIRES_AT: "snapshot_expires_at is None",
    GUARD_SNAPSHOT_HAS_ISSUED_AT: "snapshot_issued_at is None",
    GUARD_OUTER_EVALUATED_AT_IS_BOUND: (
        "to_canonical_obj(decision_evaluated_at) != to_canonical_obj(snapshot_evaluated_at)"
    ),
    GUARD_OUTER_EXPIRES_AT_IS_BOUND: (
        "to_canonical_obj(decision_expires_at) != to_canonical_obj(snapshot_expires_at)"
    ),
    GUARD_EVALUATED_AFTER_VALID_FROM: "subject_valid_from > bound_evaluated_at",
    GUARD_EVALUATED_BEFORE_ISSUED: "bound_evaluated_at > bound_issued_at",
    GUARD_COMPARABLE_IS_DATETIME: "type(value) is not datetime",
    GUARD_SUBJECT_ORDERING: "not subject_from <= subject_asserted <= subject_until",
}

#: Sibling guards a reader might credit with each kill. Removing the sibling instead must
#: leave the attack refused — otherwise the test is measuring the sibling, not its own gate.
SIBLINGS = {
    GUARD_SNAPSHOT_TENANT: 12,          # p_tenant != d_tenant, shares TENANT_MISMATCH
    GUARD_SNAPSHOT_DOMAIN: 17,          # request requested_domain, shares D4_IDENTIFIER_MISMATCH
    GUARD_REQUEST_REDERIVATION: 13,     # p_request_digest != d_request_digest, shares the reason
    GUARD_TZ_AWARE: 2,                  # the isinstance(datetime) check in the same helper
    GUARD_EVIDENCE_BINDING: 32,         # the tuple/non-empty check on the same field
    # R-12b siblings: each is the gate a reader might credit with the same kill, and every
    # one shares DECISION_INSTANT_NOT_BOUND with its subject except where noted.
    GUARD_OUTER_EVALUATED_AT_IS_BOUND: GUARD_SNAPSHOT_HAS_EVALUATED_AT,
    GUARD_OUTER_EXPIRES_AT_IS_BOUND: GUARD_SNAPSHOT_HAS_EXPIRES_AT,
    GUARD_EVALUATED_AFTER_VALID_FROM: GUARD_EVALUATED_BEFORE_ISSUED,
    GUARD_EVALUATED_BEFORE_ISSUED: GUARD_EVALUATED_AFTER_VALID_FROM,
}


def _canonical_ts(value):
    """The canonical wire form of an instant, as the snapshot stores it."""

    from risk_authority.crypto.canonical import to_canonical_obj

    return to_canonical_obj(value)


def _artifacts_for(projection):
    """The four non-projection artifacts the builder needs, all genuine."""

    from conftest import build_attestation, build_policy_binding, build_target_scope

    scope = build_target_scope(projection)
    policy = build_policy_binding(scope)
    return dict(
        producer_attestation=build_attestation(
            recommendation_digest=projection.recommendation_digest
        ),
        policy_binding=policy,
        policy_coordinate_binding=coordinate_for(policy),
        target_scope=scope,
    )


def _bypassing_post_init(artifact, **overrides):
    """A field-for-field copy with ``**overrides`` applied, skipping ``__post_init__``.

    ``dataclasses.replace`` re-runs validation, which is exactly what these two tests must
    get past: the point is to hand the builder an artifact its own upstream contract would
    never have produced, and see what the builder itself does with it.
    """

    forged = object.__new__(type(artifact))
    for field in dataclasses.fields(artifact):
        object.__setattr__(forged, field.name, getattr(artifact, field.name))
    for name, value in overrides.items():
        object.__setattr__(forged, name, value)
    return forged


def test_the_canonical_guard_numbers_still_name_these_conditions():
    """Anchor the inventory before any mutation is aimed by number."""

    for number, condition in EXPECTED_CONDITIONS.items():
        assert guard_condition(number) == condition, (
            f"canonical guard {number} now reads {guard_condition(number)!r}; the sweep "
            f"anchors have drifted and every mutation below is aimed at the wrong line"
        )


class _ClockTripwire:
    """Fails the test if wall-clock time is read while a candidate is being refused.

    A sentinel, not a mock: it replaces nothing the builder legitimately uses. Phase 5A
    holds no clock, so any read at all is the failure.
    """

    def __enter__(self):
        self._saved = {n: getattr(time, n) for n in ("time", "monotonic", "time_ns")}

        def _fail(*_a, **_k):  # pragma: no cover - reaching this IS the failure
            raise AssertionError("the Phase 5A boundary read a clock while refusing input")

        for name in self._saved:
            setattr(time, name, _fail)
        return self

    def __exit__(self, *exc):
        for name, fn in self._saved.items():
            setattr(time, name, fn)
        return False


def _refuses(projection, decision, *, reason, diagnostic, not_diagnostic=None):
    """Submit the attack to the real public builder and assert it fails closed.

    Returns the raised error. Asserts the typed reason, a gate-specific diagnostic, that no
    candidate exists, that no clock was read, and that the entry point has no collaborator
    to reach in the first place.
    """

    import inspect

    from conftest import build_attestation, build_policy_binding, build_target_scope

    attestation = build_attestation(recommendation_digest=projection.recommendation_digest)
    scope = build_target_scope(projection)
    policy = build_policy_binding(scope)

    built = "sentinel"
    with _ClockTripwire():
        with pytest.raises(ReconciliationError) as exc:
            built = build_capacity_authorization_candidate(
                projection=projection,
                decision=decision,
                producer_attestation=attestation,
                policy_binding=policy,
                policy_coordinate_binding=coordinate_for(policy),
                target_scope=scope,
            )

    # 6. no candidate — and no envelope, authorization, credential, execution request or
    #    receipt, none of which this package can express at all.
    assert built == "sentinel", "the builder returned across a refusal"
    assert not isinstance(built, CapacityAuthorizationCandidate)
    # 2. typed rejection reason
    assert exc.value.reason is reason
    # 3. gate-specific diagnostic
    assert diagnostic in str(exc.value), f"{str(exc.value)!r} does not name this gate"
    if not_diagnostic is not None:
        assert not_diagnostic not in str(exc.value), "a sibling gate produced this refusal"
    # 7. there is no collaborator parameter to reach
    assert set(inspect.signature(build_capacity_authorization_candidate).parameters) == {
        "projection", "decision", "producer_attestation", "policy_binding",
        "policy_coordinate_binding", "target_scope",
    }
    return exc.value


def _admits_when_removed(tmp_path, guard, projection, decision):
    """4/5: the attack reaches candidate construction iff *this* guard is removed."""

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), guard)
        candidate = mp.build(projection, decision)
    assert type(candidate).__name__ == "CapacityAuthorizationCandidate"

    sibling = SIBLINGS[guard]
    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), sibling)
        with pytest.raises(Exception) as exc:
            mp.build(projection, decision)
    assert "guard neutralised" not in str(exc.value)
    return candidate


# ======================================================================================
# H-1 — canonical guard 26: the decision snapshot names a different tenant
# ======================================================================================


def _snapshot_variant(decision, **fields):
    """A decision whose binding snapshot differs, with its digest honestly recomputed.

    ``dataclasses.replace`` re-runs Risk Authority's own ``__post_init__``, so the result is
    an internally valid ``SubjectRiskDecision``. Recomputing ``decision_digest`` over the
    altered snapshot is what a fabricator would do — and is what makes this attack
    interesting: the decision is *self*-consistent, so every digest check passes.
    """

    snapshot = dict(decision.decision_snapshot)
    snapshot.update(fields)
    return dataclasses.replace(
        decision, decision_snapshot=snapshot, decision_digest=digest_of_snapshot(snapshot)
    )


def test_a_decision_snapshot_naming_another_tenant_is_refused(projection, decision):
    """H-1: canonical guard 26, isolated.

    The projection and the decision's own ``tenant_id`` both restate the legitimate tenant,
    so the projection-versus-decision tenant gate (guard 11) cannot fire. The binding
    snapshot — the artifact that records *what was actually decided* — names a different
    tenant, and its ``decision_digest`` is recomputed so the snapshot re-derivation
    (guard 24) accepts it too.

    Without guard 26 the candidate is built for the legitimate tenant on the authority of a
    decision whose own record says it was about somebody else. Because the candidate takes
    its tenant from the projection, nothing downstream can ever notice.
    """

    forged = _snapshot_variant(decision, tenant_id=VICTIM_TENANT)

    # Every sibling that could absorb this failure is asserted to still agree.
    assert forged.tenant_id == projection.tenant_id            # guard 11 cannot fire
    assert forged.request_digest == projection.request_digest  # guard 12 cannot fire
    assert forged.subject_digest == projection.subject_digest  # guard 13 cannot fire
    assert forged.decision_digest == digest_of_snapshot(forged.decision_snapshot)
    assert forged.decision_snapshot["tenant_id"] == VICTIM_TENANT

    error = _refuses(
        projection,
        forged,
        reason=Reason.TENANT_MISMATCH,
        diagnostic="the decision snapshot names a different tenant",
        # guard 11's message, which shares this reason code, must NOT be what fired
        not_diagnostic="vs decision",
    )
    assert VICTIM_TENANT not in str(error), "the gate must not echo the substituted tenant"


def test_the_snapshot_tenant_gate_is_the_only_thing_refusing_it(
    tmp_path, projection, decision
):
    """H-1 attribution: removing guard 26 admits; removing its sibling does not."""

    forged = _snapshot_variant(decision, tenant_id=VICTIM_TENANT)
    candidate = _admits_when_removed(
        tmp_path, GUARD_SNAPSHOT_TENANT, projection, forged
    )
    # The admission is silent: the candidate names the legitimate tenant.
    assert candidate.tenant_id == projection.tenant_id


def test_the_snapshot_tenant_is_reconciled_against_an_independently_derived_value(
    projection,
):
    """H-1 design: ``p_tenant`` is not a second attacker-controlled copy.

    ``tenant_id`` participates in the request digest *and* in the subject binding that
    ``validate_subject_binding`` re-derives, so it cannot be varied while the re-derivations
    still agree. That is what makes guard 26 a reconciliation against an independent source
    rather than a comparison of two fabricated objects.
    """

    from risk_authority.integrations import validate_subject_binding

    request = projection.request
    other = dataclasses.replace(request, tenant_id=VICTIM_TENANT)
    assert request.digest() != other.digest(), "tenant_id is outside the request digest"

    with pytest.raises(Exception) as exc:
        validate_subject_binding(other)
    assert "subject_digest" in str(exc.value)


# ======================================================================================
# H-2 — canonical guard 27: the decision snapshot names a foreign domain
# ======================================================================================


def test_a_decision_snapshot_naming_another_domain_is_refused(projection, decision):
    """H-2: canonical guard 27, isolated.

    The request's own ``requested_domain`` is the D-4 ratified value, so the request-level
    domain gate (guard 16) cannot fire; the snapshot alone names a foreign domain, with its
    digest recomputed so the snapshot re-derivation accepts it.

    Guard 27 binds the snapshot to ``DOMAIN_CLOUD_SCALING`` — a module constant, never
    caller-supplied — so a fabricated projection and a fabricated decision cannot validate
    each other merely by agreeing on an attacker-chosen domain.
    """

    forged = _snapshot_variant(decision, domain=FOREIGN_DOMAIN)

    assert projection.request.requested_domain == DOMAIN_CLOUD_SCALING  # guard 16 cannot fire
    assert forged.tenant_id == projection.tenant_id                     # guard 11 cannot fire
    assert forged.decision_snapshot["tenant_id"] == projection.tenant_id  # guard 26 cannot fire
    assert forged.decision_digest == digest_of_snapshot(forged.decision_snapshot)

    _refuses(
        projection,
        forged,
        reason=Reason.D4_IDENTIFIER_MISMATCH,
        diagnostic="the decision snapshot names domain",
        # guard 16's message, which shares this reason code
        not_diagnostic="requested_domain",
    )


def test_the_snapshot_domain_gate_is_the_only_thing_refusing_it(
    tmp_path, projection, decision
):
    """H-2 attribution: removing guard 27 admits; removing its sibling does not."""

    forged = _snapshot_variant(decision, domain=FOREIGN_DOMAIN)
    candidate = _admits_when_removed(
        tmp_path, GUARD_SNAPSHOT_DOMAIN, projection, forged
    )
    # The admission is silent: the candidate restates the ratified domain regardless.
    assert candidate.domain == DOMAIN_CLOUD_SCALING


def test_the_ratified_domain_is_a_module_constant_not_a_carried_value(projection, decision):
    """H-2 design: one side of guard 27 is ratified, not supplied.

    There is no argument to the public builder, and no field on any input artifact, that can
    change what guard 27 compares against.
    """

    import inspect

    from ugence_cloud_scaling_authorization_contracts import identifiers

    assert identifiers.DOMAIN_CLOUD_SCALING == DOMAIN_CLOUD_SCALING
    source = inspect.getsource(
        __import__(
            "ugence_cloud_scaling_authorization_contracts.reconciliation",
            fromlist=["reconcile_phase4"],
        ).reconcile_phase4
    )
    assert "snapshot_domain != DOMAIN_CLOUD_SCALING" in source


# ======================================================================================
# M-1 — canonical guard 9: the carried request_digest is re-derived from the request
# ======================================================================================


def _projection_with(projection, **overrides):
    """An exact-typed projection forced past its own constructor.

    ``CapacityRiskSubjectProjection.__post_init__`` enforces this same property, so an
    *ordinarily constructed* projection can never carry the mismatch — which is asserted
    below. Forcing it is how a fabricated or replayed artifact reaches Phase 5A, and guard 9
    is the independent re-derivation standing behind it.
    """

    from ugence_cloud_scaling_risk_integration import CapacityRiskSubjectProjection

    forced = object.__new__(CapacityRiskSubjectProjection)
    for field in dataclasses.fields(projection):
        object.__setattr__(forced, field.name, getattr(projection, field.name))
    for name, value in overrides.items():
        object.__setattr__(forced, name, value)
    assert type(forced) is CapacityRiskSubjectProjection
    return forced


def test_a_projection_whose_request_digest_is_a_lie_is_refused(projection, decision):
    """M-1: canonical guard 9, isolated.

    The audit refuted the claim that this property was safely sibling-backed. The named
    sibling — guard 12, ``p_request_digest != d_request_digest`` — compares the projection's
    copy to the decision's, and a fabricator controls both. Here they are *made to agree* on
    a fabricated digest, so guard 12 cannot fire.

    What varies is the independent value: ``p_request.digest()``, recomputed from the
    carried request object. Guard 9 is the only check that consults it.
    """

    fabricated = "sha256:" + "0" * 64
    true_digest = projection.request.digest()
    assert projection.request_digest == true_digest

    forced = _projection_with(projection, request_digest=fabricated)
    agreeing = dataclasses.replace(decision, request_digest=fabricated)

    # The two attacker-controlled values agree; only the independent one differs.
    assert forced.request_digest == agreeing.request_digest      # guard 12 cannot fire
    assert forced.request.digest() == true_digest != fabricated
    assert agreeing.tenant_id == projection.tenant_id            # guard 11 cannot fire

    _refuses(
        projection=forced,
        decision=agreeing,
        reason=Reason.REQUEST_DIGEST_MISMATCH,
        diagnostic="request_digest does not match the carried request",
        # guard 12's message, which shares this reason code
        not_diagnostic="the decision was made against",
    )


def test_the_request_rederivation_gate_is_the_only_thing_refusing_it(
    tmp_path, projection, decision
):
    """M-1 attribution: removing guard 9 admits; removing sibling guard 12 does not."""

    fabricated = "sha256:" + "0" * 64
    forced = _projection_with(projection, request_digest=fabricated)
    agreeing = dataclasses.replace(decision, request_digest=fabricated)
    candidate = _admits_when_removed(
        tmp_path, GUARD_REQUEST_REDERIVATION, forced, agreeing
    )
    # The admission binds the fabricated digest into the candidate, under a valid digest.
    assert candidate.request_digest == fabricated


def test_an_ordinarily_constructed_projection_cannot_carry_the_mismatch(projection):
    """M-1 scope: the exact-type path is protected upstream as well.

    Guard 9 is defence in depth for *ordinary* construction and the only defence for a
    forced one. Both facts are recorded rather than one being used to excuse the other.
    """

    with pytest.raises(Exception) as exc:
        dataclasses.replace(projection, request_digest="sha256:" + "0" * 64)
    assert "request_digest" in str(exc.value)


# ======================================================================================
# L-1 — canonical guard 3: timezone-naive validity timestamps
# ======================================================================================

#: Every authoritative validity timestamp Phase 5A accepts, and the artifact that holds the
#: bound copy of it. The three subject instants live on the **context** — the R-12 correction
#: made that the reconciler's only source for them, replacing the projection's unbound outer
#: ``valid_from``/``valid_until``/``asserted_at`` fields.
#:
#: **The two decision instants stay on the decision, and that is deliberate.** R-12b re-sourced
#: their *values* from ``decision_snapshot``, so the obvious move is to attack them there too.
#: It cannot be done and must not be faked: the snapshot stores instants as canonical UTC
#: **strings**, so a timezone-naive snapshot timestamp is not representable at all.
#:
#: Worse, moving these rows would delete live coverage. ``to_canonical_obj`` formats a naive
#: datetime by *attaching* UTC, so a naive outer ``evaluated_at`` canonicalizes to exactly the
#: bound string and sails through the outer-equals-bound gates. Guard 3 is the only thing that
#: refuses it — solely attributed, still, and measured as such below.
VALIDITY_TIMESTAMPS = [
    ("context", "subject_valid_from", Reason.PROJECTION_RECONCILIATION_FAILED),
    ("context", "subject_valid_until", Reason.PROJECTION_RECONCILIATION_FAILED),
    ("context", "subject_asserted_at", Reason.PROJECTION_RECONCILIATION_FAILED),
    ("decision", "evaluated_at", Reason.PROJECTION_RECONCILIATION_FAILED),
    ("decision", "expires_at", Reason.MISSING_EXPIRY_FACT),
]


@pytest.mark.parametrize("holder,field,reason", VALIDITY_TIMESTAMPS)
def test_a_timezone_naive_validity_timestamp_is_refused(
    projection, decision, holder, field, reason
):
    """L-1: canonical guard 3, swept across every Phase 5A validity timestamp.

    A naive timestamp is not merely untidy. ``risk_authority.crypto.canonical`` formats a
    naive ``datetime`` by *attaching* UTC to it — so without this guard a naive local-time
    fact is silently reinterpreted as a different instant and bound into a candidate digest
    that then validates perfectly. Nothing downstream can recover the intended instant.

    The check is therefore a rejection, never a repair: Phase 5A does not attach UTC, does
    not convert from ambient local time, and does not normalize a malformed timestamp into a
    valid one.

    **How the attack is constructed changed with the R-12 correction, and it matters.** The
    three subject instants used to be attacked by ``dataclasses.replace`` on the projection's
    outer copy, because the reconciler read that copy and nothing validated it. That is the
    defect R-12 closed. They are now attacked on the context, which requires forcing past
    ``SubjectContext.__post_init__`` and recomputing ``context_digest`` — so guard 3 is no
    longer reachable for them by ordinary construction. It remains reachable that way for the
    two decision instants, which is why they are still attacked with ``replace``.
    """

    if holder == "context":
        context = projection.context
        aware = getattr(context, field)
        assert aware.tzinfo is not None
        object.__setattr__(context, field, aware.replace(tzinfo=None))
        # The context IS digest-bound, so the forgery must carry its own digest or it dies at
        # the re-derivation and this test measures that instead of guard 3.
        target = _bypassing_post_init(projection, context_digest=context.digest())
        other = decision
    else:
        aware = getattr(decision, field)
        assert aware.tzinfo is not None
        naive = dataclasses.replace(decision, **{field: aware.replace(tzinfo=None)})
        assert getattr(naive, field).tzinfo is None
        target, other = projection, naive

    _refuses(
        target,
        other,
        reason=reason,
        diagnostic=f"{field} must be timezone-aware",
        # guard 2's message: a naive datetime IS a datetime, so that sibling cannot fire
        not_diagnostic="must be a datetime",
    )


def test_the_awareness_gate_is_now_sibling_backed_rather_than_solely_attributed(
    tmp_path, projection, decision
):
    """L-1 attribution, corrected by R-12 — and the correction is the point.

    Guard 3 used to be the *only* thing refusing a naive timestamp: removing it admitted the
    candidate, and the naive fact was carried into the digest as though it had been UTC all
    along. That exclusive attribution is gone, deliberately.

    R-12's temporal-coherence gate has to compare these instants, and a gate whose fail-closed
    behaviour depends on another gate still being present is not fail-closed — with guard 3
    mutated away, a naive value reached the comparison and escaped as a bare ``TypeError``,
    an unclassified exception rather than a refusal. ``_comparable_instant`` now re-checks
    awareness before comparing, so the same malformed input is still refused, and refused with
    the package's existing canonical-field reason rather than an R-12 ordering reason.

    Neither guard was weakened to preserve a kill count. Correct fail-closed classification is
    worth more than exclusive attribution, and this test now measures the classification.
    """

    naive = decision.expires_at.replace(tzinfo=None)
    forged = dataclasses.replace(decision, expires_at=naive)
    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_TZ_AWARE)
        with pytest.raises(Exception) as exc:
            mp.build(projection, forged)

    # Matched by class *name* and reason *value*: the mutated package is a separate module
    # copy, so its exception classes are distinct objects from the ones imported here.
    assert type(exc.value).__name__ == "CanonicalFieldError"
    assert exc.value.reason.value == Reason.MALFORMED_CANONICAL_FIELD.value
    assert "timezone-aware" in str(exc.value)
    assert "decision_expires_at_fact" in str(exc.value)
    # Not an R-12 ordering reason: the value is malformed, not validly ordered wrongly.
    assert "temporal_ordering" not in exc.value.reason.value
    # And not the unclassified escape this replaced.
    assert not isinstance(exc.value, TypeError)


def test_the_comparable_type_gate_is_solely_responsible_for_classifying_a_non_datetime(
    tmp_path, projection, decision
):
    """R-12 guard 42, killed rather than assumed.

    The five Phase 4 instants are type-checked in ``reconciliation.py`` before they ever
    reach the coherence block, so they cannot exercise this gate. The sixth — the producer
    attestation's ``issued_at`` — is read straight off the attestation, and an attestation
    whose ``__post_init__`` was bypassed can carry anything. That is the only input that
    reaches ``_comparable_instant``'s type check, so that is the attack.

    With the gate present the input is a typed canonical-field refusal. With it removed the
    very next line dereferences ``.tzinfo`` on a string and the attack escapes as an
    unclassified ``AttributeError`` — no candidate, but no refusal either. The gate is
    therefore doing the classification on its own.
    """

    from conftest import build_attestation, build_policy_binding, build_target_scope

    genuine = build_attestation(recommendation_digest=projection.recommendation_digest)
    forged = _bypassing_post_init(genuine, issued_at="not-a-datetime")
    scope = build_target_scope(projection)
    policy = build_policy_binding(scope)

    with pytest.raises(CanonicalFieldError) as exc:
        build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=forged,
            policy_binding=policy,
            policy_coordinate_binding=coordinate_for(policy),
            target_scope=scope,
        )
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "attestation_issued_at_fact must be a datetime, not a str" in str(exc.value)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_COMPARABLE_IS_DATETIME)
        mutant = mp.attestation(recommendation_digest=projection.recommendation_digest)
        object.__setattr__(mutant, "issued_at", "not-a-datetime")
        with pytest.raises(Exception) as escaped:
            mp.build(projection, decision, attestation=mutant)
    assert type(escaped.value).__name__ == "AttributeError", (
        "with guard 42 removed the non-datetime must escape unclassified; if some other "
        "gate now refuses it, this kill belongs to that gate and not to guard 42"
    )


def test_removing_the_subject_ordering_guard_changes_nothing_it_is_not_load_bearing(
    tmp_path, projection, decision
):
    """R-12 guard 45's status, measured rather than argued — and it has been wrong before.

    The guard was claimed unreachable on an argument that reasoned only about the subject
    *context* and missed the projection's unauthenticated outer copy of the same three
    instants, which was a live vector until the R-12 correction sourced the reconciler from
    the context. This test therefore measures the status instead of restating it: with the
    guard neutralised and nothing else changed, the strongest available forgery — the
    context mutated in place so every digest re-derives consistently — is refused exactly as
    it is with the guard present, and by the same upstream rule.

    That is what "defence in depth, not load-bearing" means here, and it will start failing
    the moment some path does reach the guard.
    """

    from datetime import timedelta

    context = projection.context
    object.__setattr__(
        context, "subject_valid_from", context.subject_asserted_at + timedelta(microseconds=1)
    )
    forged = _bypassing_post_init(projection, context_digest=context.digest())

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_SUBJECT_ORDERING)
        with pytest.raises(Exception) as exc:
            mp.build(forged, decision)
    assert type(exc.value).__name__ == "ReconciliationError"
    assert exc.value.reason.value == Reason.PROJECTION_RECONCILIATION_FAILED.value
    assert "subject_valid_from <= subject_asserted_at <= subject_valid_until" in str(exc.value)
    assert "guard neutralised" not in str(exc.value)


# ======================================================================================
# R-12b — the decision instants must come from the digest-bound snapshot
# ======================================================================================
def _snapshot_and_outer(decision, **snapshot_fields):
    """A decision whose snapshot carries ``snapshot_fields`` and whose digest re-derives.

    The outer ``evaluated_at`` / ``expires_at`` are left alone deliberately: these attacks
    are about the two disagreeing, and a helper that quietly kept them in step would measure
    nothing. Where a test wants them in step it says so.
    """

    snapshot = dict(decision.decision_snapshot)
    snapshot.update(snapshot_fields)
    return dataclasses.replace(
        decision, decision_snapshot=snapshot, decision_digest=digest_of_snapshot(snapshot)
    )


def test_backdating_the_outer_evaluated_at_no_longer_moves_the_carried_fact(
    tmp_path, projection, decision
):
    """**The R-12b defect, measured as the attack it closes.**

    ``SubjectRiskDecision.evaluated_at`` is an outer field: ``decision_digest`` covers
    ``decision_snapshot``, and before R-12b that snapshot carried no ``evaluated_at`` at all.
    So a plain ``dataclasses.replace`` moved the instant ten years with the digest still
    valid, and the candidate carried the backdated value.

    That fact is not inert. Phase 5B's occurrence gate refuses a determination whose ``as_of``
    precedes an instant the candidate says already happened, so moving this one earlier
    *widens* what that gate admits — a live bypass reachable by public construction.
    """

    backdated = dataclasses.replace(
        decision, evaluated_at=decision.evaluated_at - datetime_mod.timedelta(days=3650)
    )
    # The forgery really is self-consistent: this is why the digest gate cannot catch it.
    assert backdated.decision_digest == decision.decision_digest

    error = _refuses(
        projection,
        backdated,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="outer evaluated_at does not equal the value bound",
    )
    assert "decision_digest" not in str(error), "this is a source failure, not a corrupt artifact"
    _admits_when_removed(tmp_path, GUARD_OUTER_EVALUATED_AT_IS_BOUND, projection, backdated)


def test_backdating_it_in_the_snapshot_instead_cannot_even_be_constructed(decision):
    """The other half: where the value is bound, moving it is refused before Phase 5A sees it.

    Measured rather than assumed, and the measurement is stronger than expected — the forgery
    does not reach ``reconcile_phase4`` at all. ``SubjectRiskDecision.__post_init__`` re-derives
    ``decision_digest`` over the snapshot on every construction, ``dataclasses.replace``
    included, so a snapshot edit without a matching digest dies at the seam contract.

    Together with the test above, this is the whole of R-12b: before it, one of these two moves
    was free. Now neither is, and they fail in different places for different reasons.
    """

    from risk_authority.integrations.evaluation_contracts import SeamContractError

    forged = dict(decision.decision_snapshot)
    forged["evaluated_at"] = "2016-01-04T00:05:00.000000Z"
    with pytest.raises(SeamContractError) as exc:
        dataclasses.replace(decision, decision_snapshot=forged)
    assert "decision_digest must equal digest(decision_snapshot)" in str(exc.value)


def test_a_snapshot_carrying_no_evaluated_at_is_refused_rather_than_fallen_back_from(
    tmp_path, projection, decision
):
    """A pre-R-12b decision cannot supply the instant, and must not be allowed to pretend.

    The tempting reading is "fall back to the outer field for compatibility". That would
    silently restore the unauthenticated path for exactly the artifacts that need it closed,
    so the snapshot's absence is a refusal.

    **This guard is sibling-backed, not solely attributed, and that is stated rather than
    engineered around.** With it removed the input is still refused — by the outer-equals-bound
    gate, since a present outer instant cannot equal an absent bound one. What the guard adds
    is the *right diagnostic*: for a decision minted before R-12b the answer is "this artifact
    predates the field", not "someone rewrote a timestamp", and those send an operator to
    different places. Measured below in both directions.
    """

    snapshot = {k: v for k, v in decision.decision_snapshot.items() if k != "evaluated_at"}
    legacy = dataclasses.replace(
        decision, decision_snapshot=snapshot, decision_digest=digest_of_snapshot(snapshot)
    )
    assert "evaluated_at" not in legacy.decision_snapshot

    _refuses(
        projection,
        legacy,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="carries no evaluated_at",
    )

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_SNAPSHOT_HAS_EVALUATED_AT)
        with pytest.raises(Exception) as exc:
            mp.build(legacy_projection := projection, legacy)
    assert type(exc.value).__name__ == "ReconciliationError"
    assert exc.value.reason.value == Reason.DECISION_INSTANT_NOT_BOUND.value
    # Still refused, but now naming the wrong defect — which is what the guard buys.
    assert "does not equal the value bound" in str(exc.value)
    assert "carries no evaluated_at" not in str(exc.value)


def test_an_evaluation_stamped_before_the_recommendation_became_valid_is_refused(
    tmp_path, projection, decision
):
    """A fact cannot be decided before the thing it decides existed.

    Bound in the snapshot *and* mirrored on the outer field, so the outer-equals-bound gates
    cannot fire and the ordering gate is the only thing left.
    """

    early = projection.context.subject_valid_from - datetime_mod.timedelta(microseconds=1)
    forged = _snapshot_and_outer(decision, evaluated_at=_canonical_ts(early))
    forged = dataclasses.replace(forged, evaluated_at=early)

    _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="evaluated before the recommendation it decides became valid",
    )
    _admits_when_removed(tmp_path, GUARD_EVALUATED_AFTER_VALID_FROM, projection, forged)


def test_a_decision_issued_before_the_evaluation_it_binds_is_refused(
    tmp_path, projection, decision
):
    """Reversed order between the two bound instants: issuance cannot precede evaluation."""

    later = decision.evaluated_at + datetime_mod.timedelta(microseconds=1)
    forged = _snapshot_and_outer(decision, evaluated_at=_canonical_ts(later))
    forged = dataclasses.replace(forged, evaluated_at=later)

    _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="issued before the evaluation it binds",
    )
    _admits_when_removed(tmp_path, GUARD_EVALUATED_BEFORE_ISSUED, projection, forged)


def test_evaluation_and_issuance_in_the_same_instant_remain_legal(projection, decision):
    """Equality is legal and there is no tolerance window — the genuine fixture depends on it.

    The reference seam evaluates and issues at the same injected instant, so a strict
    comparison anywhere here would refuse the real chain. Worth stating, not assuming.
    """

    snapshot = decision.decision_snapshot
    assert snapshot["evaluated_at"] == snapshot["issued_at"]
    candidate = build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        **_artifacts_for(projection),
    )
    assert candidate.decision_evaluated_at_fact == decision.evaluated_at


def test_an_expiry_that_does_not_project_the_bound_one_is_refused(
    tmp_path, projection, decision
):
    """``expires_at`` is the second outer field, and it bounds authorization directly."""

    stretched = dataclasses.replace(
        decision, expires_at=decision.expires_at + datetime_mod.timedelta(days=3650)
    )
    assert stretched.decision_digest == decision.decision_digest

    _refuses(
        projection,
        stretched,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="outer expires_at does not equal the value bound",
    )
    _admits_when_removed(tmp_path, GUARD_OUTER_EXPIRES_AT_IS_BOUND, projection, stretched)


def test_a_three_digit_year_cannot_invert_the_bound_orderings(projection, decision):
    """**The ordering defect, pinned as the attack that found it.**

    The two orderings were first written against canonical *strings*, on the claim that the
    format is "fixed-width, zero-padded and UTC-normalised". Two thirds held: ``%f`` always
    pads and ``astimezone`` normalises. ``%Y`` does **not** pad below year 1000, so
    ``"999-12-31T…"`` sorts above ``"2026-01-01T…"`` while 999 precedes 2026 — and both
    guards inverted. The control is what made it decisive: a backdate of one year was
    refused and a backdate of a thousand was admitted.

    Both are refused now, but **by different gates, and the difference is worth stating.** A
    four-digit backdate parses and loses on ordering. A sub-1000 one never parses:
    ``strptime``'s ``%Y`` requires exactly four digits, so the writer can emit a form the
    reader will not accept. That asymmetry is the same one that caused the defect, and here
    it fails closed — which is the only direction it may fail.
    """

    from risk_authority.crypto.canonical import to_canonical_obj

    # The premise the old comment rested on, disproven in one line.
    ancient = datetime_mod.datetime(999, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc)
    modern = projection.context.subject_valid_from
    assert to_canonical_obj(ancient) > to_canonical_obj(modern), "the inversion is gone"
    assert ancient < modern, "…but chronologically it is a thousand years earlier"

    cases = [
        (2025, "evaluated before the recommendation it decides became valid"),
        (999, "is not a canonical UTC instant"),
        (99, "is not a canonical UTC instant"),
        (9, "is not a canonical UTC instant"),
    ]
    for year, diagnostic in cases:
        at = datetime_mod.datetime(year, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc)
        forged = _snapshot_and_outer(
            decision, evaluated_at=_canonical_ts(at), issued_at=_canonical_ts(at)
        )
        forged = dataclasses.replace(forged, evaluated_at=at)
        _refuses(
            projection,
            forged,
            reason=Reason.DECISION_INSTANT_NOT_BOUND,
            diagnostic=diagnostic,
        )


def test_the_four_digit_ordering_refusal_is_the_guard_and_not_a_sibling(
    tmp_path, projection, decision
):
    """Attribution for the ordering guard, on the case that actually reaches it."""

    at = datetime_mod.datetime(2025, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc)
    forged = _snapshot_and_outer(
        decision, evaluated_at=_canonical_ts(at), issued_at=_canonical_ts(at)
    )
    forged = dataclasses.replace(forged, evaluated_at=at)
    _admits_when_removed(tmp_path, GUARD_EVALUATED_AFTER_VALID_FROM, projection, forged)


def test_a_three_digit_issuance_cannot_invert_the_second_ordering(projection, decision):
    """The mirror: a genuine evaluation, issuance moved to year 999, was admitted."""

    ancient = datetime_mod.datetime(999, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc)
    forged = _snapshot_and_outer(decision, issued_at=_canonical_ts(ancient))
    _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="decision_snapshot.issued_at",
    )


@pytest.mark.parametrize("value", [0, "garbage", "2026-01-01T00:00:00Z"])
def test_a_non_instant_snapshot_value_is_a_typed_refusal_not_a_bare_typeerror(
    projection, decision, value
):
    """The second instance of the class ``_comparable_instant`` was written to prevent.

    ``snapshot_issued_at`` was only null-checked, never type-checked, so a non-string reached
    the raw ``>`` and escaped as ``builtins.TypeError`` — an unclassified exception rather
    than a refusal. The author diagnosed exactly this in ``candidate.py`` and did not apply
    it here; ``_bound_instant`` now does.

    The third case is a *well-formed RFC 3339 instant in the wrong precision*: canonical form
    carries microseconds, so a second-precision string is not the canonical encoding and is
    refused rather than guessed at.
    """

    forged = _snapshot_and_outer(decision, issued_at=value)
    error = _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="decision_snapshot.issued_at",
    )
    assert not isinstance(error, TypeError), "a bare TypeError is not a refusal"


def test_the_orderings_are_decided_on_instants_not_canonical_strings():
    """Pinned structurally, so the comparison cannot quietly move back onto strings."""

    import inspect

    from ugence_cloud_scaling_authorization_contracts import reconciliation as module

    source = inspect.getsource(module.reconcile_phase4)
    assert "subject_valid_from > bound_evaluated_at" in source
    assert "bound_evaluated_at > bound_issued_at" in source
    assert "to_canonical_obj(subject_valid_from) >" not in source
    assert "to_canonical_obj(snapshot_evaluated_at) >" not in source


class _CompliantInstant(datetime_mod.datetime):
    """A ``datetime`` subclass that satisfies every ordering by fiat.

    Deliberately built **without** ``to_canonical_obj``: the previous defect survived a green
    suite precisely because every attack value was constructed through the same primitive the
    guards were wrong in. A control that shares its subject's representation measures nothing.

    Overriding the comparison operators is not exotic — it is the cheapest way to defeat a
    gate that decides ordering on an object it did not construct.
    """

    def __gt__(self, other):  # pragma: no cover - the point is that it is never reached
        return False

    def __lt__(self, other):  # pragma: no cover
        return False

    def __ge__(self, other):  # pragma: no cover
        return True

    def __le__(self, other):  # pragma: no cover
        return True


def test_the_digest_cannot_distinguish_a_live_datetime_from_its_canonical_string(decision):
    """**Why the exact-type gate is load-bearing rather than tidy.**

    ``to_canonical_obj`` renders a ``datetime`` to exactly the string it would have been, so a
    snapshot carrying a live object and one carrying its rendered form hash identically. Every
    digest gate downstream — ``_bind``, ``digest_of_snapshot``, the candidate payload — is
    blind to the difference. The type is the only place it survives, which is why the check
    has to live there and not in a digest comparison.
    """

    ancient = _CompliantInstant(
        999, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc
    )
    live = {**decision.decision_snapshot, "evaluated_at": ancient, "issued_at": ancient}
    rendered = {
        **decision.decision_snapshot,
        "evaluated_at": "999-12-31T23:59:59.000000Z",
        "issued_at": "999-12-31T23:59:59.000000Z",
    }
    assert digest_of_snapshot(live) == digest_of_snapshot(rendered), (
        "if these ever differ the type gate could be a digest check instead"
    )


def test_a_live_datetime_in_the_snapshot_is_refused(tmp_path, projection, decision):
    """The hole the exact-type gate closes, measured end to end.

    Before it: a ``datetime`` subclass overriding ``__gt__`` in ``decision_snapshot`` carried a
    valid ``decision_digest``, was accepted by ``_bound_instant``'s ``isinstance`` branch, and
    satisfied both orderings by fiat — admitting an evaluation stamped in year 999.
    """

    ancient = _CompliantInstant(
        999, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc
    )
    forged = _snapshot_and_outer(decision, evaluated_at=ancient, issued_at=ancient)
    forged = dataclasses.replace(forged, evaluated_at=ancient)
    _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="must be a canonical instant string, not a live",
    )


def test_a_live_datetime_as_the_outer_evaluated_at_is_refused(projection, decision):
    """The same object on the outer ``evaluated_at``.

    **Guard 39 kills this, not ``_comparable_instant``** — measured, and worth naming
    correctly. The outer field must canonically equal the value bound in the snapshot, and
    the snapshot here still carries the genuine instant, so the outer-equals-bound equality
    gate refuses it before any coherence comparison is reached. The diagnostic asserted
    below is that gate's, which is what makes the attribution checkable rather than assumed.

    ``candidate.py``'s exact-type rule is a separate, later line of defence; it is measured
    on its own in ``test_a_datetime_subclass_in_any_carried_instant_is_refused_at_construction``.
    """

    ancient = _CompliantInstant(
        999, 12, 31, 23, 59, 59, tzinfo=datetime_mod.timezone.utc
    )
    forged = dataclasses.replace(decision, evaluated_at=ancient)
    _refuses(
        projection,
        forged,
        reason=Reason.DECISION_INSTANT_NOT_BOUND,
        diagnostic="does not equal the value bound",
    )


CARRIED_INSTANTS = (
    "subject_valid_from_fact",
    "subject_valid_until_fact",
    "subject_asserted_at_fact",
    "decision_evaluated_at_fact",
    "decision_expires_at_fact",
    "attestation_issued_at_fact",
)


@pytest.mark.parametrize("field", CARRIED_INSTANTS)
def test_a_datetime_subclass_in_any_carried_instant_is_refused_at_construction(field):
    """**The candidate's six instants are admitted by exact type, like its four artifacts.**

    Not symmetry for its own sake. ``canonical_digest`` renders a ``datetime`` subclass to
    exactly the string a plain ``datetime`` produces — asserted below — so
    ``candidate_digest`` cannot tell them apart. Phase 5B's gate 13 reads all six fields
    straight into ``<``/``>``, so a subclass overriding those operators verified ``VERIFIED``
    on every one, ``decision_evaluated_at_fact`` included: the ``_OCCURRENCE_FACTS`` member
    R-12b exists to bind.

    The subclass is declared directly rather than derived through ``to_canonical_obj``, for
    the reason the whole suite now follows: an attack value built from the primitive the
    guard is wrong about inherits its blind spot.
    """

    from conftest import build_candidate

    genuine = build_candidate()
    honest = getattr(genuine, field)
    sneaky = _CompliantInstant(
        honest.year, honest.month, honest.day, honest.hour, honest.minute,
        honest.second, honest.microsecond, tzinfo=datetime_mod.timezone.utc,
    )
    kwargs = {f.name: getattr(genuine, f.name) for f in dataclasses.fields(genuine)}
    kwargs[field] = sneaky

    with pytest.raises(ExactTypeError) as exc:
        CapacityAuthorizationCandidate(**kwargs)
    assert exc.value.reason is Reason.UNSUPPORTED_EXACT_TYPE
    assert field in str(exc.value)


def test_the_candidate_digest_cannot_distinguish_a_subclass_instant():
    """Why the exact-type gate carries this and no digest check can.

    If these ever differ, the distinction would survive in the digest and the type gate
    could be relaxed. They do not differ, so it cannot.
    """

    from conftest import build_candidate

    genuine = build_candidate()
    honest = genuine.decision_evaluated_at_fact
    sneaky = _CompliantInstant(
        honest.year, honest.month, honest.day, honest.hour, honest.minute,
        honest.second, honest.microsecond, tzinfo=datetime_mod.timezone.utc,
    )
    with_subclass = _bypassing_post_init(genuine, decision_evaluated_at_fact=sneaky)
    with_plain = _bypassing_post_init(genuine, decision_evaluated_at_fact=honest)
    assert canonical_digest(with_subclass.digest_payload()) == canonical_digest(
        with_plain.digest_payload()
    )


def test_the_canonicalizer_silently_attaches_utc_to_a_naive_timestamp():
    """L-1 rationale, proven rather than asserted.

    This is the behaviour guard 3 exists to keep out of the digest. It is a property of the
    shared canonicalizer and is not being changed here — Phase 5A refuses the input instead.
    """

    from datetime import datetime, timedelta, timezone

    from risk_authority.crypto import canonical_bytes

    naive = datetime(2026, 1, 1, 12, 0, 0)
    as_utc = naive.replace(tzinfo=timezone.utc)
    elsewhere = naive.replace(tzinfo=timezone(timedelta(hours=-5)))

    assert canonical_bytes({"t": naive}) == canonical_bytes({"t": as_utc})
    assert canonical_bytes({"t": naive}) != canonical_bytes({"t": elsewhere})


def test_the_attestation_timestamp_is_swept_for_the_same_class_of_defect():
    """L-1 sweep: ``issued_at`` is the sixth Phase 5A validity timestamp.

    It is validated in :mod:`attestation`, outside the 49 canonical in-scope guards, by its
    own awareness check. It is recorded here so the sweep over "every authoritative validity
    timestamp accepted by Phase 5A" is complete rather than complete-within-two-files.
    """

    from datetime import datetime

    from conftest import build_attestation
    from ugence_cloud_scaling_authorization_contracts import CanonicalFieldError

    # Built through the genuine fixture so every sibling gate — signing purpose, algorithm,
    # digest form — is satisfied and only the timestamp is naive.
    genuine = build_attestation(recommendation_digest="sha256:" + "1" * 64)
    naive = genuine.issued_at.replace(tzinfo=None)
    assert genuine.issued_at.tzinfo is not None

    with pytest.raises(CanonicalFieldError) as exc:
        dataclasses.replace(genuine, issued_at=naive)
    assert "timezone-aware" in str(exc.value)
    assert "rejected rather than assumed UTC" in str(exc.value)
    assert "must be a datetime" not in str(exc.value)


# ======================================================================================
# N-1 — canonical guard 32: the projection's evidence references misstate the request's
# ======================================================================================
#
# Found by completing the 49-guard sweep during this remediation, not by the closure audit.
# It is the same family as H-1/H-2/M-1/L-1 — a security-relevant guard with no test — and
# is closed the same way rather than waived for having been unnamed.
#
# It is also the most reachable of the five: no forced construction is needed at all.


def test_a_projection_misstating_the_requests_evidence_is_refused(projection, decision):
    """N-1: canonical guard 32, isolated.

    ``CapacityRiskSubjectProjection`` carries ``evidence_references`` as its own field, and
    an ordinarily constructed projection accepts any value for it — nothing upstream binds
    it to the request. The **request's** copy is different: it participates in
    ``request.digest()``, which guard 9 re-derives, so it cannot be varied silently.

    Guard 32 is the only place the two are reconciled. Without it a candidate is built whose
    ``evidence_references`` name evidence the risk decision was never evaluated against —
    and since the candidate takes the field from the *projection*, the substituted list is
    what every later phase would read.
    """

    fabricated = ("sha256:" + "a" * 64,)
    assert tuple(projection.request.evidence_references) != fabricated

    # Ordinary construction: no object.__new__, no forced attribute.
    forged = dataclasses.replace(projection, evidence_references=fabricated)
    assert forged.evidence_references == fabricated
    assert tuple(forged.request.evidence_references) == tuple(projection.evidence_references)

    # Siblings that could otherwise absorb the failure all still pass.
    assert forged.request_digest == projection.request_digest   # guard 9/12 cannot fire
    assert isinstance(forged.evidence_references, tuple) and forged.evidence_references
    assert decision.tenant_id == forged.tenant_id               # guard 11 cannot fire

    _refuses(
        forged,
        decision,
        reason=Reason.INVALID_EVIDENCE_BINDING,
        diagnostic="the request's evidence_references differ from the projection's",
        # guard 31's message, which shares this reason code
        not_diagnostic="at least one evidence reference",
    )


def test_the_evidence_binding_gate_is_the_only_thing_refusing_it(
    tmp_path, projection, decision
):
    """N-1 attribution: removing guard 32 admits; removing sibling guard 31 does not."""

    fabricated = ("sha256:" + "a" * 64,)
    forged = dataclasses.replace(projection, evidence_references=fabricated)
    candidate = _admits_when_removed(
        tmp_path, GUARD_EVIDENCE_BINDING, forged, decision
    )
    # The admission is the point: the candidate carries evidence nobody evaluated.
    assert candidate.evidence_references == fabricated


def test_the_requests_evidence_references_are_digest_anchored(projection):
    """N-1 design: one side of guard 32 is independently anchored, the other is not.

    This is what makes guard 32 a reconciliation rather than a comparison of two values the
    same caller can fabricate — and it is why the projection's copy is the untrusted one.
    """

    other = ("sha256:" + "a" * 64,)
    request = projection.request

    # The request's copy is inside the request digest, which guard 9 re-derives.
    assert request.digest() != dataclasses.replace(
        request, evidence_references=other
    ).digest()

    # The projection's copy is inside nothing: ordinary construction accepts any value and
    # every carried digest is unchanged.
    forged = dataclasses.replace(projection, evidence_references=other)
    assert forged.request_digest == projection.request_digest
    assert forged.context_digest == projection.context_digest
    assert forged.subject_digest == projection.subject_digest
