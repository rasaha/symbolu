"""Tests for the post-hire calibration loop (spec §21 step 6).

Covers review timing, provenance, immutable historical decisions, cohort
aggregation, calibration deltas, proposal generation, approval-before-recompile,
version advancement, and prohibition of direct policy mutation.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

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
import ugence_ai_hiring.hiring_calibration as hc
from ugence_ai_hiring.hiring_decision.enums import CalibrationTarget

HIRE = datetime(2026, 1, 1, tzinfo=timezone.utc)
PROV = hd.AssessmentProvenance(engine="compat-engine-v1")


def build_policy():
    return HiringPolicy(
        policy_id="pol-arch",
        role=RoleRef(job_definition_id="jd-arch", title="Senior Architect", seniority_level="L5"),
        requirements=Requirements(required_skills=("AWS",), mandatory=(MandatoryGateType.REQUIRED_SKILLS,),
            emphasis=(("TECHNICAL", DimensionEmphasis.PRIMARY), ("LEADERSHIP", DimensionEmphasis.SECONDARY))),
        action_constraints=ActionConstraints(salary_ceiling=220000, approved_level="L5",
            approved_roles=("Senior Architect",), allowed_locations=("NYC",)),
        approval_chain=("Hiring Manager", "Director", "VP Eng"), authored_by="hr",
    )


def hired_case(cid, *, tech_pred=90, disposition=hd.DecisionDisposition.ADVANCE):
    policy = build_policy()
    ir = HiringPolicyCompiler().compile(policy)
    hdc = project_contract(ir, job_definition_id="jd-arch")
    cref = hd.contract_ref_of(hdc)
    assess = (hd.DimensionAssessment(dimension="TECHNICAL", outcome=hd.AssessmentOutcome.SCORED,
                                     score=tech_pred, confidence=0.9, evidence_refs=("ln-1",), provenance=PROV),
              hd.DimensionAssessment(dimension="LEADERSHIP", outcome=hd.AssessmentOutcome.SCORED,
                                     score=85, confidence=0.7, evidence_refs=("ln-1",), provenance=PROV))
    ev = (hd.AdmittedEvidence(evidence_id="e1", evidence_class=HiringEvidenceClass.CODING_ASSESSMENT,
                              admitted=True, lineage_node_id="ln-1", attributes={"required_skills_met": True}),)
    gr = hd.MandatoryGateEvaluator().evaluate(hdc.mandatory_gates, ev)
    elig = hd.derive_eligibility(gr, cref)
    pa = hd.ProposedAction(level="L5", salary=200000, role="Senior Architect", location="NYC",
                           employment_type=hd.EmploymentType.FULL_TIME)
    rec = hd.build_recommendation(candidate_id=cid, role_id="jd-arch", contract_ref=cref, admitted_evidence=ev,
        dimension_assessments=assess, gate_results=gr, eligibility=elig, proposed_action=pa,
        action_constraints=hdc.action_constraints)
    case = (hd.HiringDecisionCase(case_id="case-" + cid, candidate_id=cid, role_id="jd-arch", contract_ref=cref)
            .record_evidence(ev).record_assessments(assess).record_gate_results(gr, elig).record_recommendation(rec))
    out = hd.DecisionAuthorityOutcome(recommendation_id=rec.recommendation_id, disposition=disposition,
                                      binding=True, authority_id="hm-alex", rationale_job_related="x")
    return case.record_decision(out), hdc, policy


def overpredicted_review(observed=62, dim="TECHNICAL"):
    return hd.ReviewObservation(dimension=dim, predicted=90, observed=observed,
                                outcome_evidence=(hd.OutcomeEvidenceType.DELIVERY,
                                                  hd.OutcomeEvidenceType.MANAGER_REVIEW))


# --- review timing --------------------------------------------------------
def test_review_recorded_within_window():
    case, _hdc, _p = hired_case("c1")
    svc = hc.PostHireReviewService()
    case2, review = svc.record_review(case, hd.ReviewCheckpoint.THREE_MONTH, (overpredicted_review(),),
                                      hire_date=HIRE, review_date=HIRE + timedelta(days=90))
    assert review.checkpoint is hd.ReviewCheckpoint.THREE_MONTH
    assert len(case2.reviews) == 1


def test_review_outside_window_rejected():
    case, _hdc, _p = hired_case("c1")
    with pytest.raises(hc.ReviewTimingError):
        hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.ONE_MONTH, (overpredicted_review(),),
                                                 hire_date=HIRE, review_date=HIRE + timedelta(days=200))


def test_duplicate_checkpoint_rejected():
    case, _hdc, _p = hired_case("c1")
    svc = hc.PostHireReviewService()
    case2, _ = svc.record_review(case, hd.ReviewCheckpoint.THREE_MONTH, (overpredicted_review(),))
    with pytest.raises(hc.DuplicateReviewError):
        svc.record_review(case2, hd.ReviewCheckpoint.THREE_MONTH, (overpredicted_review(),))


def test_non_hired_case_rejected():
    case, _hdc, _p = hired_case("c1", disposition=hd.DecisionDisposition.HOLD)
    with pytest.raises(hc.NotHiredError):
        hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.ONE_MONTH, (overpredicted_review(),))


# --- job-related, observable evidence only -------------------------------
@pytest.mark.parametrize("bad", ["CULTURE_FIT", "RESILIENCE"])
def test_forbidden_dimension_rejected_in_review(bad):
    case, _hdc, _p = hired_case("c1")
    obs = (hd.ReviewObservation(dimension=bad, observed=50, outcome_evidence=(hd.OutcomeEvidenceType.DELIVERY,)),)
    with pytest.raises(Exception):
        hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.ONE_MONTH, obs)


def test_observed_value_requires_job_related_evidence():
    case, _hdc, _p = hired_case("c1")
    obs = (hd.ReviewObservation(dimension="TECHNICAL", predicted=90, observed=62),)  # no outcome_evidence
    with pytest.raises(Exception):
        hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.THREE_MONTH, obs)


# --- immutable historical decision ---------------------------------------
def test_review_does_not_change_historical_decision():
    case, _hdc, _p = hired_case("c1")
    before = (case.decision, case.recommendation, case.eligibility)
    case2, _ = hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.THREE_MONTH, (overpredicted_review(),))
    assert (case2.decision, case2.recommendation, case2.eligibility) == before
    assert case2.history[:len(case.history)] == case.history  # append-only


# --- role sustainability accumulates post-hire ---------------------------
def test_role_sustainability_accumulates_across_horizons():
    case, _hdc, _p = hired_case("c1")
    svc = hc.PostHireReviewService()
    rs = lambda v: hd.ReviewObservation(dimension="ROLE_SUSTAINABILITY_AND_ADAPTATION", observed=v,
                                        outcome_evidence=(hd.OutcomeEvidenceType.RETENTION,))
    case, _ = svc.record_review(case, hd.ReviewCheckpoint.THREE_MONTH, (rs(70),))
    case, _ = svc.record_review(case, hd.ReviewCheckpoint.SIX_MONTH, (rs(75),))
    report = hc.build_calibration_report((case,), policy_id="pol-arch", now=HIRE)
    horizons = {d.horizon for d in report.deltas if d.dimension == "ROLE_SUSTAINABILITY_AND_ADAPTATION"}
    assert hd.ReviewCheckpoint.THREE_MONTH in horizons and hd.ReviewCheckpoint.SIX_MONTH in horizons


# --- cohort aggregation + deltas -----------------------------------------
def build_cohort(n=3, observed=62):
    svc = hc.PostHireReviewService()
    cases = []
    for i in range(n):
        case, _hdc, _p = hired_case(f"c{i}")
        case, _ = svc.record_review(case, hd.ReviewCheckpoint.THREE_MONTH, (overpredicted_review(observed=observed),))
        cases.append(case)
    return tuple(cases)


def test_cohort_delta_direction_overprediction():
    report = hc.build_calibration_report(build_cohort(observed=62), policy_id="pol-arch", now=HIRE)
    tech = [d for d in report.deltas if d.dimension == "TECHNICAL"][0]
    assert tech.predicted_mean == 90 and tech.observed_mean == 62
    assert tech.delta == -28 and tech.direction is hc.CalibrationDirection.OVERPREDICTION


def test_cohort_delta_direction_accurate():
    report = hc.build_calibration_report(build_cohort(observed=92), policy_id="pol-arch", now=HIRE)
    tech = [d for d in report.deltas if d.dimension == "TECHNICAL"][0]
    assert tech.direction is hc.CalibrationDirection.ACCURATE


def test_cohort_mismatch_rejected():
    case, _hdc, _p = hired_case("c1")
    case2 = case.model_copy(update={"contract_ref": case.contract_ref.model_copy(update={"version": 2})})
    with pytest.raises(hc.CohortMismatchError):
        hc.build_calibration_report((case, case2), policy_id="pol-arch")


def test_cohort_key_has_no_protected_attribute_fields():
    fields = set(hc.CohortKey.model_fields)
    assert fields == {"role_id", "policy_id", "contract_id", "contract_version", "ir_digest"}


# --- proposal generation --------------------------------------------------
def test_proposal_generated_from_overprediction_signal():
    report = hc.build_calibration_report(build_cohort(observed=62), policy_id="pol-arch", now=HIRE)
    proposal = hc.generate_calibration_proposal(report, required_approver="head-of-talent", policy_id="pol-arch")
    assert CalibrationTarget.CONFIDENCE_THRESHOLDS in proposal.targets
    assert CalibrationTarget.DIMENSION_WEIGHTS in proposal.targets
    assert proposal.proposed_contract_version == report.cohort_key.contract_version + 1
    assert proposal.required_approver == "head-of-talent"
    assert report.report_id in proposal.supporting_evidence


def test_missing_evidence_signals_evidence_requirement_change():
    case, _hdc, _p = hired_case("c1")
    obs = (overpredicted_review(),
           hd.ReviewObservation(dimension="LEADERSHIP", observed=None))  # missing observed
    case, _ = hc.PostHireReviewService().record_review(case, hd.ReviewCheckpoint.THREE_MONTH, obs)
    report = hc.build_calibration_report((case,), policy_id="pol-arch", now=HIRE)
    assert report.missing_evidence.get("LEADERSHIP", 0) >= 1
    proposal = hc.generate_calibration_proposal(report, required_approver="ht", policy_id="pol-arch")
    assert CalibrationTarget.EVIDENCE_REQUIREMENTS in proposal.targets


def test_no_signal_raises():
    report = hc.build_calibration_report(build_cohort(observed=92), policy_id="pol-arch", now=HIRE)
    with pytest.raises(hc.NoCalibrationSignalError):
        hc.generate_calibration_proposal(report, required_approver="ht", policy_id="pol-arch")


# --- approval-before-recompile + version advancement ---------------------
def _proposal_and_policy():
    report = hc.build_calibration_report(build_cohort(observed=62), policy_id="pol-arch", now=HIRE)
    proposal = hc.generate_calibration_proposal(report, required_approver="head-of-talent", policy_id="pol-arch")
    return report, proposal, build_policy()


def test_recompile_requires_approval():
    report, proposal, policy = _proposal_and_policy()
    with pytest.raises(hc.CalibrationApprovalError):
        hc.CalibrationApprovalService().recompile(proposal, policy, job_definition_id="jd-arch")


def test_wrong_approver_rejected():
    _report, proposal, _policy = _proposal_and_policy()
    with pytest.raises(hc.CalibrationApprovalError):
        hc.CalibrationApprovalService().approve(proposal, approver="random-person")


def test_approved_recompile_advances_version_and_reissues_contract():
    report, proposal, policy = _proposal_and_policy()
    svc = hc.CalibrationApprovalService()
    approved = svc.approve(proposal, approver="head-of-talent")
    assert approved.status == hc.ProposalStatus.APPROVED.value
    result = svc.recompile(approved, policy, job_definition_id="jd-arch", report=report)
    assert result.contract.version == proposal.proposed_contract_version
    assert result.contract.version > proposal.contract_ref.version
    assert result.proposal.status == hc.ProposalStatus.RECOMPILED.value


def test_provenance_links_the_full_chain():
    report, proposal, policy = _proposal_and_policy()
    svc = hc.CalibrationApprovalService()
    approved = svc.approve(proposal, approver="head-of-talent")
    result = svc.recompile(approved, policy, job_definition_id="jd-arch", report=report)
    p = result.provenance
    assert p.decision_case_ids == report.case_ids
    assert p.report_id == report.report_id
    assert p.proposal_id == proposal.proposal_id
    assert p.next_contract_version == result.contract.version
    assert p.current_contract_ref.version == report.cohort_key.contract_version


# --- prohibition of direct policy mutation -------------------------------
def test_recompile_produces_new_contract_without_mutating_original():
    report, proposal, policy = _proposal_and_policy()
    original = project_contract(HiringPolicyCompiler().compile(policy), job_definition_id="jd-arch")
    svc = hc.CalibrationApprovalService()
    approved = svc.approve(proposal, approver="head-of-talent")
    result = svc.recompile(approved, policy, job_definition_id="jd-arch")
    assert result.contract.version != original.version
    assert original.version == 1  # unchanged


def test_calibration_targets_are_policy_artifacts_not_model_params():
    from ugence_ai_hiring.hiring_decision.reviews import CalibrationProposal

    # targets are declarative policy artifacts, never neural/model parameters
    values = {t.value for t in CalibrationTarget}
    assert values == {
        "DIMENSION_WEIGHTS", "CONFIDENCE_THRESHOLDS", "EVIDENCE_REQUIREMENTS",
        "MANDATORY_GATES", "ACTION_CONSTRAINTS",
    }
    # a proposal names targets + rationale; it carries no numeric weight/parameter field
    for field in CalibrationProposal.model_fields:
        assert "weight" not in field.lower()
        assert "param" not in field.lower()


# --- Overall Fit stays analytics-only in this path -----------------------
def test_proposal_generation_ignores_overall_fit():
    cohort = build_cohort(observed=62)
    with_ofi = hc.build_calibration_report(cohort, policy_id="pol-arch",
                                           overall_fit_descriptive={"mean": 88.0, "range": "HIGH"}, now=HIRE)
    without = hc.build_calibration_report(cohort, policy_id="pol-arch", now=HIRE)
    p1 = hc.generate_calibration_proposal(with_ofi, required_approver="ht", policy_id="pol-arch")
    p2 = hc.generate_calibration_proposal(without, required_approver="ht", policy_id="pol-arch")
    assert set(p1.targets) == set(p2.targets)


def test_proposal_and_report_modules_do_not_import_analytics():
    import importlib
    for module in ("ugence_ai_hiring.hiring_calibration.proposal",
                   "ugence_ai_hiring.hiring_calibration.report",
                   "ugence_ai_hiring.hiring_calibration.review_service"):
        src = inspect.getsource(importlib.import_module(module))
        import_lines = [ln for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
        assert not any("analytics" in ln for ln in import_lines)
        assert "OverallFit" not in src and "compute_overall_fit" not in src


# --- standalone -----------------------------------------------------------
def test_calibration_plane_imports_standalone():
    import sys
    for name in list(sys.modules):
        assert not name.startswith("ugence_tap_provider")
        assert not name.startswith("ugence_actiongate_provider")
