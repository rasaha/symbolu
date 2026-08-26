"""Adversarial properties: every way a caller might try to manufacture authority.

Each test states one distinct property. The uniform postcondition is that **no candidate
exists** afterwards — not a degraded one, not a flagged one, not a cached fragment.

Substitution attacks below are built by mutating one field of an otherwise perfect chain,
so a passing test means that single field is load-bearing.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import timedelta

import pytest

from conftest import (
    ACCOUNT_ID,
    PRODUCER_ID,
    RECOMMENDATION_ID,
    build_attestation,
    build_candidate,
    build_decision,
    build_policy_binding,
    build_policy_coordinate_binding,
    build_projection,
    build_recommendation,
    build_target_scope,
    coordinate_for,
    production_subject,
)
from risk_authority.integrations import SubjectRiskDecision
from ugence_cloud_scaling_authorization_contracts import (
    PRODUCER_SIGNING_PURPOSE,
    AuthorizationCandidateRejectionReason as Reason,
)
from ugence_cloud_scaling_authorization_contracts import (
    CandidateConstructionError,
    CapacityAuthorizationCandidate,
    ExactTypeError,
    ExecutionTargetScope,
    MagnitudeBoundError,
    PolicyTargetBindingError,
    PolicyTargetBindingReference,
    ProducerAttestationError,
    ProducerAttestationEvidence,
    ReconciliationError,
    TargetScopeError,
    build_capacity_authorization_candidate,
    reconcile_phase4,
)


def _build(**kw):
    return build_candidate(**kw)


# ======================================================================================
# Cross-artifact substitution
# ======================================================================================


def test_cross_tenant_substitution_is_refused():
    """A-1: a decision made for another tenant cannot back this projection."""

    ours = build_projection()
    theirs = build_projection(
        build_recommendation(subject=production_subject(tenant_id="tenant-2"))
    )
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(ours, build_decision(theirs))
    assert exc.value.reason in {
        Reason.TENANT_MISMATCH,
        Reason.REQUEST_DIGEST_MISMATCH,
        Reason.SUBJECT_MISMATCH,
    }


def test_cross_subject_substitution_is_refused():
    """A-2: a decision for a different workload cannot back this projection."""

    ours = build_projection()
    theirs = build_projection(
        build_recommendation(subject=production_subject(workload_id="payments-api"))
    )
    with pytest.raises(ReconciliationError):
        reconcile_phase4(ours, build_decision(theirs))


def test_recommendation_substitution_is_refused():
    """A-3: a projection of a different recommendation cannot reuse this decision."""

    ours = build_projection()
    other = build_projection(build_recommendation(predicted=12, recommendation_id="rec-other"))
    with pytest.raises(ReconciliationError):
        reconcile_phase4(other, build_decision(ours))


def test_attestation_for_another_recommendation_is_refused(projection, decision, target_scope, policy_binding):
    """A-4: an attestation binding a different recommendation digest is not evidence."""

    other = build_projection(build_recommendation(predicted=12, recommendation_id="rec-other"))
    foreign = build_attestation(recommendation_digest=other.recommendation_digest)
    with pytest.raises(ProducerAttestationError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=foreign,
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )
    assert exc.value.reason is Reason.PRODUCER_ATTESTATION_CONTENT_MISMATCH


def test_action_substitution_is_refused(projection, decision, attestation):
    """A-5: a scope naming a different action than the decision was made for is refused."""

    other_action = "scale_down" if projection.context.action_type != "scale_down" else "scale_up"
    scope = build_target_scope(projection, action_type=other_action)
    with pytest.raises(TargetScopeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=build_policy_binding(scope),
            policy_coordinate_binding=coordinate_for(build_policy_binding(scope)),
            target_scope=scope,
        )
    assert exc.value.reason is Reason.ACTION_SUBSTITUTION


@pytest.mark.parametrize(
    "field,value",
    [
        ("region", "eu-west-1"),
        ("zone", "eu-west-1c"),
        ("compute_group", "prod-eu-west-1-green"),
        ("resource_class", "deploy/other-api"),
        ("environment", "staging"),
    ],
)
def test_target_substitution_is_refused(projection, decision, attestation, field, value):
    """A-6: relocating the action to another region/zone/cluster/resource/env is refused."""

    scope = build_target_scope(projection, **{field: value})
    with pytest.raises(TargetScopeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=build_policy_binding(scope),
            policy_coordinate_binding=coordinate_for(build_policy_binding(scope)),
            target_scope=scope,
        )
    assert exc.value.reason is Reason.TARGET_SUBSTITUTION


def test_account_substitution_changes_the_binding_digest(projection):
    """A-7: a different account produces a different scope digest, breaking the policy tie."""

    a = build_target_scope(projection, account_id=ACCOUNT_ID)
    b = build_target_scope(projection, account_id="acct-999999999999")
    assert a.digest() != b.digest()


def test_policy_binding_for_another_account_is_refused(projection, decision, attestation):
    """A-8: a policy bound to another account's scope cannot be transplanted onto this one."""

    ours = build_target_scope(projection)
    theirs = build_target_scope(projection, account_id="acct-999999999999")
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=build_policy_binding(theirs),
            policy_coordinate_binding=coordinate_for(build_policy_binding(theirs)),
            target_scope=ours,
        )
    assert exc.value.reason is Reason.POLICY_TARGET_CONTENT_MISMATCH


