"""Coverage for the guards the CI mutation sweep found unscored.

The sweep on ``932869c3`` neutralised each of Phase 5A's 109 authority-bearing guards in
turn and ran the whole suite against the result. 78 died. The 31 that survived were not
guards the suite tests weakly — they were guards the suite never reached at all, so
removing them changed nothing any test could see.

A survivor is a coverage defect, not an exclusion. Each test below reaches exactly one
surviving guard through the public surface it defends and asserts the refusal that guard
alone produces; the guard number in each docstring is its index in ``guard_inventory.json``
and the sweep re-runs against these tests, so a guard that stops being load-bearing shows
up here as a survivor again rather than as silence.

Where a guard is genuinely unreachable, redundant behind an earlier one, or an equivalent
mutant, it is recorded in ``guard_classification.json`` with the measurement that shows it
— never here, and never merely because it survived.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_cloud_scaling_authorization_contracts import (
    CanonicalFieldError,
    ExactTypeError,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    PolicyTargetBindingReferenceV2,
    ProducerAttestationEvidence,
    PolicyTargetBindingError,
    ProducerAttestationError,
    ReconciliationError,
    TargetScopeError,
    digest_of_snapshot,
    reconcile_phase4,
)


def _bypassing_post_init(artifact, **overrides):
    """A field-for-field copy with ``**overrides``, skipping ``__post_init__``.

    Same instrument as ``test_reconciliation_integrity``: ``dataclasses.replace`` re-runs
    the constructor's own validation, and several guards below sit *behind* that validation
    on a path a fabricated artifact reaches.
    """

    forged = object.__new__(type(artifact))
    for field in dataclasses.fields(artifact):
        object.__setattr__(forged, field.name, getattr(artifact, field.name))
    for name, value in overrides.items():
        object.__setattr__(forged, name, value)
    return forged


# --- canonical.py ---------------------------------------------------------------------


def test_a_snapshot_that_is_not_a_mapping_is_refused():
    """Guard 1 — ``canonical.py:82``, ``not isinstance(snapshot, Mapping)``.

    ``digest_of_snapshot`` is the independent re-derivation the reconciler leans on. Handed
    a sequence, an unguarded canonicalizer would happily digest it and return a digest that
    binds nothing.
    """

    with pytest.raises(CanonicalFieldError) as excinfo:
        digest_of_snapshot([("decision_id", "d-1")])
    assert "must be a mapping" in str(excinfo.value)


def test_an_identifier_carrying_surrounding_whitespace_is_refused(projection):
    """Guard 7 — ``canonical.py:171``, ``text != text.strip()``.

    Reached through ``ExecutionTargetScope``, which admits every one of its identifiers
    through ``require_canonical_identifier``. Whitespace is not cosmetic here: canonical
    digests are over the exact bytes, so ``" acct"`` and ``"acct"`` are two different
    subjects that read as one to a human reviewing an audit record.
    """

    from tests.conftest import build_target_scope  # noqa: PLC0415

    with pytest.raises(CanonicalFieldError) as excinfo:
        build_target_scope(projection, account_id=" acct-1 ")
    assert "whitespace" in str(excinfo.value)


# --- target.py ------------------------------------------------------------------------


def test_a_negative_permitted_ceiling_is_refused(projection):
    """Guard 12 — ``target.py:101``, ``type(value) is not int or value < 0``.

    The ceilings are what every bound check compares against. A negative ceiling is not
    merely nonsense — it is a ceiling no request can satisfy, which turns a bound check
    into an unconditional refusal, and the mirror case (an ``int`` subclass that lies about
    ``<``) is why the type half is exact.
    """

    from tests.conftest import build_target_scope  # noqa: PLC0415

    with pytest.raises(TargetScopeError) as excinfo:
        build_target_scope(projection, max_magnitude=-1)
    assert "max_permitted_magnitude" in str(excinfo.value)


def test_a_bool_permitted_ceiling_is_refused(projection):
    """Guard 12, the exact-type half — ``bool`` is not ``int`` exactly.

    ``isinstance(True, int)`` is true, so an ``isinstance`` admission would let ``True``
    stand as the ceiling 1. This is the measured half of the R-12B repair.
    """

    from tests.conftest import build_target_scope  # noqa: PLC0415

    with pytest.raises(TargetScopeError):
        build_target_scope(projection, max_delta=True)


def test_an_action_type_outside_the_ratified_set_is_refused(projection):
    """Guard 15 — ``target.py:168``, ``action not in CANONICAL_ACTION_TYPES``.

    Action substitution: a scope that names an action D-4 never ratified would carry a
    ratified-looking digest for an action nobody authorized.
    """

    from tests.conftest import build_target_scope  # noqa: PLC0415

    with pytest.raises(TargetScopeError) as excinfo:
        build_target_scope(projection, action_type="scale_sideways")
    assert "ratified canonical action type" in str(excinfo.value)


def test_execution_target_scope_from_dict_refuses_a_non_mapping():
    """Guard 18 — ``target.py:268``, ``not isinstance(data, Mapping)``."""

    with pytest.raises(ExactTypeError):
        ExecutionTargetScope.from_dict([("tenant_id", "t-1")])


def test_policy_target_binding_from_dict_refuses_a_non_mapping():
    """Guard 24 — ``target.py:436``, ``not isinstance(data, Mapping)``."""

    with pytest.raises(ExactTypeError):
        PolicyTargetBindingReference.from_dict([("policy_id", "p-1")])


def test_policy_target_binding_from_dict_refuses_a_missing_field(policy_binding):
    """Guard 26 — ``target.py:453``, ``missing``.

    A dropped field is not an absent field: ``from_dict`` would fill it from ``data[...]``
    and raise ``KeyError``, which is an accident rather than a refusal. The guard turns it
    into a typed one that names what is missing.
    """

    data = policy_binding.to_canonical_dict()
    # ``trust_state`` is derived, and ``from_dict`` refuses it as an input on purpose.
    data.pop("trust_state", None)
    data.pop("policy_id")
    with pytest.raises(CanonicalFieldError) as excinfo:
        PolicyTargetBindingReference.from_dict(data)
    assert "policy_id" in str(excinfo.value)


def test_policy_coordinate_binding_from_dict_refuses_a_non_mapping():
    """Guard 31 — ``target.py:659``, ``not isinstance(data, Mapping)``."""

    with pytest.raises(ExactTypeError):
        PolicyTargetBindingReferenceV2.from_dict([("policy_id", "p-1")])


# --- attestation.py -------------------------------------------------------------------


def test_an_unsupported_signature_algorithm_is_refused(projection):
    """Guard 37 — ``attestation.py:133``.

    Phase 5A verifies no signature. That is exactly why the admitted algorithm matters: the
    algorithm name is all a later verifier has to go on, and an unadmitted one would reach
    it as though Phase 5A had considered it.
    """

    from tests.conftest import build_attestation  # noqa: PLC0415

    genuine = build_attestation(recommendation_digest=projection.recommendation_digest)
    with pytest.raises(ProducerAttestationError) as excinfo:
        dataclasses.replace(genuine, signature_algorithm="rsa-md5")
    assert "unsupported signature_algorithm" in str(excinfo.value)


def test_producer_attestation_from_dict_refuses_a_non_mapping():
    """Guard 40 — ``attestation.py:234``, ``type(data) is not dict and not isinstance(...)``."""

    with pytest.raises(ExactTypeError):
        ProducerAttestationEvidence.from_dict([("producer_id", "p-1")])


def test_producer_attestation_from_dict_refuses_a_missing_field(attestation):
    """Guard 42 — ``attestation.py:250``, ``missing``."""

    data = attestation.to_canonical_dict()
    data.pop("trust_state", None)
    data.pop("producer_id")
    with pytest.raises(CanonicalFieldError) as excinfo:
        ProducerAttestationEvidence.from_dict(data)
    assert "producer_id" in str(excinfo.value)


def test_producer_attestation_from_dict_requires_an_explicit_schema_version(attestation):
    """Guard 43 — ``attestation.py:255``, ``'schema_version' not in data``.

    Distinct from guard 42, which the ``_ALLOWED_KEYS - {"schema_version"}`` term
    deliberately excuses: the version must be *stated*, not defaulted, because a default
    would silently re-version an artifact produced under different rules.
    """

    data = attestation.to_canonical_dict()
    data.pop("trust_state", None)
    data.pop("schema_version")
    with pytest.raises(CanonicalFieldError) as excinfo:
        ProducerAttestationEvidence.from_dict(data)
    assert "schema_version" in str(excinfo.value)


def test_a_coordinate_tenant_carrying_surrounding_whitespace_is_refused(target_scope):
    """Guard 28 — ``target.py:562``, ``tenant != tenant.strip()``.

    ``policy_tenant_id`` is the one component admitted through ``allow_empty=True``, so it
    does not pass through ``require_canonical_identifier`` and carries its own whitespace
    guard. Empty is legitimate; empty-looking is not.
    """

    from tests.conftest import build_policy_coordinate_binding  # noqa: PLC0415

    with pytest.raises(PolicyTargetBindingError) as excinfo:
        build_policy_coordinate_binding(target_scope, policy_tenant_id=" t-1 ")
    assert "whitespace" in str(excinfo.value)


def test_a_coordinate_naming_a_body_its_signature_never_covered_is_refused(target_scope):
    """Guard 29 — ``target.py:572``, ``policy_content_digest != policy_body_digest``.

    This is the check standing in for ADR residual R-3: issuance enforces the equality and
    resolution does not re-enforce it, so a coordinate that names one body in its content
    digest and another in the digest its signature covers is refused here or nowhere.
    """

    from tests.conftest import build_policy_coordinate_binding  # noqa: PLC0415

    with pytest.raises(PolicyTargetBindingError) as excinfo:
        build_policy_coordinate_binding(target_scope, policy_content_digest="b" * 64)
    assert "policy_content_digest must equal policy_body_digest" in str(excinfo.value)


# --- reconciliation.py ----------------------------------------------------------------
#
# Every attack below is built with ``_bypassing_post_init``: ``reconcile_phase4`` admits
# only the *exact* ``CapacityRiskSubjectProjection`` and ``SubjectRiskDecision``, so a stub
# is refused at the door and proves nothing about the guards behind it. What reaches these
# guards is a genuine instance of the exact type carrying a value its own constructor would
# have refused — which is precisely the artifact a fabricator with the canonicaliser
# produces, and precisely what the reconciler exists to catch.


def _reforged_projection(projection, **context_overrides):
    """A projection self-consistent about a forged context, digests and all re-derived.

    Forging the context alone does not reach the guards that read it: the reconciler
    revalidates the *request*, whose ``subject_context`` still carries the genuine value, so
    guard 50 refuses first. A fabricator would re-derive, so this re-derives — new context,
    new ``context_digest``, a new ``SubjectBinding`` over it, new ``subject_digest``, and a
    request carrying both. What survives that is what the guard under test alone catches.
    """

    from risk_authority.integrations import SubjectBinding  # noqa: PLC0415

    context = _bypassing_post_init(projection.context, **context_overrides)
    context_digest = context.digest()
    binding = SubjectBinding(
        tenant_id=projection.tenant_id,
        subject_id=projection.subject_id,
        subject_type=projection.request.subject_type,
        recommendation_digest=projection.recommendation_digest,
        context_digest=context_digest,
    )
    subject_digest = binding.digest()
    request = _bypassing_post_init(
        projection.request, subject_context=context, subject_digest=subject_digest
    )
    return _bypassing_post_init(
        projection,
        context=context,
        context_digest=context_digest,
        binding=binding,
        subject_digest=subject_digest,
        request=request,
        request_digest=request.digest(),
    )


def _snapshot_without(decision, key):
    """The decision with one snapshot key dropped and ``decision_digest`` re-derived.

    Dropping the key alone would die at the digest recomputation, which is a different
    guard. Re-deriving is what makes the test aim at the one that reads the field.
    """

    from ugence_cloud_scaling_authorization_contracts.canonical import (  # noqa: PLC0415
        digest_of_snapshot,
    )

    snapshot = dict(decision.decision_snapshot)
    snapshot.pop(key, None)
    return _bypassing_post_init(
        decision, decision_snapshot=snapshot, decision_digest=digest_of_snapshot(snapshot)
    )


def test_a_projection_whose_context_digest_is_a_lie_is_refused(projection, decision):
    """Guard 50 — ``reconciliation.py:283``, ``validation.context_digest != p_context_digest``.

    The independent re-derivation: the digest is recomputed from the request the projection
    carries, never read back from the projection's own copy of it.
    """

    forged = _bypassing_post_init(projection, context_digest="0" * 64)
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert "revalidation produced a different context_digest" in str(excinfo.value)


def test_a_projection_whose_context_disagrees_with_its_request_is_refused(
    projection, decision
):
    """Guard 54 — ``reconciliation.py:303``, ``p_context.digest() != p_context_digest``.

    Not redundant behind guard 50, and the difference is the whole point. Guard 50 compares
    the digest recomputed from the **request** against the carried digest; guard 54 compares
    the digest of the projection's **own** ``context`` object against the same value. A
    projection carrying a genuine request and a swapped context passes the first and fails
    the second — the two copies are different objects, and only guard 54 reads the second.
    """

    swapped = _bypassing_post_init(
        projection,
        context=_bypassing_post_init(projection.context, action_type="scale_sideways"),
    )
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(swapped, decision)
    assert "context_digest does not match the carried context" in str(excinfo.value)


def test_a_self_consistent_unratified_action_type_is_refused(projection):
    """Guard 61 — ``reconciliation.py:364``, ``action_type not in CANONICAL_ACTION_TYPES``.

    Action substitution surviving a full re-derivation. Guard 15 defends the execution
    target scope; this defends the reconciled facts, and a candidate reaches Phase 5B
    through this path whether or not a scope was ever built.
    """

    from tests.conftest import build_decision  # noqa: PLC0415

    forged = _reforged_projection(projection, action_type="scale_sideways")
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, build_decision(forged))
    assert "not a D-4 ratified canonical action type" in str(excinfo.value)


def test_a_self_consistent_negative_magnitude_is_refused(projection):
    """Guard 44 — ``reconciliation.py:122``, ``type(value) is not int or value < 0``.

    Reached at the very end, where the reconciled facts are assembled: every digest check
    above has already passed, because the forgery re-derived them. A negative magnitude is
    the value every downstream bound check would compare against.
    """

    from tests.conftest import build_decision  # noqa: PLC0415

    forged = _reforged_projection(projection, magnitude_before=-1)
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, build_decision(forged))
    assert "magnitude_before must be an int >= 0" in str(excinfo.value)


def test_a_disposition_that_is_not_the_seam_enum_is_refused(projection, decision):
    """Guard 62 — ``reconciliation.py:371``, ``not isinstance(d_disposition, ...)``.

    A string that reads ``"allow"`` is not an ALLOW-family disposition. Admitting one would
    make the membership test below it a string comparison against an enum.
    """

    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(projection, _bypassing_post_init(decision, disposition="allow"))
    assert "must be a SubjectRiskDisposition" in str(excinfo.value)


@pytest.mark.parametrize(
    ("guard", "overrides", "expected"),
    [
        (64, {"risk_outcome": None}, "must carry a risk_outcome"),
        (65, {"decision_snapshot": None}, "must carry the binding decision_snapshot"),
        (66, {"decision_snapshot": [("decision_id", "d-1")]},
         "decision_snapshot must be a canonical mapping"),
        (67, {"decision_digest": None}, "must carry a decision_digest"),
        (81, {"expires_at": None}, "must carry an expires_at"),
    ],
)
def test_an_allow_family_decision_missing_a_binding_fact_is_refused(
    projection, decision, guard, overrides, expected
):
    """Guards 64, 65, 66, 67 and 81 — the binding facts an ALLOW must carry.

    Each is a separate refusal with its own diagnosis, and they are parametrised rather than
    merged because a single test asserting "some refusal happened" would let four of the
    five be deleted without a failure.
    """

    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(projection, _bypassing_post_init(decision, **overrides))
    assert expected in str(excinfo.value)


@pytest.mark.parametrize(
    ("guard", "key", "expected"),
    [
        (69, "decision_id", "decision_snapshot carries no decision_id"),
        (77, "evidence_snapshot_digest", "carries no evidence_snapshot_digest"),
    ],
)
def test_a_snapshot_missing_a_required_key_is_refused(
    projection, decision, guard, key, expected
):
    """Guards 69 and 77 — snapshot keys the reconciler reads, with the digest re-derived."""

    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(projection, _snapshot_without(decision, key))
    assert expected in str(excinfo.value)


def test_a_projection_with_no_idempotency_key_is_refused(projection, decision):
    """Guard 72 — ``reconciliation.py:444``, ``not p_idempotency_key``.

    Kept ahead of the canonical admission on purpose: an absent key and a malformed one are
    different findings, and admitting first would report both as malformed.
    """

    forged = _bypassing_post_init(projection, idempotency_key="")
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert "carries no D-6 idempotency_key" in str(excinfo.value)


def test_a_projection_with_no_evidence_references_is_refused(projection, decision):
    """Guard 75 — ``reconciliation.py:468``, ``not isinstance(..., tuple) or not ...``."""

    forged = _bypassing_post_init(projection, evidence_references=())
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert "at least one evidence reference" in str(excinfo.value)


# --- identifiers.py -------------------------------------------------------------------
#
# Guards 9, 10 and 11 are the only Phase 5A survivors this module does not kill, and they
# are not killable by this operator. Each compares two frozen constants at import time, and
# in-tree the comparison is False — so rewriting the ``if`` header to ``if False:`` produces
# a program that behaves identically on every path, for every input, forever. That is an
# equivalent mutant, and no test can distinguish it: a test that could would have to make
# the condition true, which means editing a constant, which is a different mutation operator
# than gate removal.
#
# What they defend is real, so the ADR (Phase 5 §9) asks for the assertions at test time as
# well as at import time. That instrument was missing; it is below. It does not kill the
# guards, and this comment says so rather than letting a green test imply otherwise.


def test_the_ratified_identifiers_have_not_drifted_from_phase_4c():
    """The test-time half of the drift assertion (ADR Phase 5 §9).

    Re-runs the import-time check explicitly. Import alone would raise, but only in a
    process that imports this package *after* the drift — a stale wheel, an editable install
    pointing at an older checkout, or a resolver that satisfied Phase 4C from elsewhere all
    produce a green suite and a drifted binding.
    """

    from ugence_cloud_scaling_authorization_contracts import identifiers as ids  # noqa: PLC0415

    ids._assert_no_drift()


def test_the_drift_guards_are_equivalent_mutants_because_their_conditions_are_false():
    """Why guards 9, 10 and 11 are classified ``EXCLUDED`` rather than left as survivors.

    The exclusion rests on a measurable claim, so the claim is measured here: each guard's
    condition is False in-tree. A guard whose condition never holds cannot change behaviour
    when it is removed. If any assertion below ever fails, the exclusion is void — and the
    package will already have failed to import, which is the guard doing its job.
    """

    from ugence_cloud_scaling_controller.planning.candidates import ActionKind  # noqa: PLC0415
    from ugence_cloud_scaling_risk_integration import (  # noqa: PLC0415
        CANONICAL_ACTION_TYPES as PHASE4C_ACTION_TYPES,
    )
    from ugence_cloud_scaling_risk_integration import (  # noqa: PLC0415
        DOMAIN_CLOUD_SCALING as PHASE4C_DOMAIN,
    )
    from ugence_cloud_scaling_risk_integration import (  # noqa: PLC0415
        PURPOSE_CAPACITY_ACTION as PHASE4C_PURPOSE,
    )
    from ugence_cloud_scaling_risk_integration import (  # noqa: PLC0415
        SUBJECT_TYPE_CAPACITY_SUBJECT as PHASE4C_SUBJECT_TYPE,
    )

    from ugence_cloud_scaling_authorization_contracts import identifiers as ids  # noqa: PLC0415

    # Guard 9 — ``ours != theirs``, over all four ratified pairs.
    assert ids.PURPOSE_CAPACITY_ACTION == PHASE4C_PURPOSE
    assert ids.DOMAIN_CLOUD_SCALING == PHASE4C_DOMAIN
    assert ids.SUBJECT_TYPE_CAPACITY_SUBJECT == PHASE4C_SUBJECT_TYPE
    assert ids.CANONICAL_ACTION_TYPES == PHASE4C_ACTION_TYPES

    # Guard 10 — ``controller_actions != CANONICAL_ACTION_TYPES``.
    assert frozenset(kind.value for kind in ActionKind) == ids.CANONICAL_ACTION_TYPES

    # Guard 11 — ``PRODUCER_SIGNING_PURPOSE == PURPOSE_CAPACITY_ACTION``. The producer
    # signing purpose must stay distinct from the D-4 routing purpose.
    assert ids.PRODUCER_SIGNING_PURPOSE != ids.PURPOSE_CAPACITY_ACTION
