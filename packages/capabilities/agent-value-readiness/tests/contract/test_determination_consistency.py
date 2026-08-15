"""Adversarial tests for the GV-3R-a audit corrections (GV3R-F1..F6).

Every test asserts the security property, not merely that a constructor runs.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

import ugence_agent_value_readiness as R
import ugence_uvi_policy_contracts as uvi
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
    AgentValueReadinessDetermination,
    ConditionSet,
    ConditionStatus,
    GateResult,
    GateStatus,
    ReadinessClassification,
    ReadinessContractError,
)

D = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
FUT = datetime(2030, 1, 1, tzinfo=timezone.utc)
PAST = datetime(2020, 1, 1, tzinfo=timezone.utc)
PROD = (ReadinessTarget.PRODUCTION,)
PILOT = (ReadinessTarget.PILOT,)


def _meta(family, pid):
    return PolicyArtifactMetadata(policy_id=pid, policy_family=family, version="1", content_digest=D,
                                  lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1)


def ctx():
    return AssessmentContext.bind_policies(
        context_id="ctx1", tenant_id="t1", subject_id="a1",
        geography=GeographyPolicy(metadata=_meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US", reporting_currency="USD", functional_currency="USD"),
        domain=DomainPolicy(metadata=_meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="u"),
        intended_outcome=IntendedOutcomePolicy(metadata=_meta(PolicyFamily.INTENDED_OUTCOME, "i"), target_outcome="o", task_definition="t"),
        as_of=MID)


def rref():
    return PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D)


def pgate(gid, kind, applicability):
    return PolicyGate(gate_id=gid, category=GateCategory.SAFETY, requirement_class=kind, applicability=applicability)


def gate(gid, kind, status, applicability=PROD, target=ReadinessTarget.PRODUCTION, ref=None):
    return GateResult(policy_gate=pgate(gid, kind, applicability), readiness_policy_ref=ref or rref(), requested_target=target, status=status)


def cond(cid, source, status=ConditionStatus.APPROVED_ACTIVE, ef=T0, et=None, exp=None):
    kw = dict(condition_id=cid, source_gate_or_finding_ref=source, concern_requirement_class=RequirementClass.CONDITIONAL, current_status=status)
    if status is ConditionStatus.APPROVED_ACTIVE:
        kw.update(approved_mitigation_ref="m", approving_authority_ref="au", accountable_owner="o", scope_exposure_limit="l",
                  monitoring_requirement="mo", evidence_refs=["e"], revocation_trigger="rev")
    kw.update(effective_from=ef, effective_to=et, expiry=exp)
    return ConditionSet(**kw)


def det(**kw):
    base = dict(assessment_id="a", tenant_id="t1", subject_id="a1", context=ctx(), readiness_policy_ref=rref(),
                requested_target=ReadinessTarget.PRODUCTION, classification=ReadinessClassification.DEPLOYMENT_READY, created_at=MID)
    base.update(kw)
    return AgentValueReadinessDetermination(**base)


# --------------------------------------------------------------------------- #
# GV3R-F2: gate metadata is derived from the embedded PolicyGate (non-forgeable)
# --------------------------------------------------------------------------- #
def test_type_reexport_identity_unchanged():
    assert R.api.ReadinessTarget is uvi.ReadinessTarget
    assert R.api.RequirementClass is uvi.RequirementClass


def test_gate_kind_cannot_be_relabelled():
    # There is no gate_kind constructor field; kind comes from the PolicyGate.
    import dataclasses
    names = {f.name for f in dataclasses.fields(GateResult)}
    assert "gate_kind" not in names and "applicable" not in names and "threshold_ref" not in names
    g = gate("x", RequirementClass.MANDATORY, GateStatus.FAIL)
    assert g.gate_kind is RequirementClass.MANDATORY  # derived


def test_applicability_derived_production_only_for_pilot_is_diagnostic():
    g = gate("x", RequirementClass.MANDATORY, GateStatus.FAIL, applicability=PROD, target=ReadinessTarget.PILOT)
    assert g.is_diagnostic and not g.is_blocking


def test_applicability_cannot_be_forged_to_pilot():
    # A production-only PolicyGate can never be made pilot-applicable — no field exists.
    g = gate("x", RequirementClass.MANDATORY, GateStatus.FAIL, applicability=PROD, target=ReadinessTarget.PILOT)
    assert ReadinessTarget.PILOT not in g.policy_gate.applicability
    assert g.applicable is False


# --------------------------------------------------------------------------- #
# GV3R-F1: ready classifications scan all gate_results, not a caller summary
# --------------------------------------------------------------------------- #
def test_deployment_ready_rejects_hidden_mandatory_fail():
    with pytest.raises(ReadinessContractError):
        det(gate_results=[gate("mf", RequirementClass.MANDATORY, GateStatus.FAIL)])


def test_deployment_ready_rejects_hidden_mandatory_indeterminate():
    with pytest.raises(ReadinessContractError):
        det(gate_results=[gate("mi", RequirementClass.MANDATORY, GateStatus.INDETERMINATE)])


def test_pilot_ready_rejects_pilot_applicable_mandatory_fail():
    with pytest.raises(ReadinessContractError):
        det(requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY,
            gate_results=[gate("mf", RequirementClass.MANDATORY, GateStatus.FAIL, applicability=PILOT, target=ReadinessTarget.PILOT)])


def test_pilot_ready_permits_production_only_diagnostic_fail():
    d = det(requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY,
            gate_results=[gate("prod", RequirementClass.MANDATORY, GateStatus.FAIL, applicability=PROD, target=ReadinessTarget.PILOT)])
    assert d.blocking_gate_ids == ()  # diagnostic, not blocking


def test_ready_with_conditions_rejects_mandatory_fail_even_with_active_condition():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    mf = gate("mf", RequirementClass.MANDATORY, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        det(classification=ReadinessClassification.READY_WITH_CONDITIONS, gate_results=[cg, mf], conditions=[cond("c1", "cg")])


def test_blocking_ids_are_derived_and_complete():
    d = det(classification=ReadinessClassification.NOT_READY,
            gate_results=[gate("mf", RequirementClass.MANDATORY, GateStatus.FAIL), gate("ok", RequirementClass.MANDATORY, GateStatus.PASS)])
    assert d.blocking_gate_ids == ("mf",)


# --------------------------------------------------------------------------- #
# GV3R precedence compatibility (§7)
# --------------------------------------------------------------------------- #
def test_precedence_fail_indet_pass_not_ready_ok():
    d = det(classification=ReadinessClassification.NOT_READY,
            gate_results=[gate("a", RequirementClass.MANDATORY, GateStatus.FAIL), gate("b", RequirementClass.MANDATORY, GateStatus.INDETERMINATE), gate("c", RequirementClass.MANDATORY, GateStatus.PASS)])
    assert d.classification is ReadinessClassification.NOT_READY


def test_precedence_fail_dominates_rejects_not_assessable():
    with pytest.raises(ReadinessContractError):
        det(classification=ReadinessClassification.NOT_ASSESSABLE,
            gate_results=[gate("a", RequirementClass.MANDATORY, GateStatus.FAIL), gate("b", RequirementClass.MANDATORY, GateStatus.INDETERMINATE)])


def test_precedence_indet_pass_not_assessable_ok():
    d = det(classification=ReadinessClassification.NOT_ASSESSABLE,
            gate_results=[gate("b", RequirementClass.MANDATORY, GateStatus.INDETERMINATE), gate("c", RequirementClass.MANDATORY, GateStatus.PASS)])
    assert d.classification is ReadinessClassification.NOT_ASSESSABLE


def test_precedence_indet_pass_ready_rejected():
    with pytest.raises(ReadinessContractError):
        det(gate_results=[gate("b", RequirementClass.MANDATORY, GateStatus.INDETERMINATE), gate("c", RequirementClass.MANDATORY, GateStatus.PASS)])


def test_precedence_all_pass_ready_ok():
    d = det(gate_results=[gate("a", RequirementClass.MANDATORY, GateStatus.PASS), gate("b", RequirementClass.MANDATORY, GateStatus.PASS)])
    assert d.classification is ReadinessClassification.DEPLOYMENT_READY


# --------------------------------------------------------------------------- #
# GV3R-F3/F4: READY_WITH_CONDITIONS active coverage at determination time
# --------------------------------------------------------------------------- #
def _rwc(**kw):
    base = dict(classification=ReadinessClassification.READY_WITH_CONDITIONS)
    base.update(kw)
    return det(**base)


def test_rwc_full_active_coverage_ok():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    d = _rwc(gate_results=[cg], conditions=[cond("c1", "cg")])
    assert d.classification is ReadinessClassification.READY_WITH_CONDITIONS


def test_rwc_no_condition_rejected():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[])


@pytest.mark.parametrize("status", [ConditionStatus.PROPOSED, ConditionStatus.EXPIRED, ConditionStatus.REVOKED, ConditionStatus.SATISFIED])
def test_rwc_non_active_condition_rejected(status):
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[cond("c1", "cg", status=status)])


def test_rwc_future_effective_condition_rejected():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[cond("c1", "cg", ef=FUT)])


def test_rwc_expired_window_condition_rejected():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[cond("c1", "cg", ef=T0, exp=datetime(2026, 2, 1, tzinfo=timezone.utc))])


def test_rwc_condition_boundary_at_expiry_rejected():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[cond("c1", "cg", ef=T0, exp=MID)])  # as_of == expiry (exclusive)


def test_rwc_uncovered_concern_rejected():
    cg1 = gate("cg1", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    cg2 = gate("cg2", RequirementClass.CONDITIONAL, GateStatus.INDETERMINATE)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg1, cg2], conditions=[cond("c1", "cg1")])


def test_rwc_wrong_gate_coverage_rejected():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        _rwc(gate_results=[cg], conditions=[cond("c1", "WRONG")])


def test_rwc_all_concerns_covered_ok():
    cg1 = gate("cg1", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    cg2 = gate("cg2", RequirementClass.CONDITIONAL, GateStatus.INDETERMINATE)
    d = _rwc(gate_results=[cg1, cg2], conditions=[cond("c1", "cg1"), cond("c2", "cg2")])
    assert len(d.conditions) == 2


# --------------------------------------------------------------------------- #
# GV3R-F5: DEPLOYMENT_READY rejects unresolved / open conditions
# --------------------------------------------------------------------------- #
def test_deployment_ready_rejects_open_active_condition():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.PASS)  # resolved gate
    with pytest.raises(ReadinessContractError):
        det(gate_results=[cg], conditions=[cond("c1", "cg")])  # but an active open condition remains


def test_deployment_ready_rejects_unresolved_conditional_fail():
    cg = gate("cg", RequirementClass.CONDITIONAL, GateStatus.FAIL)
    with pytest.raises(ReadinessContractError):
        det(gate_results=[cg])


def test_deployment_ready_clean_ok():
    d = det(gate_results=[gate("m", RequirementClass.MANDATORY, GateStatus.PASS)])
    assert d.classification is ReadinessClassification.DEPLOYMENT_READY


def test_deployment_ready_with_satisfied_history_ok():
    d = det(gate_results=[gate("m", RequirementClass.MANDATORY, GateStatus.PASS)],
            conditions=[cond("c1", "cg", status=ConditionStatus.SATISFIED)])
    assert d.classification is ReadinessClassification.DEPLOYMENT_READY


# --------------------------------------------------------------------------- #
# GV3R-F6: every gate must belong to the determination's ReadinessPolicy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_ref", [
    PolicyReference(policy_id="OTHER", policy_family=PolicyFamily.READINESS, version="1", content_digest=D),
    PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="9", content_digest=D),
    PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=hashlib.sha256(b"other").hexdigest()),
])
def test_gate_from_different_readiness_policy_rejected(bad_ref):
    with pytest.raises(ReadinessContractError):
        det(gate_results=[gate("g", RequirementClass.MANDATORY, GateStatus.PASS, ref=bad_ref)])


def test_gate_same_readiness_policy_ok():
    d = det(gate_results=[gate("g", RequirementClass.MANDATORY, GateStatus.PASS, ref=rref())])
    assert len(d.gate_results) == 1