def test_missing_account_binding_is_refused(projection):
    """A-9: a scope with no account is refused with the specific account reason."""

    with pytest.raises(TargetScopeError) as exc:
        build_target_scope(projection, account_id="")
    assert exc.value.reason is Reason.MISSING_ACCOUNT_BINDING


# ======================================================================================
# Escalation
# ======================================================================================


def test_magnitude_escalation_above_scope_maximum_is_refused(projection):
    """A-10: a requested magnitude above the permitted maximum cannot be represented."""

    with pytest.raises(MagnitudeBoundError) as exc:
        build_target_scope(projection, max_magnitude=projection.context.magnitude_after - 1)
    assert exc.value.reason is Reason.REQUESTED_MAGNITUDE_ABOVE_MAXIMUM


def test_delta_escalation_above_scope_maximum_is_refused(projection):
    """A-11: a delta above the permitted maximum cannot be represented."""

    delta = abs(projection.context.magnitude_after - projection.context.magnitude_before)
    with pytest.raises(MagnitudeBoundError) as exc:
        build_target_scope(projection, max_delta=delta - 1)
    assert exc.value.reason is Reason.DELTA_ABOVE_MAXIMUM


def test_scope_cannot_widen_bounds_beyond_the_policy(projection, decision, attestation):
    """A-12: a scope claiming a higher ceiling than the policy grants is refused."""

    scope = build_target_scope(projection, max_magnitude=100, max_delta=100)
    policy = build_policy_binding(scope, max_magnitude=8, max_delta=1)
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=policy,
            policy_coordinate_binding=coordinate_for(policy),
            target_scope=scope,
        )
    assert exc.value.reason is Reason.POLICY_TARGET_CONTENT_MISMATCH


# ======================================================================================
# Decision integrity
# ======================================================================================


def test_stale_phase4_digest_with_recomputed_outer_fields_is_refused(projection, decision):
    """A-13: recomputing the outer digests cannot launder a stale inner request digest."""

    stale = dataclasses.replace(decision, request_digest="sha256:" + "0" * 64)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, stale)
    assert exc.value.reason is Reason.REQUEST_DIGEST_MISMATCH


def test_decision_digest_mismatch_is_refused(projection, decision):
    """A-14: a decision_digest that is not digest(decision_snapshot) is refused."""

    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "decision_digest", "sha256:" + "a" * 64)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.DECISION_DIGEST_MISMATCH


def test_mutated_decision_snapshot_is_refused(projection, decision):
    """A-15: editing the snapshot without the digest breaks the recomputation."""

    tampered = dict(decision.decision_snapshot)
    # Widen the decision's scope — the substitution an attacker would actually want.
    tampered["decision_id"] = str(tampered.get("decision_id", "")) + "-widened"
    tampered["conditions"] = ["no-conditions-at-all"]
    assert tampered != dict(decision.decision_snapshot), "the mutation must be a real change"
    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "decision_snapshot", tampered)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.DECISION_DIGEST_MISMATCH


def test_missing_decision_snapshot_is_refused(projection, decision):
    """A-16: an ALLOW-family decision with no binding snapshot is refused."""

    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "decision_snapshot", None)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.MISSING_DECISION_SNAPSHOT


def test_missing_expiry_fact_is_refused(projection, decision):
    """A-17: a decision carrying no expires_at is refused."""

    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "expires_at", None)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.MISSING_EXPIRY_FACT


