"""Invariant tests for the hiring decision plane (spec §21 steps 2–9).

Focused on the required invariants:
  * Compatibility ≠ Eligibility
  * Overall Fit ≠ Policy
  * AI Recommendation ≠ Binding Authority
  * Missing/unadmitted evidence cannot satisfy a mandatory gate
  * No culture-fit / resilience constructs
  * OPERATING_ENVIRONMENT_COMPATIBILITY / ROLE_SUSTAINABILITY_AND_ADAPTATION remain
  * Role Sustainability & Adaptation stays post-hire unless justified
  * Shared capabilities are ports, not copied implementations
"""

from __future__ import annotations

import inspect
import sys

import pydantic
import pytest

from ugence_ai_hiring.errors import BoundaryViolationError, DomainValidationError
from ugence_ai_hiring.hiring_policy import (
    ActionConstraints,
    DimensionEmphasis,
    HiringPolicy,
    HiringPolicyCompiler,
    MandatoryGateType,
    Requirements,
    RoleRef,
    project_contract,
)
from ugence_ai_hiring.hiring_policy.enums import HiringEvidenceClass
import ugence_ai_hiring.hiring_decision as hd
from ugence_ai_hiring.hiring_decision import (
    AdmittedEvidence,
    AssessmentOutcome,
    AssessmentProvenance,
    CalibrationProposal,
    ContractRef,
    DecisionAuthorityOutcome,
    DecisionDisposition,
    DimensionAssessment,
    EmploymentType,
    GateState,
    HiringActionRequest,
    HiringDecisionCase,
    MandatoryGateEvaluator,
    ProposedAction,
    build_recommendation,
    contract_ref_of,
    derive_eligibility,
)
from ugence_ai_hiring.hiring_decision import CompensationBounds
from ugence_ai_hiring.hiring_decision.enums import CalibrationTarget, ReviewCheckpoint
from ugence_ai_hiring.hiring_decision.ports import (
    ActionAuthorizationPort,
    DecisionAuthorityPort,
    EvidenceAdmissionPort,
    ReconciliationPort,
    RuntimeAssurancePort,
)

from .hiring_decision_fakes import (
    FakeActionAuthorizationPort,
    FakeDecisionAuthorityPort,
    FakeEvidenceAdmissionPort,
    FakeReconciliationPort,
    FakeRuntimeAssurancePort,
)

PROV = AssessmentProvenance(engine="compat-engine-v1", model_id="m", model_version="1")


# --- fixtures -------------------------------------------------------------
def build_contract():
    policy = HiringPolicy(
        policy_id="pol-arch",
        role=RoleRef(job_definition_id="jd-arch", title="Senior Architect", seniority_level="L5"),
        requirements=Requirements(
            required_skills=("AWS", "Kubernetes"),
            mandatory=(MandatoryGateType.REQUIRED_SKILLS, MandatoryGateType.SECURITY_CLEARANCE),
            operating_environment="HEALTHCARE",
            emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY), ("LEADERSHIP", DimensionEmphasis.SECONDARY)),
        ),
        action_constraints=ActionConstraints(
            salary_ceiling=220000, approved_level="L5",
            approved_roles=("Senior Architect",), allowed_locations=("NYC",),
        ),
        approval_chain=("Hiring Manager", "Director", "VP Eng"),
        authored_by="hr-jane",
    )
    ir = HiringPolicyCompiler().compile(policy)
    hdc = project_contract(ir, job_definition_id="jd-arch")
    return hdc, ir


def high_scores():
    return (
        DimensionAssessment(dimension="TECHNICAL", outcome=AssessmentOutcome.SCORED, score=92,
                            confidence=0.9, evidence_refs=("ln-e1",), provenance=PROV),
        DimensionAssessment(dimension="LEADERSHIP", outcome=AssessmentOutcome.SCORED, score=85,
                            confidence=0.8, evidence_refs=("ln-e1",), provenance=PROV),
    )


def ev(evidence_id, cls, admitted, attrs):
    return AdmittedEvidence(evidence_id=evidence_id, evidence_class=cls, admitted=admitted,
                            lineage_node_id=f"ln-{evidence_id}", attributes=attrs)


