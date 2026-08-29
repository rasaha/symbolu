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
    AuthorizationCandidateRejectionReason as _Reason,
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
    assert excinfo.value.reason is _Reason.MALFORMED_CANONICAL_FIELD


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
    assert excinfo.value.reason is _Reason.NON_CANONICAL_IDENTIFIER


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
    assert excinfo.value.reason is _Reason.MALFORMED_CANONICAL_FIELD


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
    assert excinfo.value.reason is _Reason.ACTION_SUBSTITUTION


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
    assert excinfo.value.reason is _Reason.MALFORMED_CANONICAL_FIELD


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
    assert excinfo.value.reason is _Reason.MALFORMED_PRODUCER_ATTESTATION


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
    assert excinfo.value.reason is _Reason.MALFORMED_CANONICAL_FIELD


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
    assert excinfo.value.reason is _Reason.UNSUPPORTED_SCHEMA_VERSION


def test_a_coordinate_tenant_carrying_surrounding_whitespace_is_refused(target_scope):
    """Guard 28 — ``target.py:562``, ``tenant != tenant.strip()``.

    ``policy_tenant_id`` is the one component admitted through ``allow_empty=True``, so it
    does not pass through ``require_canonical_identifier`` and carries its own whitespace
    guard. Empty is legitimate; empty-looking is not.
    """

    from tests.conftest import build_policy_coordinate_binding  # noqa: PLC0415

    with pytest.raises(PolicyTargetBindingError) as excinfo:
        build_policy_coordinate_binding(target_scope, policy_tenant_id=" t-1 ")
    assert excinfo.value.reason is _Reason.NON_CANONICAL_IDENTIFIER


def test_a_coordinate_naming_a_body_its_signature_never_covered_is_refused(target_scope):
    """Guard 29 — ``target.py:572``, ``policy_content_digest != policy_body_digest``.

    This is the check standing in for ADR residual R-3: issuance enforces the equality and
    resolution does not re-enforce it, so a coordinate that names one body in its content
    digest and another in the digest its signature covers is refused here or nowhere.
    """

    from tests.conftest import build_policy_coordinate_binding  # noqa: PLC0415

    with pytest.raises(PolicyTargetBindingError) as excinfo:
        build_policy_coordinate_binding(target_scope, policy_content_digest="b" * 64)
    assert excinfo.value.reason is _Reason.MALFORMED_POLICY_COORDINATE_BINDING


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
    assert excinfo.value.reason is _Reason.CONTEXT_DIGEST_MISMATCH


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
    assert excinfo.value.reason is _Reason.CONTEXT_DIGEST_MISMATCH


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
    assert excinfo.value.reason is _Reason.ACTION_SUBSTITUTION


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
    assert excinfo.value.reason is _Reason.PROJECTION_RECONCILIATION_FAILED


def test_a_disposition_that_is_not_the_seam_enum_is_refused(projection, decision):
    """Guard 62 — ``reconciliation.py:371``, ``not isinstance(d_disposition, ...)``.

    A string that reads ``"allow"`` is not an ALLOW-family disposition. Admitting one would
    make the membership test below it a string comparison against an enum.
    """

    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(projection, _bypassing_post_init(decision, disposition="allow"))
    assert excinfo.value.reason is _Reason.UNSUPPORTED_EXACT_TYPE