def test_idempotency_key_mismatch_is_refused(projection, decision):
    """A-18: a decision whose D-6 key differs from the projection's is refused."""

    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "idempotency_key", "sha256:" + "b" * 64)
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.IDEMPOTENCY_KEY_MISMATCH


@pytest.mark.parametrize("disposition", ["RISK_DENIED", "RISK_ESCALATED", "NOT_EVALUATED"])
def test_non_allow_family_dispositions_are_refused(projection, decision, disposition):
    """A-19: only the ALLOW family is a candidate input; denial and escalation are not."""

    from risk_authority.integrations import SubjectRiskDisposition

    forged = SubjectRiskDecision.__new__(SubjectRiskDecision)
    for f, v in vars(decision).items():
        object.__setattr__(forged, f, v)
    object.__setattr__(forged, "disposition", SubjectRiskDisposition(disposition))
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, forged)
    assert exc.value.reason is Reason.DECISION_NOT_ALLOW_FAMILY


# ======================================================================================
# Producer attestation
# ======================================================================================


def test_missing_producer_attestation_is_refused(projection, decision, target_scope, policy_binding):
    """A-20: absence of the attestation fails candidate construction."""

    with pytest.raises(ExactTypeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=None,
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )
    assert exc.value.reason is Reason.MISSING_PRODUCER_ATTESTATION


def test_malformed_attestation_signature_is_refused(projection):
    """A-21: a non-string / empty signature is refused at construction."""

    with pytest.raises(CandidateConstructionError):
        ProducerAttestationEvidence(
            producer_id=PRODUCER_ID, producer_key_id="k1", signature_algorithm="ed25519",
            signature="", recommendation_id=RECOMMENDATION_ID,
            recommendation_digest=projection.recommendation_digest,
            signing_purpose=PRODUCER_SIGNING_PURPOSE,
            signing_payload_digest="sha256:" + "0" * 64,
            issued_at=projection.asserted_at,
        )


def test_unsupported_signing_purpose_is_refused(projection):
    """A-22: an attestation naming a policy-signing purpose is refused."""

    with pytest.raises(ProducerAttestationError) as exc:
        build_attestation(
            recommendation_digest=projection.recommendation_digest,
            signing_purpose="ugence.policy_authority.policy_signing",
        )
    assert exc.value.reason is Reason.UNSUPPORTED_SIGNING_PURPOSE


def test_attestation_signing_payload_digest_must_match(projection):
    """A-23: a signing_payload_digest that is not the digest of the payload is refused."""

    good = build_attestation(recommendation_digest=projection.recommendation_digest)
    with pytest.raises(ProducerAttestationError) as exc:
        dataclasses.replace(good, signing_payload_digest="sha256:" + "c" * 64)
    assert exc.value.reason is Reason.PRODUCER_ATTESTATION_CONTENT_MISMATCH


def test_unsupported_signature_algorithm_is_refused(projection):
    """A-24: an unrecognised algorithm identifier is refused structurally."""

    with pytest.raises(ProducerAttestationError):
        ProducerAttestationEvidence(
            producer_id=PRODUCER_ID, producer_key_id="k1", signature_algorithm="md5",
            signature="00", recommendation_id=RECOMMENDATION_ID,
            recommendation_digest=projection.recommendation_digest,
            signing_purpose=PRODUCER_SIGNING_PURPOSE,
            signing_payload_digest="sha256:" + "0" * 64,
            issued_at=projection.asserted_at,
        )


def test_attestation_from_dict_refuses_a_forged_trust_state(projection):
    """A-25: a caller cannot deserialize an attestation into a verified state."""

    good = build_attestation(recommendation_digest=projection.recommendation_digest)
    payload = {
        k: v for k, v in good.to_canonical_dict().items() if k != "trust_state"
    }
    payload["trust_state"] = "TRUST_VERIFIED"
    with pytest.raises(CandidateConstructionError) as exc:
        ProducerAttestationEvidence.from_dict(payload)
    assert exc.value.reason is Reason.FORGED_TRUST_STATE


def test_trust_state_cannot_be_overwritten(candidate):
    """A-26: object.__setattr__ cannot forge the trust state — it is a property."""

    for artifact in (candidate.producer_attestation, candidate.policy_binding, candidate):
        with pytest.raises(AttributeError):
            object.__setattr__(artifact, "trust_state", "TRUST_VERIFIED")


# ======================================================================================
# Policy / target binding
# ======================================================================================