# --- Compatibility ≠ Eligibility -----------------------------------------
def test_high_compatibility_cannot_buy_back_a_failed_gate():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    evidence = (
        ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),
        ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": False}),
    )
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = derive_eligibility(gr, cref)
    assert elig.status.value == "NOT_ELIGIBLE"
    rec = build_recommendation(
        candidate_id="c1", role_id="jd-arch", contract_ref=cref, admitted_evidence=evidence,
        dimension_assessments=high_scores(), gate_results=gr, eligibility=elig,
    )
    assert rec.recommendation.value == "NOT_ELIGIBLE"
    assert rec.proposed_action is None


def test_eligibility_pending_when_gate_indeterminate():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    # only the skills gate is decidable; clearance evidence absent → INDETERMINATE
    evidence = (ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),)
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = derive_eligibility(gr, cref)
    assert elig.status.value == "ELIGIBILITY_PENDING"


def test_eligibility_derives_from_gates_only_no_score_input():
    sig = inspect.signature(derive_eligibility)
    assert set(sig.parameters) == {"gate_results", "contract_ref"}


# --- Overall Fit ≠ Policy -------------------------------------------------
def test_importing_decision_plane_does_not_load_analytics():
    # fresh import state check: the plane must never pull in the analytics path
    assert "ugence_ai_hiring.hiring_decision.analytics" not in sys.modules


@pytest.mark.parametrize(
    "module",
    [
        "ugence_ai_hiring.hiring_decision.gates",
        "ugence_ai_hiring.hiring_decision.eligibility",
        "ugence_ai_hiring.hiring_decision.recommendation",
        "ugence_ai_hiring.hiring_decision.decision_case",
        "ugence_ai_hiring.hiring_policy.compiler",
    ],
)
def test_policy_and_gate_code_never_references_analytics(module):
    import importlib

    src = inspect.getsource(importlib.import_module(module))
    import_lines = [ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    # no import of the analytics module …
    assert not any("analytics" in ln for ln in import_lines)
    # … and no reference to any analytics symbol (prose like "analytics-only" is fine)
    assert "OverallFit" not in src
    assert "compute_overall_fit" not in src


def test_build_recommendation_takes_no_overall_fit_input():
    params = set(inspect.signature(build_recommendation).parameters)
    assert not any("fit" in p or "overall" in p for p in params)


def test_overall_fit_high_while_not_eligible():
    from ugence_ai_hiring.hiring_decision.analytics import compute_overall_fit

    hdc, ir = build_contract()
    result = compute_overall_fit(high_scores(), ir.dimension_weights)
    assert result.range.value == "HIGH"  # analytics says HIGH …
    # … yet eligibility (a separate object) is independent and can be NOT_ELIGIBLE
    cref = contract_ref_of(hdc)
    evidence = (ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": False}),
                ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}))
    elig = derive_eligibility(MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence), cref)
    assert elig.status.value == "NOT_ELIGIBLE"


# --- AI Recommendation ≠ Binding Authority -------------------------------
def test_recommendation_is_advisory_and_ai():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    evidence = (ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),
                ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": True}))
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = derive_eligibility(gr, cref)
    rec = build_recommendation(candidate_id="c1", role_id="jd-arch", contract_ref=cref,
                               admitted_evidence=evidence, dimension_assessments=high_scores(),
                               gate_results=gr, eligibility=elig)
    assert rec.actor_type == "AI"
    assert rec.advisory_only is True
    assert rec.binding is False


def test_binding_decision_cannot_be_ai():
    from ugence_ai_hiring.hiring_decision.decision_case import BindingDecision

    with pytest.raises(pydantic.ValidationError):
        BindingDecision(recommendation_id="r1", disposition=DecisionDisposition.ADVANCE,
                        decided_by="ai-engine", authority_id="ai-engine", actor_type="AI")


def test_case_refuses_binding_when_decision_authority_not_binding():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    evidence = (ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),
                ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": True}))
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = derive_eligibility(gr, cref)
    rec = build_recommendation(candidate_id="c1", role_id="jd-arch", contract_ref=cref,
                               admitted_evidence=evidence, dimension_assessments=high_scores(),
                               gate_results=gr, eligibility=elig)
    case = (HiringDecisionCase(candidate_id="c1", role_id="jd-arch", contract_ref=cref)
            .record_evidence(evidence).record_assessments(high_scores())
            .record_gate_results(gr, elig).record_recommendation(rec))
    advisory_only = DecisionAuthorityOutcome(recommendation_id=rec.recommendation_id,
                                             disposition=DecisionDisposition.ADVANCE, binding=False,
                                             authority_id="hm-alex")
    with pytest.raises(BoundaryViolationError):
        case.record_decision(advisory_only)