@pytest.mark.parametrize(
    ("guard", "overrides", "expected"),
    [
        (64, {"risk_outcome": None}, _Reason.MISSING_BINDING_DECISION),
        (65, {"decision_snapshot": None}, _Reason.MISSING_DECISION_SNAPSHOT),
        (66, {"decision_snapshot": [("decision_id", "d-1")]},
         _Reason.MISSING_DECISION_SNAPSHOT),
        (67, {"decision_digest": None}, _Reason.MISSING_BINDING_DECISION),
        (81, {"expires_at": None}, _Reason.MISSING_EXPIRY_FACT),
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
    assert excinfo.value.reason is expected


@pytest.mark.parametrize(
    ("guard", "key", "expected"),
    [
        (69, "decision_id", _Reason.MISSING_BINDING_DECISION),
        (77, "evidence_snapshot_digest", _Reason.INVALID_EVIDENCE_BINDING),
    ],
)
def test_a_snapshot_missing_a_required_key_is_refused(
    projection, decision, guard, key, expected
):
    """Guards 69 and 77 — snapshot keys the reconciler reads, with the digest re-derived."""

    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(projection, _snapshot_without(decision, key))
    assert excinfo.value.reason is expected


def test_a_projection_with_no_idempotency_key_is_refused(projection, decision):
    """Guard 72 — ``reconciliation.py:444``, ``not p_idempotency_key``.

    Kept ahead of the canonical admission on purpose: an absent key and a malformed one are
    different findings, and admitting first would report both as malformed.
    """

    forged = _bypassing_post_init(projection, idempotency_key="")
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert excinfo.value.reason is _Reason.IDEMPOTENCY_KEY_MISMATCH


def test_a_projection_with_no_evidence_references_is_refused(projection, decision):
    """Guard 75 — ``reconciliation.py:468``, ``not isinstance(..., tuple) or not ...``."""

    forged = _bypassing_post_init(projection, evidence_references=())
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert excinfo.value.reason is _Reason.INVALID_EVIDENCE_BINDING


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


def test_the_in_tree_drift_assertions_hold():
    """The test-time half of §9.3, and the measurement behind guard 11's exclusion.

    Each assertion below re-runs one import-time condition against what is actually
    installed. All three are False in this tree, which is the package importing correctly
    rather than a claim about any of them.

    It carries a classification only for **guard 11**, whose operands are two frozen
    literals defined in this module, in this distribution: no resolution can move either,
    so ``if False:`` is the same program on every path and ``equivalent-mutant`` holds.
    That argument is available precisely because nothing outside this distribution supplies
    an operand.

    It is **not** available for guard 9, and the earlier version of this test claimed
    otherwise for all three. Guard 9's right operands come from Phase 4C, admitted by an
    open-ended pin, so its condition being False here says only that one resolution agrees.
    Measuring it needed a second resolution, which is
    ``test_the_phase_4c_drift_guard_fires_under_a_second_permitted_resolution``; it is
    SCORED and killed. Guard 10 is excluded on reachability, measured separately.
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

    # The four ratified pairs guard 9 compares. Agreement here is not why guard 9 is
    # classified as it is — it is SCORED, and killed under a second resolution.
    assert ids.PURPOSE_CAPACITY_ACTION == PHASE4C_PURPOSE
    assert ids.DOMAIN_CLOUD_SCALING == PHASE4C_DOMAIN
    assert ids.SUBJECT_TYPE_CAPACITY_SUBJECT == PHASE4C_SUBJECT_TYPE
    assert ids.CANONICAL_ACTION_TYPES == PHASE4C_ACTION_TYPES

    # Guard 10 — ``controller_actions != CANONICAL_ACTION_TYPES``.
    assert frozenset(kind.value for kind in ActionKind) == ids.CANONICAL_ACTION_TYPES

    # Guard 11 — ``PRODUCER_SIGNING_PURPOSE == PURPOSE_CAPACITY_ACTION``. The producer
    # signing purpose must stay distinct from the D-4 routing purpose.
    assert ids.PRODUCER_SIGNING_PURPOSE != ids.PURPOSE_CAPACITY_ACTION


#: Source of the probe the guard-10 measurement below runs. It reports which guard answered,
#: so a refusal from a guard upstream of this one cannot be read as this one firing.
ACTION_VOCABULARY_PROBE = (
    "try:\n"
    "    import ugence_cloud_scaling_authorization_contracts.identifiers as ids\n"
    "    from ugence_cloud_scaling_controller.planning.candidates import ActionKind\n"
    "    print('NO-IMPORT-ERROR ratified=' + repr(sorted(ids.CANONICAL_ACTION_TYPES))\n"
    "          + ' controller=' + repr(sorted(k.value for k in ActionKind)))\n"
    "except ImportError as exc:\n"
    "    print('IMPORT-ERROR ' + str(exc))\n"
)


def test_a_projection_whose_request_carries_a_different_context_is_refused(
    projection, decision
):
    """Guard 50 — ``reconciliation.py:283``, isolated from guard 54.

    Guard 54 digests the projection's own ``context``; guard 50 re-derives from the
    *request*. Here the request is re-derived around a forged context — self-consistent, so
    revalidation succeeds — while the projection's ``context`` and ``context_digest`` are
    left genuine. Guard 54 is silent, because those two still agree; only guard 50 consults
    the request's copy.

    Without this test guard 50 survives under the ratified definition: the attack in
    ``test_a_projection_whose_context_digest_is_a_lie_is_refused`` is caught by guard 54
    with the *same* reason, so removing guard 50 changed nothing the typed refusal records.
    That made guard 50 look diagnostic-only. It is not — it was under-attacked.
    """

    from risk_authority.integrations import SubjectBinding  # noqa: PLC0415

    context = _bypassing_post_init(projection.context, action_type="scale_sideways")
    binding = SubjectBinding(
        tenant_id=projection.tenant_id,
        subject_id=projection.subject_id,
        subject_type=projection.request.subject_type,
        recommendation_digest=projection.recommendation_digest,
        context_digest=context.digest(),
    )
    request = _bypassing_post_init(
        projection.request, subject_context=context, subject_digest=binding.digest()
    )
    forged = _bypassing_post_init(projection, request=request)
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert excinfo.value.reason is _Reason.CONTEXT_DIGEST_MISMATCH


def test_evidence_references_that_are_not_a_tuple_are_refused(projection, decision):
    """Guard 75 — ``reconciliation.py:468``, the non-tuple half.

    The *empty* case is caught downstream by the equality comparison against the request's
    own references, with the same reason — so the empty-tuple attack alone left guard 75
    looking diagnostic-only. A **list** with identical contents is a different matter:
    ``tuple(list) == tuple(tuple)``, so that comparison is silent, and only this guard's
    ``isinstance`` half stands between a mutable references container and the reconciled
    facts.
    """

    forged = _bypassing_post_init(
        projection, evidence_references=list(projection.evidence_references)
    )
    with pytest.raises(ReconciliationError) as excinfo:
        reconcile_phase4(forged, decision)
    assert excinfo.value.reason is _Reason.INVALID_EVIDENCE_BINDING


def test_the_action_kind_guard_fires_when_phase_4c_stops_refusing(tmp_path):
    """Guard 10 — ``identifiers.py:100``, ``controller_actions != CANONICAL_ACTION_TYPES``.

    Excluded as ``unreachable-behind-earlier-guard`` on the evidence that Phase 4C's own
    import-time check answers first. It does — *in this installation*. The earlier guard
    lives in ``ugence-cloud-scaling-risk-integration``, a **separate distribution** under an
    open-ended ``>=0.1.0`` pin, so "which guard fires first" is a fact about the resolution
    that happens to be installed, not about the program. ADR Phase 5 §9.2 already forbids
    exactly that reasoning for ``equivalent-mutant``; it now forbids it here too.

    The second resolution is a 0.2.0 that no longer refuses at import — a plausible
    relaxation, since that check duplicates one its consumers also make — paired with a
    controller ratifying a fifth ``ActionKind``. Phase 4C's ratified set is left untouched,
    so Phase 5A's *pair* check cannot be the one that answers and this guard is isolated.

    Present, Phase 5A refuses to import. Removed, it imports and binds a four-member
    vocabulary while the controller ratifies five — every candidate digest then carries an
    action vocabulary the controller has already moved past, which is the substitution the
    module docstring says fails closed.
    """

    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    declared = os.environ.get("UGENCE_REPO_ROOT")
    repo = Path(declared).resolve() if declared else Path(__file__).resolve().parents[4]

    def _edit(path, old_text, new_text):
        body = path.read_text(encoding="utf-8")
        assert body.count(old_text) == 1, (
            f"{path.name}: expected exactly one {old_text!r}; the drift this resolution "
            "introduces may not have been introduced at all"
        )
        path.write_text(body.replace(old_text, new_text), encoding="utf-8")

    chain = tmp_path / "chain-0.2.0"
    chain.mkdir()

    controller = chain / "ugence_cloud_scaling_controller"
    shutil.copytree(
        repo / "packages/capabilities/cloud-scaling-controller/src"
        / "ugence_cloud_scaling_controller",
        controller,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    _edit(
        controller / "planning/candidates.py",
        '    COORDINATED = "coordinated"',
        '    COORDINATED = "coordinated"\n    SIDEWAYS = "scale_sideways"',
    )

    phase4c = chain / "ugence_cloud_scaling_risk_integration"
    shutil.copytree(
        repo / "packages/integration/cloud-scaling-risk-integration/src"
        / "ugence_cloud_scaling_risk_integration",
        phase4c,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    _edit(phase4c / "version.py", '__version__ = "0.1.0"', '__version__ = "0.2.0"')
    _edit(
        phase4c / "identifiers.py",
        "if _CONTROLLER_ACTION_TYPES != CANONICAL_ACTION_TYPES:",
        "if False:  # a 0.2.0 that no longer refuses here",
    )

    probe = tmp_path / "action_vocabulary_probe.py"
    probe.write_text(ACTION_VOCABULARY_PROBE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [str(chain), *(p for p in sys.path if p)]
            ),
        },
    )
    output = result.stdout.strip()
    assert output.startswith("IMPORT-ERROR"), (
        "Phase 5A imported against a controller ratifying an action type it does not know, "
        f"and bound the shorter vocabulary anyway: {output!r} {result.stderr[-400:]!r}"
    )
    assert "Phase 5A fails closed" in output, (
        "the refusal came from a guard upstream of this one, which measures nothing about "
        f"this one: {output!r}"
    )


def test_an_attestation_rebuilt_from_its_canonical_wire_form_parses_its_instant():
    """Guard 48 — ``attestation.py:261``, ``isinstance(issued_at, str)``.

    The guard §9.1's conversion carve-out used to exclude, on the stated grounds that
    neutralising it produces no refusal to compare and changes what the suite can collect.
    An audit measured all three claims false, and this test is the third: nothing in the
    suite built an attestation from a canonical wire mapping, so the conversion was not
    merely excluded by definition — it was never executed.

    ``issued_at`` crosses the wire as a canonical string and reaches ``__post_init__`` as a
    ``datetime`` only because this line parses it. Without the parse the exact-type
    admission refuses the string, so the round trip a real consumer performs — serialize,
    transmit, rebuild — stops working.
    """

    from tests.conftest import build_attestation  # noqa: PLC0415

    genuine = build_attestation(recommendation_digest="sha256:" + "a" * 64)
    wire = genuine.to_canonical_dict()
    wire.pop("trust_state", None)
    # What a transport actually carries: the instant as its canonical string form.
    from risk_authority.crypto.canonical import to_canonical_obj  # noqa: PLC0415

    wire["issued_at"] = to_canonical_obj(genuine.issued_at)
    assert isinstance(wire["issued_at"], str), "the fixture no longer exercises the parse"

    rebuilt = ProducerAttestationEvidence.from_dict(wire)
    assert rebuilt.issued_at == genuine.issued_at
    assert rebuilt.digest() == genuine.digest()


#: Source of the second-resolution probe run by the guard-9 measurement below.
SECOND_RESOLUTION_PROBE = (
    "import sys\n"
    "try:\n"
    "    import ugence_cloud_scaling_authorization_contracts.identifiers\n"
    "    print('NO-IMPORT-ERROR')\n"
    "except ImportError as exc:\n"
    "    print('IMPORT-ERROR ' + str(exc))\n"
)


def test_the_phase_4c_drift_guard_fires_under_a_second_permitted_resolution(tmp_path):
    """Guard 9 — ``identifiers.py:93``, ``ours != theirs``. Scored, not unscorable.

    This guard was previously excluded as ``unscorable-by-single-checkout-fixture``: its
    right operand comes from ``ugence-cloud-scaling-risk-integration``, admitted by an
    open-ended ``>=0.1.0`` pin, and the sweep fixture installs exactly one resolution. That
    reasoning conflated two things. The *fixture* installs one resolution; the *test* is
    free to construct another. A pin that admits any version at or above 0.1.0 admits a
    0.2.0 that renames a ratified identifier, and building that distribution is the whole
    measurement.

    So it is built here, from the real Phase 4C source rather than a stub — a stub would
    prove something about the stub — with two edits: the version bumped to 0.2.0, and
    ``PURPOSE_CAPACITY_ACTION`` renamed. Placed first on ``PYTHONPATH`` it *is* the
    resolution, exactly as a released 0.2.0 would be.

    Under it the guard fires and Phase 5A refuses to import. Remove the guard and the import
    succeeds, binding ``cloud_scaling.capacity_action`` into every candidate digest while
    Phase 4C ratifies ``cloud_scaling.capacity_action.v2`` — the substitution the module
    docstring says fails closed. That is a change to the typed refusal (ADR Phase 5 §9.1:
    ImportError versus no refusal at all), so the guard is authority-bearing and scorable,
    and the exclusion is withdrawn.

    The kill rests on *whether* the import refused, not on what it said. The message is
    asserted afterwards only to pin which of the three import-time guards answered.

    In a subprocess because the measurement re-runs module-level import code; doing it
    in-process would leave a drifted Phase 4C in ``sys.modules`` for every later test.
    """

    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    declared = os.environ.get("UGENCE_REPO_ROOT")
    repo = Path(declared).resolve() if declared else Path(__file__).resolve().parents[4]
    origin = (
        repo
        / "packages"
        / "integration"
        / "cloud-scaling-risk-integration"
        / "src"
        / "ugence_cloud_scaling_risk_integration"
    )
    assert origin.is_dir(), f"Phase 4C source not found at {origin}"

    resolution = tmp_path / "resolution-0.2.0"
    package = resolution / "ugence_cloud_scaling_risk_integration"
    shutil.copytree(origin, package, ignore=shutil.ignore_patterns("__pycache__"))

    version = package / "version.py"
    bumped = version.read_text(encoding="utf-8").replace(
        '__version__ = "0.1.0"', '__version__ = "0.2.0"'
    )
    assert '"0.2.0"' in bumped, "Phase 4C no longer declares 0.1.0; re-derive this bound"
    version.write_text(bumped, encoding="utf-8")

    identifiers = package / "identifiers.py"
    before = identifiers.read_text(encoding="utf-8")
    ratified = 'PURPOSE_CAPACITY_ACTION: Final[str] = "cloud_scaling.capacity_action"'
    assert before.count(ratified) == 1, (
        "the identifier this resolution renames is no longer spelled as expected, so the "
        "drift it is supposed to introduce may not have been introduced at all"
    )
    identifiers.write_text(
        before.replace(
            ratified,
            'PURPOSE_CAPACITY_ACTION: Final[str] = "cloud_scaling.capacity_action.v2"',
        ),
        encoding="utf-8",
    )

    probe = tmp_path / "second_resolution_probe.py"
    probe.write_text(SECOND_RESOLUTION_PROBE, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(probe)],
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            # The drifted resolution first, so it *is* the installed Phase 4C for this
            # process. Everything after it is whatever this suite is already running
            # against — under the sweep, that is the mutated copy.
            "PYTHONPATH": os.pathsep.join(
                [str(resolution), *(p for p in sys.path if p)]
            ),
        },
    )
    output = result.stdout.strip()
    assert output.startswith("IMPORT-ERROR"), (
        "Phase 5A imported cleanly against a Phase 4C resolution that renamed a ratified "
        f"identifier, binding an unratified value: {output!r} {result.stderr[-400:]!r}"
    )
    assert "PURPOSE_CAPACITY_ACTION" in output, (
        f"the refusal came from some guard other than the D-4 pair check: {output!r}"
    )