def test_missing_policy_binding_is_refused(projection, decision, attestation, target_scope):
    """A-27: absence of the policy binding fails candidate construction."""

    with pytest.raises(ExactTypeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=None,
            policy_coordinate_binding=build_policy_coordinate_binding(target_scope),
            target_scope=target_scope,
        )
    assert exc.value.reason is Reason.MISSING_POLICY_TARGET_BINDING


def test_malformed_policy_binding_digest_is_refused(target_scope):
    """A-28: a binding_digest that is not the digest of the binding payload is refused."""

    good = build_policy_binding(target_scope)
    with pytest.raises(PolicyTargetBindingError) as exc:
        dataclasses.replace(good, binding_digest="sha256:" + "d" * 64)
    assert exc.value.reason is Reason.MALFORMED_POLICY_TARGET_BINDING


def test_policy_binding_from_dict_refuses_a_forged_trust_state(target_scope):
    """A-29: a caller cannot deserialize a policy binding into a verified state."""

    good = build_policy_binding(target_scope)
    payload = {k: v for k, v in good.to_canonical_dict().items() if k != "trust_state"}
    payload["verified"] = True
    with pytest.raises(CandidateConstructionError) as exc:
        PolicyTargetBindingReference.from_dict(payload)
    assert exc.value.reason is Reason.FORGED_TRUST_STATE


# ======================================================================================
# Type confusion and fabrication
# ======================================================================================


@pytest.mark.parametrize("which", ["projection", "decision"])
def test_subclass_sources_are_refused(projection, decision, which):
    """A-30: a subclass of a Phase 4 source is refused; isinstance is not the rule."""

    if which == "projection":
        Sub = type("SubProjection", (type(projection),), {})
        bad = Sub(**{f: getattr(projection, f) for f in projection.__dataclass_fields__})
        args = (bad, decision)
    else:
        Sub = type("SubDecision", (SubjectRiskDecision,), {})
        bad = Sub(**{f: getattr(decision, f) for f in decision.__dataclass_fields__})
        args = (projection, bad)
    with pytest.raises(ExactTypeError) as exc:
        reconcile_phase4(*args)
    assert exc.value.reason is Reason.UNSUPPORTED_EXACT_TYPE


def test_subclass_controlled_property_cannot_divert_a_read(projection, decision):
    """A-31: a source whose tenant_id changes between reads is refused at the type gate."""

    reads = []

    class Shifting(type(projection)):
        @property
        def tenant_id(self):  # pragma: no cover - refused before it is ever read
            reads.append(1)
            return "tenant-1" if len(reads) == 1 else "tenant-evil"

    bad = Shifting.__new__(Shifting)
    for f in projection.__dataclass_fields__:
        if f != "tenant_id":
            object.__setattr__(bad, f, getattr(projection, f))
    with pytest.raises(ExactTypeError):
        reconcile_phase4(bad, decision)
    assert reads == [], "the diverting property was read despite the exact-type gate"


def test_object_new_fabricated_sources_are_refused(projection, decision):
    """A-32: object.__new__ fabrication skips __post_init__ but not the exact-type gate."""

    Sub = type("FakeProjection", (), {})
    fake = Sub.__new__(Sub)
    for f in projection.__dataclass_fields__:
        object.__setattr__(fake, f, getattr(projection, f))
    with pytest.raises(ExactTypeError):
        reconcile_phase4(fake, decision)


def test_object_new_fabricated_candidate_has_no_valid_digest(candidate):
    """A-33: a fabricated candidate cannot produce a matching candidate digest."""

    fake = CapacityAuthorizationCandidate.__new__(CapacityAuthorizationCandidate)
    for f in candidate.__dataclass_fields__:
        object.__setattr__(fake, f, getattr(candidate, f))
    object.__setattr__(fake, "magnitude_after", candidate.magnitude_after + 50)
    assert fake.digest() != fake.candidate_digest


def test_duck_typed_lookalikes_are_refused(projection, decision, target_scope, policy_binding):
    """A-34: an object that merely has the right attributes is not an attestation."""

    class QuacksLikeAttestation:
        recommendation_id = RECOMMENDATION_ID
        recommendation_digest = projection.recommendation_digest
        signing_payload_digest = "sha256:" + "0" * 64
        producer_id = PRODUCER_ID
        producer_key_id = "k1"
        issued_at = projection.asserted_at
        trust_state = "TRUST_VERIFIED"

    with pytest.raises(ExactTypeError) as exc:
        build_capacity_authorization_candidate(
            projection=projection, decision=decision,
            producer_attestation=QuacksLikeAttestation(),
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )
    assert exc.value.reason is Reason.UNSUPPORTED_EXACT_TYPE