def test_case_binds_only_via_decision_authority_outcome():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    evidence = (ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),
                ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": True}))
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    elig = derive_eligibility(gr, cref)
    rec = build_recommendation(candidate_id="c1", role_id="jd-arch", contract_ref=cref,
                               admitted_evidence=evidence, dimension_assessments=high_scores(),
                               gate_results=gr, eligibility=elig)
    case = (HiringDecisionCase(candidate_id="c1", role_id="jd-arch", contract_ref=cref)
            .record_evidence(evidence).record_assessments(high_scores())
            .record_gate_results(gr, elig).record_recommendation(rec))
    da = FakeDecisionAuthorityPort(disposition=DecisionDisposition.ADVANCE, binding=True)
    outcome = da.adjudicate(rec.recommendation_id, cref)
    case = case.record_decision(outcome)
    assert case.decision is not None
    assert case.decision.actor_type == "HUMAN"
    assert case.status.value == "DECIDED"


# --- missing/unadmitted evidence cannot satisfy a gate -------------------
def test_no_evidence_yields_indeterminate():
    hdc, _ = build_contract()
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, ())
    assert all(g.state is GateState.INDETERMINATE for g in gr)


def test_unadmitted_evidence_cannot_satisfy_a_gate():
    hdc, _ = build_contract()
    # evidence asserts satisfaction but is NOT admitted → must be ignored
    evidence = (
        ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, False, {"required_skills_met": True}),
        ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, False, {"clearance_active": True}),
    )
    gr = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    assert all(g.state is GateState.INDETERMINATE for g in gr)


def test_gate_evaluation_is_deterministic():
    hdc, _ = build_contract()
    evidence = (ev("e1", HiringEvidenceClass.CODING_ASSESSMENT, True, {"required_skills_met": True}),
                ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": True}))
    a = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    b = MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)
    assert a == b


def test_explicit_negative_evidence_fails_gate():
    hdc, _ = build_contract()
    evidence = (ev("e2", HiringEvidenceClass.BACKGROUND_CHECK, True, {"clearance_active": False}),)
    gr = {g.gate_type.value: g for g in MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, evidence)}
    assert gr["SECURITY_CLEARANCE"].state is GateState.FAIL


# --- no culture-fit / resilience; approved dimensions remain -------------
@pytest.mark.parametrize("bad", ["CULTURE_FIT", "RESILIENCE"])
def test_forbidden_dimension_rejected_in_assessment(bad):
    with pytest.raises(DomainValidationError):
        DimensionAssessment(dimension=bad, outcome=AssessmentOutcome.SCORED, score=80,
                            confidence=0.8, evidence_refs=("ln-1",), provenance=PROV)


def test_operating_environment_dimension_allowed():
    a = DimensionAssessment(dimension="OPERATING_ENVIRONMENT_COMPATIBILITY",
                            outcome=AssessmentOutcome.SCORED, score=75, confidence=0.7,
                            evidence_refs=("ln-1",), provenance=PROV)
    assert a.dimension == "OPERATING_ENVIRONMENT_COMPATIBILITY"


# --- role sustainability stays post-hire unless justified ----------------
def test_role_sustainability_scored_pre_hire_requires_justification():
    with pytest.raises(DomainValidationError):
        DimensionAssessment(dimension="ROLE_SUSTAINABILITY_AND_ADAPTATION",
                            outcome=AssessmentOutcome.SCORED, score=70, confidence=0.6,
                            evidence_refs=("ln-1",), provenance=PROV)


def test_role_sustainability_insufficient_evidence_always_ok():
    a = DimensionAssessment(dimension="ROLE_SUSTAINABILITY_AND_ADAPTATION",
                            outcome=AssessmentOutcome.INSUFFICIENT_EVIDENCE, confidence=0.2,
                            provenance=PROV)
    assert a.score is None


def test_role_sustainability_bounded_pre_hire_with_justification_ok():
    a = DimensionAssessment(dimension="ROLE_SUSTAINABILITY_AND_ADAPTATION",
                            outcome=AssessmentOutcome.SCORED, score=68, confidence=0.6,
                            evidence_refs=("ln-jobrel-1",), pre_hire_justified=True, provenance=PROV)
    assert a.pre_hire_justified is True


