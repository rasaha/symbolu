"""End-to-end adapter behavior, and the negative assertion that carries most of the weight.

The recurring shape here is: **make an adapter gate fail, then assert the seam recorded
nothing at all.** A test that only checked the returned status would pass even if the
adapter had already called the resolver, read evidence and then discarded the result — so
every failure path below asserts non-reachability, not just the reported outcome.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from conftest import (
    INSIDE_WINDOW,
    RecordingSeam,
    build_recommendation,
    fixed_clock,
    reference_seam,
)
from risk_authority.integrations import SubjectRiskDecision, SubjectRiskDisposition

from ugence_cloud_scaling_risk_integration import (
    AdapterConfigurationError,
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskAdapter,
    CloudScalingRiskOutcome,
    NonExecutableInvariantError,
    RiskEvaluationSeamPort,
)


# --- construction -------------------------------------------------------------------


def test_the_adapter_requires_an_injected_seam():
    with pytest.raises(AdapterConfigurationError, match="RiskEvaluationSeam"):
        CloudScalingRiskAdapter(seam=None, clock=fixed_clock())


def test_a_seam_without_evaluate_is_refused():
    class NotASeam:
        pass

    with pytest.raises(AdapterConfigurationError, match="RiskEvaluationSeamPort"):
        CloudScalingRiskAdapter(seam=NotASeam(), clock=fixed_clock())


def test_the_real_seam_satisfies_the_narrow_port():
    assert isinstance(reference_seam(), RiskEvaluationSeamPort)


def test_the_port_exposes_exactly_one_method():
    """Structural containment: there is no envelope/ActionGate/credential surface."""

    members = {
        name
        for name in dir(RiskEvaluationSeamPort)
        if not name.startswith("_") and callable(getattr(RiskEvaluationSeamPort, name, None))
    }
    assert members == {"evaluate"}


def test_the_adapter_never_constructs_a_seam_resolver_or_clock():
    """No factory, default argument or fallback can produce a dependency.

    The scan walks the **AST** rather than the raw text, so it inspects code that would
    actually execute and is not fooled — in either direction — by the module docstring
    naming these very symbols while explaining that it does not use them.
    """

    import ast
    import inspect

    from ugence_cloud_scaling_risk_integration import adapter as adapter_module

    signature = inspect.signature(CloudScalingRiskAdapter.__init__)
    for name in ("seam", "clock"):
        assert signature.parameters[name].default is inspect.Parameter.empty, (
            f"{name} must have no default — a default is how a stand-in gets installed"
        )

    forbidden = {
        "production", "reference",           # seam factories
        "ReferencePolicyResolver", "ReferenceSubjectAwarePolicyResolver",
        "ReferenceControlEvidenceResolver", "ReferenceDecisionAuthority",
        "now", "utcnow", "today",            # ambient clocks
    }
    tree = ast.parse(inspect.getsource(adapter_module))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    offenders = called & forbidden
    assert not offenders, f"the adapter must not call {sorted(offenders)}"


# --- the happy path ------------------------------------------------------------------


def test_a_valid_recommendation_yields_a_non_executable_decision(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())

    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION
    assert isinstance(outcome, CloudScalingRiskOutcome)
    assert isinstance(outcome.decision, SubjectRiskDecision)
    assert outcome.disposition in set(SubjectRiskDisposition)
    assert outcome.grants_authority is False
    assert outcome.decision.executable is False


def test_the_decision_is_bound_to_what_the_adapter_projected(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.decision.subject_digest == outcome.projection.subject_digest
    assert outcome.decision.request_digest == outcome.projection.request_digest
    assert outcome.decision.tenant_id == outcome.projection.tenant_id
    assert outcome.decision.idempotency_key == outcome.projection.idempotency_key


def test_the_resolver_observes_the_validated_context(recommendation):
    """Phase 4B hands the resolver RA's re-validated context, not the raw one."""

    seam = reference_seam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    observed = seam._policy_resolver.last_subject_context
    assert observed, "the subject-aware resolver was never reached"
    assert observed[-1].digest() == outcome.projection.context_digest