@pytest.mark.parametrize(
    "cls,payload_extra",
    [
        (ExecutionTargetScope, {"authorized": True}),
        (ExecutionTargetScope, {"executable": True}),
        (PolicyTargetBindingReference, {"envelope_issued": True}),
        (ProducerAttestationEvidence, {"credential_issued": True}),
    ],
)
def test_fabricated_authority_fields_are_refused(candidate, cls, payload_extra):
    """A-35: an unknown authority-shaped field is refused, never ignored."""

    source = {
        ExecutionTargetScope: candidate.target_scope,
        PolicyTargetBindingReference: candidate.policy_binding,
        ProducerAttestationEvidence: candidate.producer_attestation,
    }[cls]
    payload = {k: v for k, v in source.to_canonical_dict().items() if k != "trust_state"}
    payload.pop("requested_delta", None)
    payload.update(payload_extra)
    with pytest.raises(CandidateConstructionError):
        cls.from_dict(payload)


def test_unknown_canonical_fields_are_refused(candidate):
    """A-36: an unrecognised field is a rejection, not a silently ignored extra."""

    payload = {
        k: v for k, v in candidate.target_scope.to_canonical_dict().items()
        if k != "requested_delta"
    }
    payload["surprise"] = "value"
    with pytest.raises(CandidateConstructionError) as exc:
        ExecutionTargetScope.from_dict(payload)
    assert exc.value.reason is Reason.UNKNOWN_FIELD


def test_missing_required_fields_are_refused(candidate):
    """A-37: a missing required field is a rejection, not a defaulted value."""

    payload = {
        k: v for k, v in candidate.target_scope.to_canonical_dict().items()
        if k not in {"requested_delta", "account_id"}
    }
    with pytest.raises(CandidateConstructionError) as exc:
        ExecutionTargetScope.from_dict(payload)
    assert exc.value.reason is Reason.MISSING_ACCOUNT_BINDING


def test_non_nfc_identifiers_are_refused(projection):
    """A-38: a non-NFC identifier is refused rather than normalized."""

    with pytest.raises(CandidateConstructionError) as exc:
        build_target_scope(projection, account_id="acct-café")
    assert exc.value.reason is Reason.NON_CANONICAL_IDENTIFIER


def test_bare_hex_digests_are_refused(target_scope):
    """A-39: a bare-hex (unprefixed) digest is not a canonical digest."""

    good = build_policy_binding(target_scope)
    with pytest.raises(CandidateConstructionError):
        dataclasses.replace(good, policy_artifact_digest="a" * 64)


def test_uppercase_hex_digests_are_refused(target_scope):
    """A-40: uppercase hex is refused — two spellings of one digest would break equality."""

    good = build_policy_binding(target_scope)
    with pytest.raises(CandidateConstructionError):
        dataclasses.replace(good, policy_artifact_digest="sha256:" + "A" * 64)


# ======================================================================================
# Post-construction integrity
# ======================================================================================


def test_candidate_is_immutable(candidate):
    """A-41: the candidate is frozen; ordinary mutation is refused."""

    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.magnitude_after = 99  # type: ignore[misc]


def test_post_construction_mutation_invalidates_the_digest(candidate):
    """A-42: forcing a field past the freeze makes the carried digest stop matching."""

    tampered = copy.copy(candidate)
    object.__setattr__(tampered, "magnitude_after", candidate.magnitude_after + 10)
    assert tampered.digest() != tampered.candidate_digest


def test_deepcopy_round_trip_preserves_the_digest(candidate):
    """A-43: a copy is the same candidate; copying grants nothing new."""

    assert copy.deepcopy(candidate).digest() == candidate.candidate_digest
    assert copy.deepcopy(candidate).grants_authority is False


def test_candidate_cannot_be_constructed_with_a_wrong_digest(candidate):
    """A-44: presenting a hand-picked candidate_digest is refused at construction."""

    fields = {f: getattr(candidate, f) for f in candidate.__dataclass_fields__}
    fields["candidate_digest"] = "sha256:" + "e" * 64
    with pytest.raises(CandidateConstructionError) as exc:
        CapacityAuthorizationCandidate(**fields)
    assert exc.value.reason is Reason.CANDIDATE_DIGEST_FAILURE


