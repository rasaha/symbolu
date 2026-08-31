"""Time authority: the adapter never becomes a clock, and never forwards one.

Two separate properties are at stake and are tested separately:

* **The adapter's own expiry gate** uses the *injected* trusted clock and fails closed
  outside the validity window, before the seam is reached.
* **Risk Authority's evaluation time** is never caller-supplied. The request always
  carries ``evaluation_time=None``, there is no API parameter that could set it, and the
  trusted production path rejects a caller-supplied value fail-closed if one ever
  appeared.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from conftest import REC_TIME, VALIDITY_SECONDS, fixed_clock, reference_seam
from risk_authority.integrations import (
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequestV2,
    SubjectRiskNonDecisionReason,
)

from ugence_cloud_scaling_risk_integration import (
    AdapterConfigurationError,
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskAdapter,
    authenticate_controller_output,
    project_recommendation,
)

VALID_FROM = REC_TIME
VALID_UNTIL = REC_TIME + timedelta(seconds=VALIDITY_SECONDS)


def adapter_at(now, seam):
    return CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(now))


# --- exact validity boundaries ---------------------------------------------------------


@pytest.mark.parametrize(
    "now,label",
    [
        (VALID_FROM, "exactly at valid_from"),
        (VALID_UNTIL, "exactly at valid_until"),
        (VALID_FROM + timedelta(microseconds=1), "one microsecond after opening"),
        (VALID_UNTIL - timedelta(microseconds=1), "one microsecond before closing"),
    ],
)
def test_instants_inside_the_window_are_admitted(recording_seam, recommendation, now, label):
    """Both boundaries are inclusive, matching the seam's own comparison exactly."""

    seam = reference_seam(now=now)
    outcome = adapter_at(now, seam).evaluate(recommendation.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION, label


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(microseconds=1), AdapterRejectionReason.RECOMMENDATION_EXPIRED),
        (timedelta(seconds=1), AdapterRejectionReason.RECOMMENDATION_EXPIRED),
        (timedelta(days=1), AdapterRejectionReason.RECOMMENDATION_EXPIRED),
    ],
)
def test_expired_recommendations_never_reach_the_seam(
    forbidden_seam, recommendation, delta, expected
):
    outcome = adapter_at(VALID_UNTIL + delta, forbidden_seam).evaluate(
        recommendation.to_canonical_dict()
    )
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is expected
    assert outcome.decision is None


@pytest.mark.parametrize("delta", [timedelta(microseconds=1), timedelta(minutes=5)])
def test_not_yet_valid_recommendations_never_reach_the_seam(
    forbidden_seam, recommendation, delta
):
    outcome = adapter_at(VALID_FROM - delta, forbidden_seam).evaluate(
        recommendation.to_canonical_dict()
    )
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is AdapterRejectionReason.RECOMMENDATION_NOT_YET_VALID


# --- the trusted clock itself ------------------------------------------------------------


def test_a_naive_clock_is_rejected_rather_than_assumed_utc(forbidden_seam, recommendation):
    naive = CloudScalingRiskAdapter(
        seam=forbidden_seam, clock=lambda: datetime(2026, 1, 1, 0, 5, 0)
    )
    outcome = naive.evaluate(recommendation.to_canonical_dict())
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is AdapterRejectionReason.UNTRUSTED_CLOCK


def test_a_non_datetime_clock_is_rejected(forbidden_seam, recommendation):
    broken = CloudScalingRiskAdapter(seam=forbidden_seam, clock=lambda: "now")
    outcome = broken.evaluate(recommendation.to_canonical_dict())
    assert outcome.rejection_reason is AdapterRejectionReason.UNTRUSTED_CLOCK


def test_an_aware_non_utc_clock_is_normalized_losslessly(recommendation):
    """A +02:00 instant inside the window is the same instant, and is admitted."""

    offset = timezone(timedelta(hours=2))
    inside = (VALID_FROM + timedelta(seconds=60)).astimezone(offset)
    assert inside.utcoffset() == timedelta(hours=2)
    seam = reference_seam(now=inside.astimezone(timezone.utc))
    outcome = CloudScalingRiskAdapter(seam=seam, clock=lambda: inside).evaluate(
        recommendation.to_canonical_dict()
    )
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION


def test_the_adapter_requires_an_injected_clock(forbidden_seam):
    with pytest.raises(AdapterConfigurationError, match="clock"):
        CloudScalingRiskAdapter(seam=forbidden_seam, clock=None)


# --- caller-supplied evaluation time is never forwarded -------------------------------------


def test_the_projected_request_always_carries_no_evaluation_time(recommendation):
    projection = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    assert projection.request.evaluation_time is None
    assert projection.request.to_canonical_dict()["evaluation_time"] is None


def test_there_is_no_api_parameter_for_an_evaluation_time():
    """Structural: a caller cannot supply one because no parameter accepts one."""

    import inspect

    for func in (CloudScalingRiskAdapter.evaluate, CloudScalingRiskAdapter.project,
                 project_recommendation):
        parameters = set(inspect.signature(func).parameters)
        assert "evaluation_time" not in parameters
        assert "now" not in parameters
        assert "clock" not in parameters


