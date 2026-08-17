"""Stage 1: the exact policy must resolve through the configured authority.

Every failure here is fail-closed and **dominant**: no gate verifier and no
condition verifier is consulted, ``evaluate_readiness`` never runs, no readiness
classification exists, and the outcome discloses no usable policy material.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from _orchestration_fixtures import (
    ARBITRARY_DIGEST,
    CONDITIONAL,
    MANDATORY,
    PILOT,
    PROD,
    T_AFTER,
    T_BEFORE,
    T_FROM,
    T_MID,
    T_TO,
    TENANT,
    RecordingResolver,
    StubConditionVerifier,
    StubGateVerifier,
    condition,
    context,
    forged_record,
    gate,
    gate_result,
    issued_authority,
    issued_resolver,
    make_authority,
    readiness_policy,
    request,
)
from ugence_policy_authority.api import (
    PolicyResolution,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    uvi_coordinate,
)
from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
    ReadinessPolicy,
)

from ugence_agent_value_readiness.api import (
    GateStatus,
    ReadinessAssessmentStatus,
    ReadinessTrustGapCode,
    assess_readiness,
)

G = ReadinessTrustGapCode
POLICY = readiness_policy([gate("m1", MANDATORY)])


def _assess(req, **kwargs):
    kwargs.setdefault("gate_verifier", StubGateVerifier())
    kwargs.setdefault("condition_verifier", StubConditionVerifier())
    return assess_readiness(req, **kwargs)


def _gaps(outcome) -> set:
    return set(outcome.trust_gap_codes)


# --------------------------------------------------------------------------- #
# The resolved happy path
# --------------------------------------------------------------------------- #
def test_a_resolved_policy_produces_an_evaluated_outcome():
    req = request(policy=POLICY, gate_results=[gate_result(POLICY, "m1", GateStatus.PASS)])
    outcome = _assess(req, policy_resolver=issued_resolver(POLICY))

    assert outcome.status is ReadinessAssessmentStatus.EVALUATED
    assert outcome.trust_gap_codes == ()
    assert outcome.trace.policy_resolution_status is PolicyResolutionStatus.RESOLVED
    assert outcome.trace.policy_resolution_reason is PolicyResolutionReason.RESOLVED
    # A stable reference to the resolved issuance record, not the record itself.
    assert outcome.trace.issuance_record_ref == "rec-1"
    assert outcome.trace.resolved_policy_digest == POLICY.canonical_digest()


def test_the_resolver_is_asked_for_the_exact_reference_at_the_exact_instant():
    recorder = RecordingResolver(inner=issued_resolver(POLICY))
    req = request(policy=POLICY, gate_results=[gate_result(POLICY, "m1", GateStatus.PASS)])
    _assess(req, policy_resolver=recorder)

    (reference, tenant, as_of), = recorder.calls
    assert reference == POLICY.reference
    assert tenant == POLICY.reference.tenant_id
    assert as_of == T_MID


# --------------------------------------------------------------------------- #
# Deny by default
# --------------------------------------------------------------------------- #
def test_no_resolver_configured_denies():
    outcome = _assess(request(policy=POLICY))

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLVER_NOT_CONFIGURED.value in outcome.trust_gap_codes
    assert outcome.classification is None
    assert outcome.evaluation is None


def test_a_duck_typed_resolver_is_refused_rather_than_probed():
    class NotAResolver:
        pass

    outcome = _assess(request(policy=POLICY), policy_resolver=NotAResolver())
    assert _gaps(outcome) == {G.POLICY_RESOLVER_MALFORMED_RESULT.value}


def test_a_resolver_that_raises_fails_closed():
    outcome = _assess(request(policy=POLICY), policy_resolver=RecordingResolver(raises=True))
    assert _gaps(outcome) == {G.POLICY_RESOLVER_ERROR.value}


def test_a_resolver_returning_a_foreign_object_fails_closed():
    outcome = _assess(
        request(policy=POLICY), policy_resolver=RecordingResolver(returns_foreign_object=True)
    )
    assert _gaps(outcome) == {G.POLICY_RESOLVER_MALFORMED_RESULT.value}


# --------------------------------------------------------------------------- #
# The authority's own refusals
# --------------------------------------------------------------------------- #
def test_a_policy_that_was_never_issued_does_not_resolve():
    unissued = readiness_policy([gate("m1", MANDATORY)], policy_id="never-issued")
    resolver = make_authority().resolver()
    outcome = _assess(request(policy=unissued), policy_resolver=resolver)

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert _gaps(outcome) == {G.POLICY_RESOLUTION_UNRESOLVED.value}
    assert outcome.trace.policy_resolution_reason is PolicyResolutionReason.NOT_FOUND


def test_a_digest_mismatched_reference_does_not_resolve():
    """A reference whose content digest is not the issued one resolves nothing."""

    forged = PolicyReference(
        policy_id=POLICY.reference.policy_id,
        policy_family=PolicyFamily.READINESS,
        version=POLICY.reference.version,
        content_digest=ARBITRARY_DIGEST,
        scope=POLICY.reference.scope,
        tenant_id=POLICY.reference.tenant_id,
    )
    req = request(policy=POLICY, policy_ref=forged, ctx=context(POLICY))
    outcome = _assess(req, policy_resolver=issued_resolver(POLICY))

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_UNRESOLVED.value in outcome.trust_gap_codes


def test_a_tenant_scoped_policy_belonging_to_another_tenant_is_refused():
    """A TENANT-scoped readiness policy must belong to the assessed tenant.

    The merged ``AssessmentContext`` already refuses to *bind* another tenant's
    reference, so the only way to present one is through a context that binds no
    readiness policy at all — and the orchestrator refuses on both counts.
    """

    foreign = readiness_policy(
        [gate("m1", MANDATORY)],
        policy_id="foreign-tenant-policy",
        scope=PolicyScope.TENANT,
        tenant_id="tenant-b",
    )
    req = request(policy=foreign, tenant=TENANT, ctx=context(None, tenant=TENANT))
    outcome = _assess(req, policy_resolver=issued_resolver(foreign))

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_TENANT_MISMATCH.value in outcome.trust_gap_codes
    assert G.POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH.value in outcome.trust_gap_codes


def test_a_tenant_scoped_policy_owned_by_the_assessed_tenant_resolves():
    owned = readiness_policy(
        [gate("m1", MANDATORY)],
        policy_id="owned-tenant-policy",
        scope=PolicyScope.TENANT,
        tenant_id="tenant-b",
    )
    req = request(
        policy=owned,
        tenant="tenant-b",
        ctx=context(owned, tenant="tenant-b"),
        gate_results=[gate_result(owned, "m1", GateStatus.PASS)],
    )
    outcome = _assess(req, policy_resolver=issued_resolver(owned))
    assert outcome.status is ReadinessAssessmentStatus.EVALUATED


def test_a_revoked_policy_does_not_resolve():
    from ugence_policy_authority.api import (
        Ed25519PolicySigner,
        KeyEntitlement,
        PolicyKeyRing,
        PolicyRevocationReasonCode,
        SigningKey,
        revoke_policy,
    )

    policy = readiness_policy([gate("m1", MANDATORY)], policy_id="to-be-revoked")
    authority = make_authority()
    authority.issue(policy)
    revoker = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.revocation",
        key_id="revocation-key-1",
        signing_key=SigningKey.from_seed(bytes([7]) * 32),
    )
    authority.key_ring = PolicyKeyRing(
        [
            authority.signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,)),
            revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,)),
        ]
    )
    revoke_policy(
        reference=policy.reference,
        revocation_id="rev-1",
        reason_code=PolicyRevocationReasonCode.CONTENT_DEFECT,
        signer=revoker,
        signature_verifier=authority.key_ring,
        registry=authority.registry,
        adapters=authority.adapters,
        revoked_at=T_BEFORE,
    )

    outcome = _assess(request(policy=policy), policy_resolver=authority.resolver())
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_UNRESOLVED.value in outcome.trust_gap_codes
    assert outcome.trace.policy_resolution_reason is PolicyResolutionReason.REVOKED


def test_an_unstructured_supersession_reference_cannot_even_be_issued():
    """v0.1 refuses such an artifact at issuance, so readiness never sees it."""

    from ugence_policy_authority.api import (
        UnsupportedSupersessionError,
        UviPolicyFamilyAdapter,
    )
    from ugence_uvi_policy_contracts.api import PolicyArtifactMetadata

    def _meta(digest):
        return PolicyArtifactMetadata(
            policy_id="supersedes-1",
            policy_family=PolicyFamily.READINESS,
            version="1.0.0",
            content_digest=digest,
            lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE,
            effective_from=T_FROM,
            effective_to=T_TO,
            supersedes_ref="an-earlier-policy",
        )

    draft = ReadinessPolicy(metadata=_meta("0" * 64), gates=(gate("m1", MANDATORY),))
    policy = ReadinessPolicy(
        metadata=_meta(UviPolicyFamilyAdapter().describe(draft).body_digest()),
        gates=(gate("m1", MANDATORY),),
    )

    authority = make_authority()
    with pytest.raises(UnsupportedSupersessionError):
        authority.issue(policy)

    # Nothing was registered, so readiness resolves nothing either.
    outcome = _assess(request(policy=policy), policy_resolver=authority.resolver())
    assert _gaps(outcome) == {G.POLICY_RESOLUTION_UNRESOLVED.value}


# --------------------------------------------------------------------------- #
# The orchestrator's own independent rechecks
# --------------------------------------------------------------------------- #
def _forged(policy, *, as_of=T_MID, historical=False, artifact=None, record=None):
    """A hand-assembled RESOLVED resolution — construction is not authenticity."""

    authority = issued_authority(policy)
    return PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=uvi_coordinate(policy.reference),
        as_of=as_of,
        policy=artifact if artifact is not None else policy,
        record=record if record is not None else authority.issued[0],
        historical=historical,
    )


def test_a_forged_resolution_of_a_different_artifact_is_rejected():
    other = readiness_policy([gate("m1", MANDATORY)], policy_id="a-different-policy")
    issued_authority(other)
    resolution = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=uvi_coordinate(POLICY.reference),
        as_of=T_MID,
        policy=other,
        record=issued_authority(other).issued[0],
    )
    outcome = _assess(
        request(policy=POLICY), policy_resolver=RecordingResolver(answer=resolution)
    )
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert G.POLICY_RESOLUTION_REFERENCE_MISMATCH.value in outcome.trust_gap_codes


def test_a_resolution_for_a_different_instant_is_rejected():
    outcome = _assess(
        request(policy=POLICY),
        policy_resolver=RecordingResolver(answer=_forged(POLICY, as_of=T_MID + timedelta(days=1))),
    )
    assert G.POLICY_RESOLUTION_AS_OF_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED


def test_a_historical_resolution_is_never_accepted():
    outcome = _assess(
        request(policy=POLICY),
        policy_resolver=RecordingResolver(answer=_forged(POLICY, historical=True)),
    )
    assert G.POLICY_RESOLUTION_HISTORICAL_NOT_ACCEPTED.value in outcome.trust_gap_codes
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED


def test_a_non_readiness_artifact_is_rejected():
    from _orchestration_fixtures import domain_policy

    wrong_family = domain_policy()
    resolution = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=uvi_coordinate(POLICY.reference),
        as_of=T_MID,
        policy=wrong_family,
        record=forged_record(wrong_family),
    )
    outcome = _assess(
        request(policy=POLICY), policy_resolver=RecordingResolver(answer=resolution)
    )
    assert G.POLICY_RESOLUTION_ARTIFACT_NOT_A_READINESS_POLICY.value in outcome.trust_gap_codes


def test_a_context_that_does_not_bind_the_policy_is_rejected():
    unbound = context(None)
    outcome = _assess(
        request(policy=POLICY, ctx=unbound), policy_resolver=issued_resolver(POLICY)
    )
    assert G.POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH.value in outcome.trust_gap_codes
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED


def test_a_context_bound_to_another_readiness_policy_is_rejected():
    other = readiness_policy([gate("m1", MANDATORY)], policy_id="context-bound-elsewhere")
    outcome = _assess(
        request(policy=POLICY, ctx=context(other)), policy_resolver=issued_resolver(POLICY)
    )
    assert G.POLICY_RESOLUTION_CONTEXT_BINDING_MISMATCH.value in outcome.trust_gap_codes


def test_a_target_the_policy_does_not_govern_is_rejected():
    pilot_only = readiness_policy(
        [gate("m1", MANDATORY, applicability=(PILOT,))],
        policy_id="pilot-only",
        targets=(PILOT,),
    )
    outcome = _assess(
        request(policy=pilot_only, target=PROD), policy_resolver=issued_resolver(pilot_only)
    )
    assert G.POLICY_RESOLUTION_TARGET_NOT_GOVERNED.value in outcome.trust_gap_codes
    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED


def test_defence_in_depth_rejects_an_inactive_artifact_a_lax_resolver_returned():
    draft = readiness_policy(
        [gate("m1", MANDATORY)],
        policy_id="draft-policy",
        lifecycle_state=PolicyLifecycleState.DRAFT,
    )
    resolution = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=uvi_coordinate(draft.reference),
        as_of=T_MID,
        policy=draft,
        record=forged_record(draft),
    )
    outcome = _assess(
        request(policy=draft), policy_resolver=RecordingResolver(answer=resolution)
    )
    assert G.POLICY_ARTIFACT_NOT_APPROVED_ACTIVE.value in outcome.trust_gap_codes


def test_defence_in_depth_rejects_an_out_of_period_artifact():
    resolution = PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=uvi_coordinate(POLICY.reference),
        as_of=T_AFTER,
        policy=POLICY,
        record=issued_authority(POLICY).issued[0],
    )
    outcome = _assess(
        request(policy=POLICY, evaluation_time=T_AFTER),
        policy_resolver=RecordingResolver(answer=resolution),
    )
    assert G.POLICY_ARTIFACT_NOT_EFFECTIVE_AT_EVALUATION_TIME.value in outcome.trust_gap_codes


# --------------------------------------------------------------------------- #
# Dominance and disclosure
# --------------------------------------------------------------------------- #
def test_policy_failure_prevents_every_later_call():
    policy = readiness_policy(
        [gate("m1", MANDATORY), gate("c1", CONDITIONAL, compensable=True)],
        policy_id="dominance",
    )
    gate_verifier = StubGateVerifier()
    condition_verifier = StubConditionVerifier()
    req = request(
        policy=policy,
        gate_results=[gate_result(policy, "m1", GateStatus.PASS)],
        conditions=[condition("cond-1", "c1")],
    )

    outcome = assess_readiness(
        req,
        policy_resolver=None,
        gate_verifier=gate_verifier,
        condition_verifier=condition_verifier,
    )

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert gate_verifier.calls == []
    assert condition_verifier.calls == []
    assert outcome.trace.gate_verifications == ()
    assert outcome.trace.condition_verifications == ()


def test_a_policy_failure_outcome_preserves_no_usable_policy_material():
    outcome = _assess(request(policy=POLICY))

    assert outcome.trace.issuance_record_ref == ""
    assert outcome.trace.resolved_policy_digest == ""
    assert outcome.evaluation is None
    assert outcome.classification is None
    # The requested reference is the caller's own input; nothing else leaks.
    assert outcome.trace.readiness_policy_ref == POLICY.reference


def test_a_mandatory_fail_cannot_produce_a_headline_under_a_policy_failure():
    """Gate information never survives a policy-resolution failure."""

    req = request(policy=POLICY, gate_results=[gate_result(POLICY, "m1", GateStatus.FAIL)])
    outcome = _assess(req, policy_resolver=None)

    assert outcome.status is ReadinessAssessmentStatus.NOT_EVALUATED
    assert outcome.classification is None