def test_swapping_a_binding_after_the_fact_breaks_the_digest(candidate, projection):
    """A-45: substituting the carried scope invalidates the candidate digest."""

    other = build_target_scope(projection, account_id="acct-999999999999")
    tampered = copy.copy(candidate)
    object.__setattr__(tampered, "target_scope", other)
    assert tampered.digest() != tampered.candidate_digest


# ======================================================================================
# A-46 — the policy binding's ceilings are the only bound the request is checked against
# ======================================================================================


class _LyingCeiling(int):
    """An ``int`` that is equal to everything and never less than anything.

    Built by hand, never through ``to_canonical_obj``: a control that shares its
    subject's representation would measure the representation, not the guard.
    """

    def __eq__(self, other):  # noqa: D105 - the lie is the point
        return True

    def __ne__(self, other):  # noqa: D105 - defeats ``b_max != s_max``
        return False

    def __hash__(self):  # noqa: D105 - __eq__ overridden, so restate int's hash
        return int.__hash__(self)

    def __lt__(self, other):  # noqa: D105 - reflected form of ``other > self``
        return False


def test_a_lying_int_subclass_cannot_carry_a_policy_ceiling(projection, decision, attestation):
    """A-46: the signed policy ceiling is admitted by exact type, never by isinstance.

    Both comparisons the builder makes against this field consult the *carried* object:
    ``candidate.py:620`` with ``!=`` and ``candidate.py:678`` with ``>``. Python gives a
    subclass operand priority in ``>`` through its reflected ``__lt__``, so an ``int``
    subclass lying in both would admit a magnitude the signed binding caps far lower —
    and no digest can see it, because the canonical payload renders the subclass to the
    honest number.
    """

    # A scope permissive enough that only the *policy* ceiling stands in the way.
    scope = build_target_scope(projection, max_magnitude=10_000, max_delta=10_000)
    assert scope.requested_magnitude > 5, "the ceiling under test must actually bind"

    # Control: the honest ceiling is refused by the bounds-agreement guard, so the
    # attack below is not passing through an already-open door.
    honest = build_policy_binding(scope, max_magnitude=5, max_delta=10_000)
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=attestation,
            policy_binding=honest,
            policy_coordinate_binding=build_policy_coordinate_binding(scope),
            target_scope=scope,
        )
    assert exc.value.reason is Reason.POLICY_TARGET_CONTENT_MISMATCH

    # No digest can distinguish the lie: the canonical payload renders it to ``5``.
    assert honest.binding_payload()["max_permitted_magnitude"] == 5
    assert type(honest.max_permitted_magnitude) is int

    # The attack: the same signed ceiling, carried as the lying subclass. It must not
    # reach the builder at all — the binding itself refuses to exist.
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_policy_binding(scope, max_magnitude=_LyingCeiling(5), max_delta=10_000)
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "max_permitted_magnitude" in str(exc.value)

    # The same exactness on the delta ceiling.
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_policy_binding(scope, max_magnitude=10_000, max_delta=_LyingCeiling(5))
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "max_permitted_delta" in str(exc.value)


# ======================================================================================
# A-47 … A-51 — the string surface: every identity guard decides with ``!=``
# ======================================================================================


class _LyingText(str):
    """A ``str`` that is never unequal to anything.

    ``__eq__`` is left honest on purpose: an over-eager ``__eq__`` trips unrelated
    emptiness and normalization checks, and the guards under test all decide with ``!=``.
    Built by hand, never through ``to_canonical_obj`` — the canonical rendering of this
    object is byte-identical to the honest string, which is precisely why no digest can
    see it and why the admitted *type* is the only place the difference survives.
    """

    def __ne__(self, other):  # noqa: D105 - the lie is the point
        return False

    def __hash__(self):  # noqa: D105 - __ne__ overridden, so restate str's hash
        return str.__hash__(self)


def test_a_lying_string_cannot_relocate_the_action(projection):
    """A-47: the scope's locus fields are admitted by exact type (candidate.py:601-607)."""

    honest = build_target_scope(projection, region="ap-south-1")
    assert honest.region == "ap-south-1"

    with pytest.raises(CandidateConstructionError) as exc:
        build_target_scope(projection, region=_LyingText("ap-south-1"))
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "region must be a string" in str(exc.value)


