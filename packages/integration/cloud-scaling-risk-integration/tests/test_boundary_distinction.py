"""The three-way distinction that Phase 4C exists to make.

This is the single most important file in the suite, because the three cases below look
similar and are routinely conflated:

1. **Partial tampering with a stale digest** — an altered field left paired with the
   digest it no longer matches. Phase 4A/4B detect this, and so does the adapter.
2. **A fully self-consistent but unauthenticated Risk Authority request** — fabricated
   from nothing, with every digest correctly recomputed by the fabricator. Phase 4A/4B
   accept it **structurally**, because internal consistency is all they check and it is
   internally consistent by construction. This is not a defect; it is the documented
   limit of what binding validation proves.
3. **The adapter boundary** — which constructs a request *only* from a controller
   recommendation whose digest reconciled with an independent expectation. Case 2 has no
   such recommendation, so the adapter has no path that would produce it.

The tests also pin the consequence that keeps case 2 tolerable: a fabricated request
obtains **no execution authority**. It terminates at a non-executable decision like
everything else on this path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from conftest import INSIDE_WINDOW, RecordingSeam, fixed_clock, reference_seam
from risk_authority.domain import Scope
from risk_authority.integrations import (
    SubjectBinding,
    SubjectContext,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequestV2,
    validate_subject_binding,
)
from risk_authority.integrations.evaluation_contracts import SubjectBindingError

from ugence_cloud_scaling_risk_integration import (
    DOMAIN_CLOUD_SCALING,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskAdapter,
    authenticate_controller_output,
    build_idempotency_key,
    project_recommendation,
)


def fabricate_self_consistent_request(
    *,
    tenant_id: str = "tnt-fabricated",
    subject_id: str = "wl-fabricated",
    recommendation_digest: str = "sha256:" + "9" * 64,
) -> SubjectRiskEvaluationRequestV2:
    """Build a v2 request from nothing, with every digest correctly recomputed.

    No ``CapacityActionRecommendation`` exists behind ``recommendation_digest`` — it is
    an arbitrary well-formed digest string. Everything else is computed exactly as the
    contract requires, which is precisely what makes this the interesting case.
    """

    now = INSIDE_WINDOW
    context = SubjectContext(
        action_type="scale_up",
        subject_asserted_at=now,
        subject_valid_from=now - timedelta(minutes=5),
        subject_valid_until=now + timedelta(minutes=30),
        environment="prod",
        region="eu-west-1",
        compute_group="cluster-fabricated",
        resource_class="web",
        magnitude_before=2,
        magnitude_after=64,
    )
    binding = SubjectBinding(
        tenant_id=tenant_id,
        subject_id=subject_id,
        subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
        recommendation_digest=recommendation_digest,
        context_digest=context.digest(),
    )
    return SubjectRiskEvaluationRequestV2(
        subject_type=SUBJECT_TYPE_CAPACITY_SUBJECT,
        subject_id=subject_id,
        subject_digest=binding.digest(),
        tenant_id=tenant_id,
        requested_purpose=PURPOSE_CAPACITY_ACTION,
        requested_domain=DOMAIN_CLOUD_SCALING,
        requested_scope=Scope(purposes=(PURPOSE_CAPACITY_ACTION,)),
        evidence_references=("sha256:" + "e" * 64,),
        subject_context=context,
        recommendation_digest=recommendation_digest,
        idempotency_key=build_idempotency_key(
            tenant_id=tenant_id,
            subject_id=subject_id,
            recommendation_digest=recommendation_digest,
        ),
    )


# --- case 1: partial tampering with a stale digest MUST fail ---------------------------


def test_case1_partial_tampering_fails_binding_validation(recommendation):
    projection = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    canonical = projection.request.to_canonical_dict()
    canonical["subject_context"] = {
        **canonical["subject_context"],
        "magnitude_after": 999,
    }
    # subject_digest deliberately left stale.
    tampered = SubjectRiskEvaluationRequestV2.from_dict(canonical)
    with pytest.raises(SubjectBindingError, match="subject_digest mismatch"):
        validate_subject_binding(tampered)


def test_case1_partial_tampering_also_fails_at_the_adapter(recommendation):
    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    document = dict(recommendation.to_canonical_dict())
    document["recommendation_id"] = "rec-TAMPERED"
    outcome = adapter.evaluate(document)
    assert outcome.rejection_reason is AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH
    assert not seam.reached


# --- case 2: a fully self-consistent fabrication IS structurally accepted ---------------


def test_case2_a_fabricated_request_passes_binding_validation():
    """The documented limit of Phase 4A/4B, asserted rather than assumed.

    If this test ever started failing, the honest reading would be that binding
    validation had quietly acquired a stronger guarantee than the ADR claims — which
    would need recording, not celebrating.
    """

    fabricated = fabricate_self_consistent_request()
    validation = validate_subject_binding(fabricated)
    assert validation.subject_digest == fabricated.subject_digest
    assert validation.recommendation_digest == fabricated.recommendation_digest


def test_case2_a_fabricated_request_reaches_the_seam_and_is_evaluated():
    """Structural admission is real: the seam does evaluate it."""

    seam = reference_seam(now=INSIDE_WINDOW)
    decision = seam.evaluate(fabricate_self_consistent_request())
    assert decision.disposition in set(SubjectRiskDisposition)


def test_case2_a_fabricated_request_still_obtains_no_execution_authority():
    """...and this is why case 2 is a documented limit rather than an escalation path."""

    decision = reference_seam(now=INSIDE_WINDOW).evaluate(
        fabricate_self_consistent_request()
    )
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "actuation_performed", "effect_verified", "executable"):
        assert getattr(decision, flag) is False


def test_case2_no_controller_recommendation_exists_behind_the_digest():
    """Make the premise explicit: the digest names nothing."""

    from ugence_cloud_scaling_risk_integration import RecommendationInputError

    fabricated = fabricate_self_consistent_request()
    assert fabricated.recommendation_digest == "sha256:" + "9" * 64
    # Nothing in the controller contract can produce that digest from real content here;
    # the fabricator simply chose a well-formed string. Asking the adapter to accept a
    # recommendation "behind" it fails at strict reconstruction, before any digest work.
    with pytest.raises(RecommendationInputError):
        authenticate_controller_output(
            {"schema_version": "capacity-action-recommendation-1"},
            expected_recommendation_digest=fabricated.recommendation_digest,
        )


# --- case 3: the ADAPTER cannot construct case 2 -----------------------------------------


def test_case3_the_adapter_has_no_path_that_fabricates_a_request():
    """Every adapter entry point demands a controller artifact, not request fields."""

    import inspect

    for func in (CloudScalingRiskAdapter.evaluate, CloudScalingRiskAdapter.project):
        parameters = set(inspect.signature(func).parameters) - {"self"}
        assert parameters == {"source", "expected_recommendation_digest"}, parameters
    # ...and the projection accepts only an already-authenticated recommendation.
    projection_params = set(inspect.signature(project_recommendation).parameters)
    assert projection_params == {"authenticated"}


def test_case3_the_adapter_refuses_a_fabricated_request_as_input():
    """Handing the fabricated request back in is not a way around the boundary."""

    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    fabricated = fabricate_self_consistent_request()
    outcome = adapter.evaluate(fabricated.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE
    assert not seam.reached


def test_case3_the_adapter_only_emits_requests_backed_by_a_verified_recommendation(
    recommendation,
):
    """The positive half: what the adapter does emit is bound to a real recommendation."""

    seam = RecordingSeam()
    seam.decision = reference_seam(now=INSIDE_WINDOW).evaluate(
        project_recommendation(
            authenticate_controller_output(recommendation.to_canonical_dict())
        ).request
    )
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    adapter.evaluate(recommendation.to_canonical_dict())

    submitted = seam.calls[0]
    assert submitted.recommendation_digest == recommendation.digest(), (
        "the submitted request must be bound to the digest of the actual recommendation"
    )


def test_case3_a_cross_tenant_fabrication_is_structurally_admitted_but_unreachable(
    recommendation,
):
    """Cross-tenant substitution, done consistently, is case 2 — not an adapter hole."""

    real_tenant = recommendation.subject.tenant_id
    fabricated = fabricate_self_consistent_request(tenant_id="tnt-attacker")
    assert fabricated.tenant_id != real_tenant
    # Structurally consistent, so binding validation passes (case 2)...
    assert validate_subject_binding(fabricated).tenant_id == "tnt-attacker"
    # ...but the adapter never emits a request for a tenant the recommendation lacks.
    projection = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    assert projection.tenant_id == real_tenant
    assert projection.request.tenant_id == real_tenant


# --- the resolver, specifically, is never reached on a failed gate -----------------------


@pytest.mark.parametrize(
    "make_source",
    [
        pytest.param(lambda rec: object(), id="foreign-object"),
        pytest.param(
            lambda rec: {**rec.to_canonical_dict(), "recommendation_id": "x"},
            id="stale-digest",
        ),
        pytest.param(lambda rec: rec, id="no-independent-digest"),
        pytest.param(
            lambda rec: {**rec.to_canonical_dict(), "smuggled": 1}, id="unknown-field"
        ),
    ],
)
def test_the_policy_resolver_observes_nothing_when_a_gate_fails(recommendation, make_source):
    """Stronger than "the seam returned a rejection": the resolver saw no facts at all."""

    seam = reference_seam(now=INSIDE_WINDOW)
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    outcome = adapter.evaluate(make_source(recommendation))
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert seam._policy_resolver.last_subject_context == [], (
        "the policy resolver observed subject facts despite a failed adapter gate"
    )


def test_the_resolver_non_reachability_assertion_is_not_vacuous(recommendation):
    """The control for the test above: on the success path the resolver IS reached.

    Without this, ``last_subject_context == []`` could hold simply because the resolver
    is never called on any path, and the negative assertion would be worthless.
    """

    seam = reference_seam(now=INSIDE_WINDOW)
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION
    assert len(seam._policy_resolver.last_subject_context) == 1, (
        "the resolver must be reached on the success path for the negative assertion "
        "above to mean anything"
    )