def test_the_live_object_path_works_with_an_expectation(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION


def test_repeated_evaluations_are_deterministic(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    first = adapter.evaluate(recommendation.to_canonical_dict())
    second = adapter.evaluate(recommendation.to_canonical_dict())
    assert first.projection.request_digest == second.projection.request_digest
    assert first.projection.idempotency_key == second.projection.idempotency_key


# --- the seam is not reached when any gate fails --------------------------------------


@pytest.mark.parametrize(
    "make_source,expected",
    [
        pytest.param(
            lambda rec: {"schema_version": "not-a-controller-schema"},
            AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE,
            id="unsupported-schema",
        ),
        pytest.param(
            lambda rec: object(),
            AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE,
            id="foreign-object",
        ),
        pytest.param(
            lambda rec: {**rec.to_canonical_dict(), "smuggled": "value"},
            AdapterRejectionReason.MALFORMED_RECOMMENDATION,
            id="unknown-field",
        ),
        pytest.param(
            lambda rec: {**rec.to_canonical_dict(), "recommendation_id": "tampered"},
            AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH,
            id="stale-digest",
        ),
        pytest.param(
            lambda rec: rec,
            AdapterRejectionReason.MISSING_INDEPENDENT_RECOMMENDATION_DIGEST,
            id="no-independent-digest",
        ),
    ],
)
def test_a_failed_gate_means_the_seam_observed_nothing(recommendation, make_source, expected):
    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    outcome = adapter.evaluate(make_source(recommendation))

    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is expected
    assert outcome.decision is None
    assert not seam.reached, "the seam was reached despite a failed adapter gate"


def test_a_missing_tenant_never_reaches_the_seam():
    import ph_helpers as H

    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    rec = build_recommendation(
        subject=H.subject(tenant_id=None), recommendation_id="rec-no-tenant"
    )
    outcome = adapter.evaluate(rec.to_canonical_dict())
    assert outcome.rejection_reason is AdapterRejectionReason.PROJECTION_FAILED
    assert not seam.reached


def test_an_expired_recommendation_never_reaches_the_seam(recommendation):
    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(
        seam=seam, clock=fixed_clock(INSIDE_WINDOW + timedelta(days=1))
    )
    outcome = adapter.evaluate(recommendation.to_canonical_dict())
    assert outcome.rejection_reason is AdapterRejectionReason.RECOMMENDATION_EXPIRED
    assert not seam.reached


# --- what the adapter refuses to accept back ---------------------------------------------


def test_a_seam_returning_a_non_decision_object_is_refused(recommendation):
    class BadSeam:
        def evaluate(self, request):
            return {"disposition": "RISK_PASSED", "executable": True}

    adapter = CloudScalingRiskAdapter(seam=BadSeam(), clock=fixed_clock(INSIDE_WINDOW))
    with pytest.raises(NonExecutableInvariantError, match="SubjectRiskDecision"):
        adapter.evaluate(recommendation.to_canonical_dict())


def test_a_seam_returning_a_forged_executable_decision_is_refused(recommendation):
    """A forged True is rejected, never normalized to False."""

    real = reference_seam().evaluate(
        CloudScalingRiskAdapter(seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW))
        .project(recommendation.to_canonical_dict())
        .request
    )
    forged = object.__new__(SubjectRiskDecision)
    for field, value in real.__dict__.items():
        object.__setattr__(forged, field, value)
    object.__setattr__(forged, "executable", True)

    class ForgingSeam:
        def evaluate(self, request):
            return forged

    adapter = CloudScalingRiskAdapter(seam=ForgingSeam(), clock=fixed_clock(INSIDE_WINDOW))
    with pytest.raises(NonExecutableInvariantError, match="forged"):
        adapter.evaluate(recommendation.to_canonical_dict())


# --- the typed outcome contract -----------------------------------------------------------


def test_an_outcome_cannot_be_constructed_with_an_executable_flag():
    with pytest.raises(NonExecutableInvariantError, match="executable"):
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_REJECTED,
            rejection_reason=AdapterRejectionReason.PROJECTION_FAILED,
            executable=True,
        )


@pytest.mark.parametrize(
    "flag",
    ["authorization_performed", "envelope_issued", "actiongate_invoked",
     "credential_issued", "actuation_performed", "effect_verified"],
)
def test_no_outcome_may_claim_an_authority_flag(flag):
    with pytest.raises(NonExecutableInvariantError):
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_REJECTED,
            rejection_reason=AdapterRejectionReason.PROJECTION_FAILED,
            **{flag: True},
        )


def test_a_rejected_outcome_cannot_carry_a_decision(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(), clock=fixed_clock(INSIDE_WINDOW)
    )
    decision = adapter.evaluate(recommendation.to_canonical_dict()).decision
    with pytest.raises(NonExecutableInvariantError, match="never carries a risk decision"):
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_REJECTED,
            rejection_reason=AdapterRejectionReason.PROJECTION_FAILED,
            decision=decision,
        )


def test_a_rejected_outcome_requires_a_typed_reason():
    with pytest.raises(NonExecutableInvariantError, match="AdapterRejectionReason"):
        CloudScalingRiskOutcome(status=AdapterOutcomeStatus.PROJECTION_REJECTED)


def test_an_abstention_outcome_cannot_carry_a_projection():
    with pytest.raises(NonExecutableInvariantError, match="never reaches the seam"):
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM,
            abstention_reason="forecast_abstained",
            projection=object(),
        )