def test_a_lying_scope_digest_cannot_rebind_a_policy_binding(
    projection, decision, attestation
):
    """A-48: a binding cannot be made to reference a scope it was not issued for."""

    scope_a = build_target_scope(projection)
    scope_b = build_target_scope(projection, account_id="acct-999999999999")

    # Control: the honest binding for scope B is refused against scope A.
    with pytest.raises(PolicyTargetBindingError) as exc:
        build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=attestation,
            policy_binding=build_policy_binding(scope_b),
            policy_coordinate_binding=build_policy_coordinate_binding(scope_a),
            target_scope=scope_a,
        )
    assert exc.value.reason is Reason.POLICY_TARGET_CONTENT_MISMATCH

    # The attack cannot even be assembled: the digest is admitted by exact type.
    with pytest.raises(CandidateConstructionError) as exc:
        build_policy_binding(scope_b, target_scope_digest=_LyingText(scope_b.digest()))
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD


def test_a_lying_policy_id_cannot_carry_two_policy_identities(projection):
    """A-49: the candidate's two policy references are compared by exact-typed strings."""

    scope = build_target_scope(projection)
    with pytest.raises(CandidateConstructionError) as exc:
        build_policy_coordinate_binding(scope, policy_id=_LyingText("someone.else"))
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD


def test_a_lying_tenant_cannot_bound_another_tenants_action(projection):
    """A-50: a TENANT-scoped policy's tenant is admitted by exact type (R-9)."""

    scope = build_target_scope(projection)
    with pytest.raises(CandidateConstructionError) as exc:
        build_policy_coordinate_binding(
            scope, policy_scope="TENANT", policy_tenant_id=_LyingText("tenant-999")
        )
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD


def test_a_lying_snapshot_tenant_is_refused_before_it_is_compared(projection, decision):
    """A-51: the decision snapshot's tenant is admitted before reconciliation compares it.

    The snapshot is a plain mapping the caller supplies; nothing admitted its values on
    the way to ``reconciliation.py``'s ``!=``, and its digest renders a subclass to the
    same bytes. Closing the string surface alone did **not** close this one — the value
    had to be put through an admission before the comparison.
    """

    from ugence_cloud_scaling_authorization_contracts.canonical import digest_of_snapshot

    def _with_tenant(value):
        snapshot = dict(decision.decision_snapshot)
        snapshot["tenant_id"] = value
        return dataclasses.replace(
            decision,
            decision_snapshot=snapshot,
            decision_digest=digest_of_snapshot(snapshot),
        )

    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, _with_tenant("tenant-999"))
    assert exc.value.reason is Reason.TENANT_MISMATCH

    with pytest.raises(CandidateConstructionError) as exc:
        reconcile_phase4(projection, _with_tenant(_LyingText("tenant-999")))
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "decision_snapshot.tenant_id" in str(exc.value)


# ======================================================================================
# A-52 / A-53 — Phase 5A exact-type hygiene: the surfaces #1469 deliberately left open
# ======================================================================================


def test_a_lying_decision_tenant_or_key_is_refused_before_reconciliation_compares_it(
    projection, decision
):
    """A-52: the decision's own tenant_id and idempotency_key are admitted first.

    Neither could alter the emitted tenant — that is re-derived from the projection — but
    each could carry a foreign decision past the binding its guard exists to enforce.
    Both attack values are hand-built, never through ``to_canonical_obj``.
    """

    other_key = "sha256:" + "b" * 64

    # Controls: honest mismatches keep the typed refusals they have always had.
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, dataclasses.replace(decision, tenant_id="tenant-999"))
    assert exc.value.reason is Reason.TENANT_MISMATCH

    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(
            projection, dataclasses.replace(decision, idempotency_key=other_key)
        )
    assert exc.value.reason is Reason.IDEMPOTENCY_KEY_MISMATCH

    # The lies are refused at admission, before either comparison runs.
    with pytest.raises(CandidateConstructionError) as exc:
        reconcile_phase4(
            projection, dataclasses.replace(decision, tenant_id=_LyingText("tenant-999"))
        )
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "decision.tenant_id" in str(exc.value)

    with pytest.raises(CandidateConstructionError) as exc:
        reconcile_phase4(
            projection,
            dataclasses.replace(decision, idempotency_key=_LyingText(other_key)),
        )
    assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
    assert "decision.idempotency_key" in str(exc.value)

    # The missing-key diagnosis is not taken away by the new admission.
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(projection, dataclasses.replace(decision, idempotency_key=""))
    assert exc.value.reason is Reason.IDEMPOTENCY_KEY_MISMATCH

    # The two remaining binding digests, on the same footing. `evaluation_digest` is
    # deliberately absent from this list: it exists on `SubjectRiskDecision` but Phase 5A
    # reads it nowhere, so there is no comparison for a lie to reach. Recorded rather than
    # given a guard nothing would exercise.
    other_digest = "sha256:" + "c" * 64
    for field, honest_reason in (
        ("request_digest", Reason.REQUEST_DIGEST_MISMATCH),
        ("subject_digest", Reason.SUBJECT_MISMATCH),
    ):
        with pytest.raises(ReconciliationError) as exc:
            reconcile_phase4(
                projection, dataclasses.replace(decision, **{field: other_digest})
            )
        assert exc.value.reason is honest_reason, f"{field} lost its typed refusal"

        with pytest.raises(CandidateConstructionError) as exc:
            reconcile_phase4(
                projection,
                dataclasses.replace(decision, **{field: _LyingText(other_digest)}),
            )
        assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
        assert f"decision.{field}" in str(exc.value)