# --- ports are protocols; package runs standalone with fakes -------------
def test_fakes_satisfy_port_protocols():
    assert isinstance(FakeEvidenceAdmissionPort(), EvidenceAdmissionPort)
    assert isinstance(FakeDecisionAuthorityPort(), DecisionAuthorityPort)
    assert isinstance(FakeActionAuthorizationPort(), ActionAuthorizationPort)
    assert isinstance(FakeRuntimeAssurancePort(), RuntimeAssurancePort)
    assert isinstance(FakeReconciliationPort(), ReconciliationPort)


def test_decision_plane_import_pulls_no_shared_service():
    # importing the plane must not load any shared platform provider module
    for name in list(sys.modules):
        assert not name.startswith("ugence_tap_provider")
        assert not name.startswith("ugence_actiongate_provider")


# --- action request → CER payload ----------------------------------------
def test_action_request_cer_payload_carries_provenance_and_fields():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    areq = HiringActionRequest(
        candidate_id="c1", role_id="jd-arch", level="L5",
        compensation=CompensationBounds(salary_ceiling=220000, currency="USD"),
        location="NYC", employment_type=EmploymentType.FULL_TIME, contract_ref=cref,
        decision_id="hdec-1", recommendation_id="hrec-1",
    )
    payload = areq.to_cer_payload()
    assert payload["subject"] == {"candidate_id": "c1", "role_id": "jd-arch"}
    assert payload["action"]["level"] == "L5"
    assert payload["action"]["salary_ceiling"] == 220000
    assert payload["action"]["employment_type"] == "FULL_TIME"
    prov = payload["provenance"]
    assert prov["contract_id"] == cref.contract_id
    assert prov["ir_digest"] == cref.ir_digest
    assert prov["decision_id"] == "hdec-1"
    assert prov["recommendation_id"] == "hrec-1"


# --- calibration proposes contract/policy versions, not weights ----------
def test_calibration_proposal_recompiles_policy_not_weights():
    cref = ContractRef(contract_id="hdc-1", version=1, ir_digest="d" * 64)
    proposal = CalibrationProposal(
        source_case_id="hcase-1", contract_ref=cref,
        targets=(CalibrationTarget.DIMENSION_WEIGHTS, CalibrationTarget.CONFIDENCE_THRESHOLDS),
        rationale="Growth over-predicted at 6 months across cohort", recompile_policy_id="pol-arch",
        proposed_contract_version=2,
    )
    assert proposal.recompile_policy_id == "pol-arch"
    assert proposal.proposed_contract_version == 2


def test_calibration_requires_a_policy_to_recompile():
    cref = ContractRef(contract_id="hdc-1", version=1, ir_digest="d" * 64)
    with pytest.raises(DomainValidationError):
        CalibrationProposal(source_case_id="hcase-1", contract_ref=cref,
                            targets=(CalibrationTarget.MANDATORY_GATES,), rationale="x",
                            recompile_policy_id="   ", proposed_contract_version=2)


def test_calibration_version_must_advance():
    cref = ContractRef(contract_id="hdc-1", version=3, ir_digest="d" * 64)
    with pytest.raises(DomainValidationError):
        CalibrationProposal(source_case_id="hcase-1", contract_ref=cref,
                            targets=(CalibrationTarget.MANDATORY_GATES,), rationale="x",
                            recompile_policy_id="pol-arch", proposed_contract_version=3)


# --- standalone review lifecycle -----------------------------------------
def test_review_and_reconciliation_with_fakes():
    hdc, _ = build_contract()
    cref = contract_ref_of(hdc)
    from ugence_ai_hiring.hiring_decision import ReviewObservation, ReviewRecord
    from ugence_ai_hiring.hiring_decision.enums import OutcomeEvidenceType

    review = ReviewRecord(
        case_id="hcase-1", checkpoint=ReviewCheckpoint.SIX_MONTH, contract_ref=cref,
        observations=(ReviewObservation(dimension="TECHNICAL", predicted=92, observed=95,
                                        outcome_evidence=(OutcomeEvidenceType.DELIVERY,)),),
    )
    assert review.observations[0].delta == 3.0
    recon = FakeReconciliationPort().reconcile("hcase-1", review.review_id)
    assert recon.case_id == "hcase-1"
