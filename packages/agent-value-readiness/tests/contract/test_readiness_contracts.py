"""Contract + adversarial tests for the Agent Value Readiness contracts (GV-3R-a).

Structure only. No test expects the package to compute a readiness decision —
that is GV-3R-b. GateResult embeds the actual PolicyGate (kind/applicability are
derived, non-forgeable); the determination derives its blocking/indeterminate
sets from gate_results.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import datetime, timezone

import pytest

from ugence_governance_contracts.api import (
    AssessmentWindow,
    BenchmarkReference,
    MetricClaim,
    SourceBasis,
    TransformationMethod,
)
from ugence_uvi_policy_contracts.api import (
    AssessmentContext,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    IntendedOutcomePolicy,
    PolicyArtifactMetadata,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyReference,
    ReadinessTarget,
    RequirementClass,
)
from ugence_agent_value_readiness.api import (
    AdoptionDimension,
    AdoptionReadinessResult,
    AgentValueReadinessDetermination,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionStatus,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessClassification,
    ReadinessContractError,
    ReadinessIndicatorClass,
)

D = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
WIN = AssessmentWindow(start=T0, end=MID)
TEN, SUB, CTX = "t1", "agent1", "ctx1"
PROD = (ReadinessTarget.PRODUCTION,)
PILOT = (ReadinessTarget.PILOT,)
BOTH = (ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION)


def _meta(family, pid):
    return PolicyArtifactMetadata(
        policy_id=pid, policy_family=family, version="1", content_digest=D,
        lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1,
    )


def context(tenant=TEN, subject=SUB, cid=CTX):
    geo = GeographyPolicy(metadata=_meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
    dom = DomainPolicy(metadata=_meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="ticket")
    io = IntendedOutcomePolicy(metadata=_meta(PolicyFamily.INTENDED_OUTCOME, "i"), target_outcome="o", task_definition="t")
    return AssessmentContext.bind_policies(context_id=cid, tenant_id=tenant, subject_id=subject, geography=geo, domain=dom, intended_outcome=io, as_of=MID)


def rref():
    return PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D)


def pgate(gid="g1", kind=RequirementClass.MANDATORY, applicability=PROD):
    return PolicyGate(gate_id=gid, category=GateCategory.SAFETY, requirement_class=kind, applicability=applicability)


def gate(gid="g1", kind=RequirementClass.MANDATORY, applicability=PROD, target=ReadinessTarget.PRODUCTION, status=GateStatus.PASS, ref=None):
    return GateResult(policy_gate=pgate(gid, kind, applicability), readiness_policy_ref=ref or rref(), requested_target=target, status=status)


def claim(metric="accuracy", value="0.95", tenant=TEN, subject=SUB, basis=SourceBasis.OBSERVED):
    kw = {"assessment_window": WIN} if basis is SourceBasis.OBSERVED else {}
    return MetricClaim(claim_id=f"clm-{metric}", tenant_id=tenant, subject_id=subject, metric_id=metric, value=value,
                       governed_unit="ratio", source_basis=basis, transformation_method=TransformationMethod.DIRECT, **kw)


def intel(**kw):
    base = dict(result_id="ir1", tenant_id=TEN, subject_id=SUB, context_id=CTX, task_or_outcome_ref="i",
                dimension=IntelligenceDimension.ACCURACY, claim=claim("accuracy"), requirement_class=RequirementClass.MANDATORY,
                applicable_targets=list(BOTH), status=GateStatus.PASS)
    base.update(kw)
    return IntelligenceFitnessResult(**base)


def cap(**kw):
    base = dict(result_id="cr1", tenant_id=TEN, subject_id=SUB, context_id=CTX, task_or_outcome_ref="i",
                dimension=CapabilityDimension.TOOL_READINESS, claim=claim("tool", "1.0"), requirement_class=RequirementClass.MANDATORY,
                applicable_targets=list(PROD), status=GateStatus.PASS, demonstration=CapabilityDemonstration.MET_THRESHOLD, evidence_sufficient=True)
    base.update(kw)
    return CapabilityReadinessResult(**base)


def adopt(**kw):
    base = dict(result_id="ar1", tenant_id=TEN, subject_id=SUB, context_id=CTX, task_or_outcome_ref="i",
                dimension=AdoptionDimension.EXPECTED_UTILIZATION, claim=claim("util", "0.7"), requirement_class=RequirementClass.ADVISORY,
                applicable_targets=list(PILOT), status=GateStatus.PASS)
    base.update(kw)
    return AdoptionReadinessResult(**base)


def active_condition(cid="cond1", source="cg", ef=T0, et=None, exp=None):
    return ConditionSet(
        condition_id=cid, source_gate_or_finding_ref=source, concern_requirement_class=RequirementClass.CONDITIONAL,
        current_status=ConditionStatus.APPROVED_ACTIVE, approved_mitigation_ref="mit", approving_authority_ref="auth",
        accountable_owner="owner", scope_exposure_limit="limited", monitoring_requirement="weekly",
        evidence_refs=["ev1"], effective_from=ef, effective_to=et, expiry=exp, revocation_trigger="breach",
    )


def determination(**kw):
    base = dict(assessment_id="a1", tenant_id=TEN, subject_id=SUB, context=context(), readiness_policy_ref=rref(),
                requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY, created_at=MID)
    base.update(kw)
    return AgentValueReadinessDetermination(**base)


# --------------------------------------------------------------------------- #
# Distinct types + classifications
# --------------------------------------------------------------------------- #
def test_indicator_types_are_distinct():
    assert IntelligenceFitnessResult is not CapabilityReadinessResult is not AdoptionReadinessResult
    assert intel().indicator_class is ReadinessIndicatorClass.INTELLIGENCE
    assert cap().indicator_class is ReadinessIndicatorClass.CAPABILITY
    assert adopt().indicator_class is ReadinessIndicatorClass.ADOPTION


def test_all_five_classifications_representable():
    assert {c.value for c in ReadinessClassification} == {
        "NOT_ASSESSABLE", "NOT_READY", "PILOT_READY", "READY_WITH_CONDITIONS", "DEPLOYMENT_READY"}


def test_gate_status_values():
    assert {g.value for g in GateStatus} == {"PASS", "FAIL", "INDETERMINATE"}


# --------------------------------------------------------------------------- #
# Indicator structural rules
# --------------------------------------------------------------------------- #
def test_indicator_cross_tenant_claim_rejected():
    with pytest.raises(ReadinessContractError):
        intel(claim=claim("accuracy", tenant="OTHER"))


def test_indicator_cross_subject_claim_rejected():
    with pytest.raises(ReadinessContractError):
        intel(claim=claim("accuracy", subject="OTHER"))


def test_indicator_threshold_xor_benchmark():
    bench = BenchmarkReference(benchmark_id="b", version="1", content_digest=D)
    with pytest.raises(ReadinessContractError):
        intel(threshold_ref="thr", benchmark_ref=bench)


def test_capability_distinguishes_demonstration_states():
    missing = cap(demonstration=CapabilityDemonstration.NOT_PRESENT, status=GateStatus.FAIL, requirement_class=RequirementClass.MANDATORY)
    assert missing.demonstration is CapabilityDemonstration.NOT_PRESENT
    assert missing.status is GateStatus.FAIL


def test_capability_evidence_sufficient_must_be_bool():
    with pytest.raises(ReadinessContractError):
        cap(evidence_sufficient="yes")


def test_adoption_pre_deployment_locked_true():
    with pytest.raises(ReadinessContractError):
        adopt(pre_deployment=False)
    assert adopt().pre_deployment is True


def test_adoption_preserves_source_basis_axis_without_elevation():
    r = adopt(claim=claim("util", "0.7", basis=SourceBasis.REPORTED))
    assert r.claim.source_basis is SourceBasis.REPORTED
    assert r.claim.attribution_status.value == "NOT_APPLICABLE"


# --------------------------------------------------------------------------- #
# GateResult: embedded PolicyGate; derived, non-forgeable facts
# --------------------------------------------------------------------------- #
def test_gateresult_requires_readiness_family_ref():
    bad = PolicyReference(policy_id="x", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=D)
    with pytest.raises(ReadinessContractError):
        gate(ref=bad)


def test_gateresult_requires_policygate():
    with pytest.raises(ReadinessContractError):
        GateResult(policy_gate="not-a-gate", readiness_policy_ref=rref(), requested_target=ReadinessTarget.PILOT, status=GateStatus.PASS)


def test_gate_kind_and_id_derived_from_policygate():
    g = gate(gid="gg", kind=RequirementClass.CONDITIONAL, applicability=PROD)
    assert g.gate_id == "gg"
    assert g.gate_kind is RequirementClass.CONDITIONAL


def test_diagnostic_gate_is_not_blocking_even_on_fail():
    # Production-only gate evaluated for a PILOT target -> diagnostic.
    g = gate(gid="prod-only", kind=RequirementClass.MANDATORY, applicability=PROD, target=ReadinessTarget.PILOT, status=GateStatus.FAIL)
    assert g.is_diagnostic is True
    assert g.is_blocking is False


def test_applicable_mandatory_fail_is_blocking():
    g = gate(kind=RequirementClass.MANDATORY, applicability=PROD, target=ReadinessTarget.PRODUCTION, status=GateStatus.FAIL)
    assert g.is_blocking is True


def test_applicable_advisory_fail_is_not_blocking():
    g = gate(kind=RequirementClass.ADVISORY, applicability=PROD, target=ReadinessTarget.PRODUCTION, status=GateStatus.FAIL)
    assert g.is_blocking is False


def test_pilot_safety_gate_applicable_for_both():
    g_pilot = gate(kind=RequirementClass.MANDATORY, applicability=BOTH, target=ReadinessTarget.PILOT, status=GateStatus.PASS)
    g_prod = gate(kind=RequirementClass.MANDATORY, applicability=BOTH, target=ReadinessTarget.PRODUCTION, status=GateStatus.PASS)
    assert g_pilot.applicable and g_prod.applicable


# --------------------------------------------------------------------------- #
# ConditionSet
# --------------------------------------------------------------------------- #
def test_condition_rejects_mandatory_concern():
    with pytest.raises(ReadinessContractError):
        ConditionSet(condition_id="c", source_gate_or_finding_ref="g", concern_requirement_class=RequirementClass.MANDATORY, current_status=ConditionStatus.PROPOSED)


def test_incomplete_approved_active_rejected():
    with pytest.raises(ReadinessContractError):
        ConditionSet(condition_id="c", source_gate_or_finding_ref="g", concern_requirement_class=RequirementClass.CONDITIONAL, current_status=ConditionStatus.APPROVED_ACTIVE)


def test_complete_approved_active_is_active_at_mid():
    c = active_condition()
    assert c.is_active is True
    assert c.is_active_at(MID) is True


def test_expired_status_condition_is_not_active():
    c = ConditionSet(condition_id="c", source_gate_or_finding_ref="g", concern_requirement_class=RequirementClass.CONDITIONAL, current_status=ConditionStatus.EXPIRED)
    assert c.is_active is False
    assert c.is_active_at(MID) is False


# --------------------------------------------------------------------------- #
# Determination: happy paths + basic structure
# --------------------------------------------------------------------------- #
def test_determination_happy_pilot_ready():
    det = determination(gate_results=[gate(applicability=PILOT, target=ReadinessTarget.PILOT, status=GateStatus.PASS)])
    assert det.classification is ReadinessClassification.PILOT_READY
    assert det.is_advisory is True


def test_deployment_ready_production_ok():
    det = determination(requested_target=ReadinessTarget.PRODUCTION, classification=ReadinessClassification.DEPLOYMENT_READY,
                        gate_results=[gate(status=GateStatus.PASS)])
    assert det.classification is ReadinessClassification.DEPLOYMENT_READY


def test_pilot_ready_cannot_target_production():
    with pytest.raises(ReadinessContractError):
        determination(requested_target=ReadinessTarget.PRODUCTION, classification=ReadinessClassification.PILOT_READY)


def test_deployment_ready_cannot_target_pilot():
    with pytest.raises(ReadinessContractError):
        determination(requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.DEPLOYMENT_READY)


def test_not_ready_requires_reason():
    with pytest.raises(ReadinessContractError):
        determination(classification=ReadinessClassification.NOT_READY)


def test_not_ready_with_blocking_gate_ok():
    g = gate(gid="mfail", applicability=PILOT, target=ReadinessTarget.PILOT, status=GateStatus.FAIL)
    det = determination(classification=ReadinessClassification.NOT_READY, gate_results=[g])
    assert det.blocking_gate_ids == ("mfail",)


def test_not_assessable_requires_reason():
    with pytest.raises(ReadinessContractError):
        determination(classification=ReadinessClassification.NOT_ASSESSABLE)


def test_not_assessable_with_indeterminate_gate_ok():
    g = gate(gid="mind", applicability=PILOT, target=ReadinessTarget.PILOT, status=GateStatus.INDETERMINATE)
    det = determination(classification=ReadinessClassification.NOT_ASSESSABLE, gate_results=[g])
    assert det.indeterminate_gate_ids == ("mind",)


def test_determination_gate_target_must_match_requested():
    g = gate(gid="g1", applicability=PROD, target=ReadinessTarget.PRODUCTION, status=GateStatus.PASS)
    with pytest.raises(ReadinessContractError):
        determination(requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY, gate_results=[g])


def test_determination_cross_tenant_context_rejected():
    with pytest.raises(ReadinessContractError):
        determination(context=context(tenant="OTHER"))


def test_determination_cross_tenant_result_rejected():
    bad = intel(tenant_id="OTHER", subject_id=SUB, claim=claim("accuracy", tenant="OTHER"))
    with pytest.raises(ReadinessContractError):
        determination(intelligence_results=[bad])


def test_determination_result_context_mismatch_rejected():
    with pytest.raises(ReadinessContractError):
        determination(intelligence_results=[intel(context_id="OTHERCTX")])


def test_determination_duplicate_gate_ids_rejected():
    with pytest.raises(ReadinessContractError):
        determination(gate_results=[gate(gid="g"), gate(gid="g")])


def test_determination_diagnostic_gate_ids_property():
    g_app = gate(gid="app", applicability=PILOT, target=ReadinessTarget.PILOT, status=GateStatus.PASS)
    g_diag = gate(gid="diag", applicability=PROD, target=ReadinessTarget.PILOT, status=GateStatus.PASS)
    det = determination(gate_results=[g_app, g_diag])
    assert det.diagnostic_gate_ids == ("diag",)


def test_readiness_policy_ref_must_be_readiness_family():
    with pytest.raises(ReadinessContractError):
        determination(readiness_policy_ref=PolicyReference(policy_id="x", policy_family=PolicyFamily.DOMAIN, version="1", content_digest=D))


def test_created_at_must_be_tzaware():
    with pytest.raises(ReadinessContractError):
        determination(created_at=datetime(2026, 6, 1))