def test_a_lying_schema_identifier_cannot_claim_another_contract(projection, candidate):
    """A-53: every public Phase 5A artifact admits its schema identifier by exact type."""

    wrong = "cloud-scaling-not-this-schema-9"
    scope = build_target_scope(projection)

    # Controls: an honest wrong identifier is refused by each artifact's own gate.
    with pytest.raises(TargetScopeError):
        dataclasses.replace(scope, schema_version=wrong)
    with pytest.raises(PolicyTargetBindingError):
        dataclasses.replace(build_policy_binding(scope), schema_version=wrong)

    # The lie is refused at admission, in every artifact that carries one.
    for build in (
        lambda sv: dataclasses.replace(scope, schema_version=sv),
        lambda sv: dataclasses.replace(build_policy_binding(scope), schema_version=sv),
        lambda sv: dataclasses.replace(
            build_policy_coordinate_binding(scope), schema_version=sv
        ),
        lambda sv: dataclasses.replace(
            build_attestation(recommendation_digest=projection.recommendation_digest),
            schema_version=sv,
        ),
        lambda sv: dataclasses.replace(candidate, schema_version=sv),
    ):
        with pytest.raises(CandidateConstructionError) as exc:
            build(_LyingText(wrong))
        assert exc.value.reason is Reason.MALFORMED_CANONICAL_FIELD
        assert "schema_version must be a string" in str(exc.value)


@pytest.mark.parametrize(
    "label, value, reason",
    [
        ("an int", 12345, Reason.MALFORMED_CANONICAL_FIELD),
        ("bytes", b"acme-tenant", Reason.MALFORMED_CANONICAL_FIELD),
        ("an embedded newline", "acme\ntenant", Reason.NON_CANONICAL_IDENTIFIER),
        ("an embedded tab", "acme\ttenant", Reason.NON_CANONICAL_IDENTIFIER),
        ("the empty string", "", Reason.MALFORMED_CANONICAL_FIELD),
    ],
)
def test_a_malformed_projection_tenant_is_not_reported_as_a_mismatch(
    projection, decision, label, value, reason
):
    """A-54: both operands of the tenant comparison are admitted, not just the decision's.

    Admitting only the decision side left this asymmetry: a projection tenant that
    ``require_canonical_identifier`` itself refuses still passed the Phase 4C constructor,
    reached ``p_tenant != d_tenant``, and was answered with ``TENANT_MISMATCH`` — a
    semantic diagnosis of a malformed input, identical to what an honest foreign tenant
    gets. Reached through public constructors only.
    """

    forged = dataclasses.replace(projection, tenant_id=value)
    with pytest.raises(CandidateConstructionError) as exc:
        reconcile_phase4(forged, decision)
    assert exc.value.reason is reason, f"{label} did not receive a canonical refusal"
    assert "projection.tenant_id" in str(exc.value)


def test_an_honest_projection_tenant_mismatch_keeps_its_semantic_reason(
    projection, decision
):
    """A-54's other direction: well-formed but different is still ``TENANT_MISMATCH``."""

    forged = dataclasses.replace(projection, tenant_id="tenant-999")
    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(forged, decision)
    assert exc.value.reason is Reason.TENANT_MISMATCH

    # And a matching canonical tenant continues normally.
    facts = reconcile_phase4(projection, decision)
    assert facts.tenant_id == projection.tenant_id