def test_the_seam_receives_a_request_with_no_evaluation_time(recording_seam, recommendation):
    recording_seam.decision = reference_seam(now=VALID_FROM).evaluate(
        project_recommendation(
            authenticate_controller_output(recommendation.to_canonical_dict())
        ).request
    )
    adapter_at(VALID_FROM, recording_seam).evaluate(recommendation.to_canonical_dict())
    assert recording_seam.reached
    assert recording_seam.calls[0].evaluation_time is None


def test_a_caller_supplied_evaluation_time_is_rejected_by_the_production_path(recommendation):
    """Even if a forged request were built by hand, the trusted path refuses it.

    This is Risk Authority's guarantee rather than the adapter's, pinned here because
    the adapter's "never populate it" rule is only load-bearing if the downstream
    rejection actually exists.
    """

    from risk_authority.api.evaluation_seam import RiskEvaluationSeam
    from risk_authority.integrations.evaluation_contracts import (
        SubjectRiskEvaluationRequestV2 as V2,
    )

    projection = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    forged = V2.from_dict(
        {
            **projection.request.to_canonical_dict(),
            "evaluation_time": "2026-01-01T00:03:10.000000Z",
        }
    )
    assert forged.evaluation_time is not None

    # A production seam is what enforces the rule; build one only to prove it does.
    seam = _production_seam(now=VALID_FROM)
    decision = seam.evaluate(forged)
    assert decision.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert (
        decision.non_decision_reason
        is SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME
    )


def _production_seam(*, now):
    """A genuine production seam, used only to prove downstream rejection behavior.

    Built inside this test module — never by the adapter, which by contract receives an
    already-constructed seam and holds no factory of its own.
    """

    from risk_authority.api.evaluation_seam import RiskEvaluationSeam
    from risk_authority.crypto import SigningKey, SigningKeyRecord
    from risk_authority.domain import (
        AuthorityGrant,
        AuthorityType,
        Predicate,
        PredicateOp,
        RiskClass,
        RuleEffect,
        Scope,
        WorkflowIR,
        WorkflowRule,
        WorkflowStatus,
    )
    from risk_authority.integrations import InMemoryWorkflowIRSource

    from ugence_cloud_scaling_risk_integration import (
        DOMAIN_CLOUD_SCALING,
        PURPOSE_CAPACITY_ACTION,
    )

    workflow = WorkflowIR(
        workflow_ir_id="cloud-scaling-risk",
        version="1.0.0",
        status=WorkflowStatus.ACTIVE,
        rules=(
            WorkflowRule(
                rule_id="CS-1",
                conditions=(Predicate("domain", PredicateOp.EQ, DOMAIN_CLOUD_SCALING),),
                required_controls=("CAPACITY_CHANGE_REVIEWED",),
                effect=RuleEffect.DENY_UNLESS_ALL,
            ),
        ),
        source_refs=("ADR-CLOUD-SCALING-P4",),
        effective_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).with_digest()
    source = InMemoryWorkflowIRSource()
    source.register(workflow)

    class _Resolver:
        is_production_authoritative = True
        is_subject_context_aware = True

        def resolve_with_subject_context(self, **kwargs):
            return workflow

    class _EvidenceResolver:
        is_production_authoritative = True

        def resolve(self, **kwargs):
            return ()

    class _Admission:
        is_production_authoritative = True

        def admit(self, *args, **kwargs):
            return ()

    class _Assurance:
        # Required by RA-5 audit H-1: a permissive/reference evaluator may not mint
        # PASS in production. This double admits nothing, so the flag is honest.
        is_production_authoritative = True

        def assure(self, *args, **kwargs):
            return ()

    class _Ingress:
        # Deliberately NOT a reference/conformance stand-in (RA-5 audit F-1), and it
        # ingests nothing, so no evidence is ever admitted through this path.
        is_production_authoritative = True
        is_reference_ingress = False

        def ingest(self, *args, **kwargs):
            return ()

    class _DecisionAuthority:
        is_production_authoritative = True

        def rule(self, *args, **kwargs):
            raise AssertionError("the caller-supplied-time test never reaches ruling")

    grant = AuthorityGrant(
        principal_id="cloud-scaling-risk-prod",
        tenant_id="tenant-1",
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=(DOMAIN_CLOUD_SCALING,),
        allowed_risk_classes=(RiskClass.HIGH,),
        max_autonomy=0,
        delegated_by="enterprise-risk-office",
        grantable_scope=Scope(purposes=(PURPOSE_CAPACITY_ACTION,)),
    )
    return RiskEvaluationSeam.production(
        workflow_source=source,
        policy_resolver=_Resolver(),
        evidence_resolver=_EvidenceResolver(),
        evidence_admission=_Admission(),
        control_assurance=_Assurance(),
        evidence_ingress=_Ingress(),
        decision_authority=_DecisionAuthority(),
        evaluator_grant=grant,
        key_record=SigningKeyRecord("cs-key", SigningKey.from_seed(bytes(range(32)))),
        clock=lambda: now,
    )
