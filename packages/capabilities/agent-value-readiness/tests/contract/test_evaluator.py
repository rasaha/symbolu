"""Deterministic evaluator tests (GV-3R-b): full PILOT/PRODUCTION decision tables,
precedence, conditional compensation, determinism, and trust/anti-gaming boundary.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import pathlib
from datetime import datetime, timezone

import pytest

import ugence_agent_value_readiness as R
from ugence_governance_contracts.api import AssessmentWindow, MetricClaim, SourceBasis, TransformationMethod
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
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
)
from ugence_agent_value_readiness.api import (
    AdvisoryComposite,
    ConditionSet,
    ConditionStatus,
    EVALUATOR_VERSION,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessClassification,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessRule,
    evaluate_readiness,
)
from decimal import Decimal

D = hashlib.sha256(b"content").hexdigest()
D2 = hashlib.sha256(b"other").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
FUT = datetime(2030, 1, 1, tzinfo=timezone.utc)
PROD = (ReadinessTarget.PRODUCTION,)
PILOT = (ReadinessTarget.PILOT,)
BOTH = (ReadinessTarget.PILOT, ReadinessTarget.PRODUCTION)
WIN = AssessmentWindow(start=T0, end=MID)


def _meta(family, pid):
    return PolicyArtifactMetadata(policy_id=pid, policy_family=family, version="1", content_digest=D,
                                  lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1)


def context():
    return AssessmentContext.bind_policies(
        context_id="ctx1", tenant_id="t1", subject_id="a1",
        geography=GeographyPolicy(metadata=_meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US", reporting_currency="USD", functional_currency="USD"),
        domain=DomainPolicy(metadata=_meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="u"),
        intended_outcome=IntendedOutcomePolicy(metadata=_meta(PolicyFamily.INTENDED_OUTCOME, "i"), target_outcome="o", task_definition="t"),
        as_of=MID)


def pg(gid, kind, appl, compensable=False):
    return PolicyGate(gate_id=gid, category=GateCategory.SAFETY, requirement_class=kind, applicability=appl, conditionally_compensable=compensable)


def policy(*gates, pid="r", targets=BOTH):
    return ReadinessPolicy(metadata=_meta(PolicyFamily.READINESS, pid), gates=tuple(gates), readiness_targets=targets)


def gr(gate, ref, status, target=ReadinessTarget.PRODUCTION):
    return GateResult(policy_gate=gate, readiness_policy_ref=ref, requested_target=target, status=status)


def acond(cid, source):
    return ConditionSet(condition_id=cid, source_gate_or_finding_ref=source, concern_requirement_class=RequirementClass.CONDITIONAL,
                        current_status=ConditionStatus.APPROVED_ACTIVE, approved_mitigation_ref="m", approving_authority_ref="au",
                        accountable_owner="o", scope_exposure_limit="l", monitoring_requirement="mo", evidence_refs=["e"],
                        effective_from=T0, revocation_trigger="rev")


def case(pol, ref, gates, target=ReadinessTarget.PRODUCTION, conditions=(), composite=None, intel=()):
    return ReadinessEvaluationCase(case_id="cs", tenant_id="t1", subject_id="a1", context=context(),
                                   readiness_policy=pol, readiness_policy_ref=ref, requested_target=target,
                                   gate_results=gates, conditions=conditions, advisory_composite=composite, intelligence_results=intel)


def ev(c):
    return evaluate_readiness(c, evaluation_time=MID)


# --------------------------------------------------------------------------- #
# PRODUCTION decision table
# --------------------------------------------------------------------------- #
def test_prod_all_pass_deployment_ready():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)]))
    assert r.classification is ReadinessClassification.DEPLOYMENT_READY
    assert r.trace.selected_rule is ReadinessRule.DEPLOYMENT_READY


def test_prod_mandatory_fail_not_ready():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.FAIL)]))
    assert r.classification is ReadinessClassification.NOT_READY
    assert r.trace.selected_rule is ReadinessRule.NOT_READY_MANDATORY_FAIL


def test_prod_mandatory_indeterminate_not_assessable():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.INDETERMINATE)]))
    assert r.classification is ReadinessClassification.NOT_ASSESSABLE
    assert r.trace.selected_rule is ReadinessRule.NOT_ASSESSABLE_MANDATORY_INDETERMINATE


def test_prod_conditional_fail_covered_ready_with_conditions():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS), gr(c, pol.reference, GateStatus.FAIL)], conditions=[acond("cd", "c")]))
    assert r.classification is ReadinessClassification.READY_WITH_CONDITIONS
    assert r.trace.accepted_condition_ids == ("cd",)


def test_prod_conditional_fail_uncovered_not_ready():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS), gr(c, pol.reference, GateStatus.FAIL)]))
    assert r.classification is ReadinessClassification.NOT_READY
    assert r.trace.selected_rule is ReadinessRule.NOT_READY_CONDITIONAL_UNCOVERED


def test_prod_conditional_noncompensable_not_ready():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=False)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS), gr(c, pol.reference, GateStatus.FAIL)], conditions=[acond("cd", "c")]))
    assert r.classification is ReadinessClassification.NOT_READY
    assert r.trace.selected_rule is ReadinessRule.NOT_READY_CONDITIONAL_NONCOMPENSABLE


def test_prod_conditional_inactive_condition_not_ready():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c)
    future_cond = ConditionSet(condition_id="cd", source_gate_or_finding_ref="c", concern_requirement_class=RequirementClass.CONDITIONAL,
                               current_status=ConditionStatus.APPROVED_ACTIVE, approved_mitigation_ref="m", approving_authority_ref="au",
                               accountable_owner="o", scope_exposure_limit="l", monitoring_requirement="mo", evidence_refs=["e"],
                               effective_from=FUT, revocation_trigger="rev")
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS), gr(c, pol.reference, GateStatus.FAIL)], conditions=[future_cond]))
    assert r.classification is ReadinessClassification.NOT_READY
    assert any("CONDITION_INACTIVE" in s for s in r.trace.rejected_condition_reasons)


# --------------------------------------------------------------------------- #
# PILOT decision table
# --------------------------------------------------------------------------- #
def test_pilot_all_pass_pilot_ready():
    m = pg("m", RequirementClass.MANDATORY, PILOT)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS, ReadinessTarget.PILOT)], target=ReadinessTarget.PILOT))
    assert r.classification is ReadinessClassification.PILOT_READY


def test_pilot_production_only_gate_is_diagnostic_and_not_blocking():
    mp = pg("mp", RequirementClass.MANDATORY, PILOT)
    prodonly = pg("prod", RequirementClass.MANDATORY, PROD)
    pol = policy(mp, prodonly)
    # prod-only gate FAILs but for a PILOT target it is diagnostic -> PILOT_READY
    r = ev(case(pol, pol.reference,
               [gr(mp, pol.reference, GateStatus.PASS, ReadinessTarget.PILOT), gr(prodonly, pol.reference, GateStatus.FAIL, ReadinessTarget.PILOT)],
               target=ReadinessTarget.PILOT))
    assert r.classification is ReadinessClassification.PILOT_READY
    assert r.trace.diagnostic_gate_ids == ("prod",)


def test_pilot_mandatory_fail_not_ready():
    m = pg("m", RequirementClass.MANDATORY, PILOT)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.FAIL, ReadinessTarget.PILOT)], target=ReadinessTarget.PILOT))
    assert r.classification is ReadinessClassification.NOT_READY


def test_pilot_never_emits_production_tiers():
    m = pg("m", RequirementClass.MANDATORY, PILOT)
    c = pg("c", RequirementClass.CONDITIONAL, PILOT, compensable=True)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS, ReadinessTarget.PILOT), gr(c, pol.reference, GateStatus.FAIL, ReadinessTarget.PILOT)],
               target=ReadinessTarget.PILOT, conditions=[acond("cd", "c")]))
    assert r.classification is ReadinessClassification.PILOT_READY  # not READY_WITH_CONDITIONS
    assert len(r.determination.conditions) == 1  # bounded pilot controls carried


# --------------------------------------------------------------------------- #
# FAIL-over-INDETERMINATE precedence
# --------------------------------------------------------------------------- #
def test_fail_dominates_indeterminate():
    a = pg("a", RequirementClass.MANDATORY, PROD)
    b = pg("b", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.MANDATORY, PROD)
    pol = policy(a, b, c)
    r = ev(case(pol, pol.reference, [gr(a, pol.reference, GateStatus.FAIL), gr(b, pol.reference, GateStatus.INDETERMINATE), gr(c, pol.reference, GateStatus.PASS)]))
    assert r.classification is ReadinessClassification.NOT_READY


def test_fail_dominates_even_when_a_gate_is_missing():
    a = pg("a", RequirementClass.MANDATORY, PROD)
    b = pg("b", RequirementClass.MANDATORY, PROD)
    pol = policy(a, b)
    # b missing, a FAIL -> still NOT_READY (fail-closed dominance)
    r = ev(case(pol, pol.reference, [gr(a, pol.reference, GateStatus.FAIL)]))
    assert r.classification is ReadinessClassification.NOT_READY


# --------------------------------------------------------------------------- #
# Omitted-gate attack / completeness
# --------------------------------------------------------------------------- #
def test_missing_mandatory_gate_not_assessable_not_pass():
    a = pg("a", RequirementClass.MANDATORY, PROD)
    b = pg("b", RequirementClass.MANDATORY, PROD)
    pol = policy(a, b)
    r = ev(case(pol, pol.reference, [gr(a, pol.reference, GateStatus.PASS)]))  # b omitted
    assert r.classification is ReadinessClassification.NOT_ASSESSABLE
    assert r.trace.selected_rule is ReadinessRule.NOT_ASSESSABLE_INCOMPLETE


def test_missing_conditional_gate_not_assessable():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)]))  # c omitted
    assert r.classification is ReadinessClassification.NOT_ASSESSABLE


# --------------------------------------------------------------------------- #
# Wrong-policy gate / malformed case -> raises
# --------------------------------------------------------------------------- #
def test_wrong_policy_gate_raises():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    other_ref = PolicyReference(policy_id="OTHER", policy_family=PolicyFamily.READINESS, version="1", content_digest=D)
    with pytest.raises(ReadinessEvaluationError):
        case(pol, pol.reference, [GateResult(policy_gate=m, readiness_policy_ref=other_ref, requested_target=ReadinessTarget.PRODUCTION, status=GateStatus.PASS)])


def test_gate_not_in_policy_raises():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    ghost = pg("ghost", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    with pytest.raises(ReadinessEvaluationError):
        case(pol, pol.reference, [gr(ghost, pol.reference, GateStatus.PASS)])


def test_tampered_embedded_gate_raises():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    tampered = pg("m", RequirementClass.ADVISORY, PROD)  # same id, different kind
    pol = policy(m)
    with pytest.raises(ReadinessEvaluationError):
        case(pol, pol.reference, [gr(tampered, pol.reference, GateStatus.PASS)])


def test_policy_body_ref_mismatch_raises():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    bad_ref = PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D2)
    with pytest.raises(ReadinessEvaluationError):
        case(pol, bad_ref, [gr(m, bad_ref, GateStatus.PASS)])


def test_target_not_governed_raises():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m, targets=PROD)  # production-only policy
    with pytest.raises(ReadinessEvaluationError):
        case(pol, pol.reference, [], target=ReadinessTarget.PILOT)


# --------------------------------------------------------------------------- #
# Missing I/C/A: gate-driven (not a separate invented requirement)
# --------------------------------------------------------------------------- #
def test_missing_indicators_is_gate_driven_not_error():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)]))  # no I/C/A results
    assert r.classification is ReadinessClassification.DEPLOYMENT_READY


def test_evidence_axes_preserved():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    claim = MetricClaim(claim_id="c", tenant_id="t1", subject_id="a1", metric_id="acc", value="0.9", governed_unit="ratio",
                        source_basis=SourceBasis.REPORTED, transformation_method=TransformationMethod.DIRECT)
    ir = IntelligenceFitnessResult(result_id="ir", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i",
                                   dimension=IntelligenceDimension.ACCURACY, claim=claim, requirement_class=RequirementClass.ADVISORY,
                                   applicable_targets=[ReadinessTarget.PRODUCTION], status=GateStatus.PASS)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)], intel=[ir]))
    assert r.determination.intelligence_results[0].claim.source_basis is SourceBasis.REPORTED  # not elevated
    assert r.determination.intelligence_results[0].claim.attestation_status.value == "UNATTESTED"


# --------------------------------------------------------------------------- #
# Composite non-influence
# --------------------------------------------------------------------------- #
def test_composite_min_to_max_same_classification_and_rule():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    lo = AdvisoryComposite(method_id="x", method_version="1", score=Decimal("0"), scale_min=Decimal("0"), scale_max=Decimal("1"), component_result_refs=["r"])
    hi = AdvisoryComposite(method_id="x", method_version="1", score=Decimal("1"), scale_min=Decimal("0"), scale_max=Decimal("1"), component_result_refs=["r"])
    r_lo = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)], composite=lo))
    r_hi = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)], composite=hi))
    assert r_lo.classification is r_hi.classification
    assert r_lo.trace.selected_rule is r_hi.trace.selected_rule
    assert r_lo.determination.advisory_composite is lo  # carried through unchanged


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_determinism_independent_of_input_order():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c1 = pg("cA", RequirementClass.CONDITIONAL, PROD, compensable=True)
    c2 = pg("cB", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c1, c2)
    gates = [gr(m, pol.reference, GateStatus.PASS), gr(c1, pol.reference, GateStatus.FAIL), gr(c2, pol.reference, GateStatus.INDETERMINATE)]
    conds = [acond("z", "cA"), acond("a", "cB")]
    r1 = ev(case(pol, pol.reference, gates, conditions=conds))
    r2 = ev(case(pol, pol.reference, list(reversed(gates)), conditions=list(reversed(conds))))
    assert r1.canonical_digest() == r2.canonical_digest()
    assert r1.trace.reason_codes == r2.trace.reason_codes


def test_evaluation_time_mandatory_and_tzaware():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    c = case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)])
    with pytest.raises(TypeError):
        evaluate_readiness(c)  # evaluation_time is keyword-only and mandatory
    with pytest.raises(ReadinessEvaluationError):
        evaluate_readiness(c, evaluation_time=datetime(2026, 6, 1))  # naive


# --------------------------------------------------------------------------- #
# Trust / advisory / anti-gaming boundary
# --------------------------------------------------------------------------- #
def test_result_is_advisory_and_carries_trust_advisories():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)]))
    assert r.is_advisory is True and r.determination.is_advisory is True
    codes = {rc.value for rc in r.trace.reason_codes}
    assert "ADVISORY_NOT_DEPLOYMENT_AUTHORIZATION" in codes
    assert "ADVISORY_POLICY_AUTHENTICITY_NOT_VERIFIED" in codes
    assert "ADVISORY_EVIDENCE_RETAINS_SOURCE_CLASSIFICATION" in codes


def test_condition_advisory_present_when_conditions_used():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    c = pg("c", RequirementClass.CONDITIONAL, PROD, compensable=True)
    pol = policy(m, c)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS), gr(c, pol.reference, GateStatus.FAIL)], conditions=[acond("cd", "c")]))
    assert "ADVISORY_CONDITION_APPROVAL_NOT_VERIFIED" in {rc.value for rc in r.trace.reason_codes}


def test_no_financial_fields_or_imports_in_services():
    # No financial field on the evaluation shapes.
    fin = ("money", "currency", "roi", "benefit", "cost", "revenue", "multiplier", "price", "npv")
    from ugence_agent_value_readiness.api import ReadinessEvaluationCase as C, EvaluationTrace as Tr, ReadinessEvaluationResult as Rr
    for shape in (C, Tr, Rr):
        for f in dataclasses.fields(shape):
            assert not any(t in f.name.lower() for t in fin), (shape.__name__, f.name)
    # No governed-value / financial import in the services package.
    svc_dir = pathlib.Path(R.__file__).resolve().parent / "services"
    for p in svc_dir.rglob("*.py"):
        tree = ast.parse(p.read_text())
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots.add(node.module.split(".")[0])
        assert "governed_value" not in roots and "ugence_governed_value" not in roots


def test_evaluator_version_stamped_in_trace():
    m = pg("m", RequirementClass.MANDATORY, PROD)
    pol = policy(m)
    r = ev(case(pol, pol.reference, [gr(m, pol.reference, GateStatus.PASS)]))
    assert r.trace.evaluator_version == EVALUATOR_VERSION
