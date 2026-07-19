"""
Stage-2 tests: per-concept violating/clean/label-ablation/content-ablation/
baseline/false-positive/provenance-edge, plus the overall verdict.
"""

import pytest

from agentic.enterprise_ontology.events import (
    DecisionEffect, EnterpriseEventEnvelope, VerticalDecision,
)
from agentic.enterprise_ontology.scenarios._helpers import AR, EO, L, V, VS, rec
from agentic.enterprise_ontology.stage2.ablation import ablate_content, ablate_label
from agentic.enterprise_ontology.stage2.evaluation import run_stage2_evaluation
from agentic.enterprise_ontology.stage2.evidence import (
    CognitionEvidence, IntegrationEvidence, PotentialEvidence, ReasoningEvidence,
    StateAssertion,
)
from agentic.enterprise_ontology.stage2.failures import Concept, Stage2FailureClass as FC
from agentic.enterprise_ontology.stage2.invariants import run_concept_invariants
from agentic.enterprise_ontology.stage2.scenarios import all_stage2_scenarios


def _classes(findings):
    return {f.failure_class for f in findings}


# --- each scenario: violating triggers expected, clean is a false-positive guard

@pytest.mark.parametrize("s", all_stage2_scenarios(), ids=lambda s: s.name)
def test_violating_triggers_expected(s):
    got = _classes(run_concept_invariants(s.concept, s.violating))
    missing = s.expected - got
    assert not missing, f"{s.name} missing {[m.value for m in missing]}"


@pytest.mark.parametrize("s", all_stage2_scenarios(), ids=lambda s: s.name)
def test_clean_case_no_false_positives(s):
    assert run_concept_invariants(s.concept, s.clean) == []


# --- the two ablations, per concept -----------------------------------------

@pytest.mark.parametrize("s", all_stage2_scenarios(), ids=lambda s: s.name)
def test_label_ablation_preserves_findings(s):
    # Retagging the layer must NOT change detection — the label is not the driver.
    full = run_concept_invariants(s.concept, s.violating)
    ablated = run_concept_invariants(s.concept, ablate_label(s.violating, s.concept))
    assert _classes(ablated) == _classes(full) and len(ablated) == len(full)


@pytest.mark.parametrize("s", all_stage2_scenarios(), ids=lambda s: s.name)
def test_content_ablation_removes_findings(s):
    # Removing the semantic content must eliminate detection — content IS the driver.
    ablated = run_concept_invariants(s.concept, ablate_content(s.violating, s.concept))
    assert ablated == []


@pytest.mark.parametrize("s", all_stage2_scenarios(), ids=lambda s: s.name)
def test_ontology_surfaces_beyond_baseline(s):
    got = {f.failure_class.value for f in run_concept_invariants(s.concept, s.violating)}
    baseline = {b.value for b in s.baseline_reproducible}
    assert got - baseline, f"{s.name} added nothing beyond baseline"


# --- provenance / authority edge cases (must NOT over-flag) ------------------

def test_cognition_advisory_with_authority_basis_is_not_escalation():
    cog = rec("cog", L.COGNITION, V.MARKETING,
              CognitionEvidence("m", "1", "expand", 0.9, 0.1, "r", "approved"),
              origin=EO.DERIVED_INTERPRETIVE, verify=VS.INFERRED, authority=AR.ADVISORY)
    auth = rec("auth", L.AGENCY, V.MARKETING, {"ok": True},
               origin=EO.DERIVED_DETERMINISTIC, verify=VS.VERIFIED, authority=AR.AUTHORITY_BEARING)
    d = VerticalDecision("d", V.MARKETING, DecisionEffect.ALLOW, "x",
                         supporting_record_ids=("cog", "auth"))
    env = EnterpriseEventEnvelope("e", "t", (cog, auth), decisions=(d,))
    got = _classes(run_concept_invariants(Concept.COGNITION, env))
    assert FC.ADVISORY_AUTHORITY_ESCALATION not in got  # advisory is not the SOLE basis


def test_potential_approval_present_is_clean():
    pe = PotentialEvidence(
        available_capabilities=("deploy_production",),
        permitted_capabilities=(), prohibited_capabilities=(),
        approval_required_capabilities=("deploy_production",),
        approvals_present=("deploy_production",))
    env = EnterpriseEventEnvelope("e", "t", (rec("p", L.POTENTIAL, V.IT, pe),))
    got = _classes(run_concept_invariants(Concept.POTENTIAL, env))
    assert FC.POTENTIAL_AUTHORITY_MISMATCH not in got


def test_reasoning_complete_override_is_clean():
    re_ = ReasoningEvidence("d", ("R1",), ("p@1",), ("a<-b",), (), ("OV",))
    env = EnterpriseEventEnvelope("e", "t", (rec("r", L.REASONING, V.EXECUTIVE, re_),))
    got = _classes(run_concept_invariants(Concept.REASONING, env))
    assert FC.UNJUSTIFIED_OVERRIDE not in got and FC.REASONING_PROVENANCE_GAP not in got


def test_integration_unmet_but_not_marked_complete_is_dependency_not_premature():
    ie = IntegrationEvidence(
        required_closure_conditions=("c1",), satisfied_closure_conditions=(),
        marked_complete=False)
    env = EnterpriseEventEnvelope("e", "t", (rec("i", L.INTEGRATION, V.OPERATIONS, ie),))
    got = _classes(run_concept_invariants(Concept.INTEGRATION, env))
    assert FC.UNRESOLVED_INTEGRATION_DEPENDENCY in got
    assert FC.PREMATURE_EVENT_CLOSURE not in got


# --- overall stage-2 verdict + metrics --------------------------------------

def test_stage2_overall_content_load_bearing_labels_not():
    r = run_stage2_evaluation()
    assert r["overall_stage2_verdict"] == "SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT"
    assert r["labels_ever_load_bearing"] is False
    assert r["content_all_load_bearing"] is True
    assert r["any_false_positive"] is False


def test_stage2_per_concept_verdicts():
    r = run_stage2_evaluation()
    assert r["concept_verdicts"] == {
        "potential": "PLANNING_GOVERNANCE_VALUE",
        "cognition": "AUDIT_VALUE",
        "reasoning": "AUDIT_VALUE",
        "integration": "ENFORCEMENT_VALUE",
    }


def test_stage2_metadata_not_full_reproduction():
    # No concept's structured findings are fully reproducible from stage-1 metadata.
    r = run_stage2_evaluation()
    for c in r["per_concept"]:
        assert c["reproducible_via_metadata_structured"] < c["findings_full"]


def test_stage2_determinism():
    assert run_stage2_evaluation() == run_stage2_evaluation()
