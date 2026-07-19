"""Enterprise Governance Evidence Model — shadow-pilot tests (deterministic)."""

import ast
import pathlib

import pytest

from agentic.enterprise_governance import (
    EvidenceStatus, ShadowEvaluator, StrongControlsBaseline, all_workflows,
    run_invariants, shadow_report,
)
from agentic.enterprise_governance.invariants import INVARIANTS
from agentic.enterprise_governance.workflows import discount_to_contract, iam_role_access


def _codes(findings):
    return {f.failure_code for f in findings}


# --- flawed workflows produce the expected net-new value --------------------

def test_discount_workflow_net_new_beyond_strong_baseline():
    r = ShadowEvaluator().evaluate_workflow(discount_to_contract())
    assert r["net_new_findings"] >= 6
    for code in ("PREMATURE_EVENT_CLOSURE", "POLICY_VERSION_CONFLICT",
                 "FORM_EXECUTION_MISMATCH", "CROSS_SYSTEM_DEPENDENCY_FAILURE",
                 "ADVISORY_AUTHORITY_ESCALATION"):
        assert code in r["net_new_codes"]
    # And it honestly concedes what a strong baseline already catches.
    assert "MISSING_AUTHORITY_BASIS" in r["duplicate_of_existing_controls"]


def test_iam_workflow_reuses_capability_and_closure_invariants():
    r = ShadowEvaluator().evaluate_workflow(iam_role_access())
    for code in ("STALE_CAPABILITY_STATE", "CAPABILITY_AUTHORITY_MISMATCH",
                 "PREMATURE_EVENT_CLOSURE", "INCOMPLETE_ENTERPRISE_TRANSITION"):
        assert code in r["net_new_codes"]
    assert "PROHIBITED_CAPABILITY_EXPOSURE" in r["duplicate_of_existing_controls"]


# --- clean workflows: false-positive guard ----------------------------------

@pytest.mark.parametrize("wf", all_workflows(clean=True), ids=lambda w: w.workflow_id)
def test_clean_workflows_have_no_findings(wf):
    assert run_invariants(wf) == []


# --- shared-invariant reuse (the scalability claim) -------------------------

def test_same_invariants_govern_both_workflows_unchanged():
    r = shadow_report()
    assert r["workflows_governed_by_same_invariants"] == 2
    # At least authority + integration reused across BOTH workflows, unchanged.
    reused = r["invariants_reused_across_workflows"]
    assert "authority_provenance" in reused
    assert "integration_closure" in reused
    for wfs in reused.values():
        assert len(wfs) >= 2


def test_shadow_report_metrics_and_zero_false_positives():
    r = shadow_report()
    assert r["false_positive_rate"] == 0.0
    assert r["clean_workflow_false_positives"] == 0
    assert r["total_net_new_findings"] > 0
    assert 0.0 < r["net_new_ratio"] <= 1.0


# --- missing data stays explicit --------------------------------------------

def test_missing_data_is_explicit_not_invented():
    wf = discount_to_contract()  # finance approver is None → MISSING evidence
    missing = [e for e in wf.evidence if e.status == EvidenceStatus.MISSING]
    assert missing, "expected an explicit MISSING evidence record"
    # No invariant fabricates a value for the missing approval.
    r = ShadowEvaluator().evaluate_workflow(wf)
    assert r["missing_data_rate"] > 0


# --- promotion ladder + dispositions are attached ---------------------------

def test_findings_carry_disposition_and_promotion():
    findings = run_invariants(discount_to_contract())
    assert all(f.disposition and f.default_promotion for f in findings)
    # Integration closure + capability exposure are the enforcement-forward ones.
    closure = [f for f in findings if f.invariant == "integration_closure"]
    assert closure and all(
        f.default_promotion.value in ("approval_required", "hard_enforce", "warning")
        for f in closure)


# --- strong baseline is honestly strong -------------------------------------

def test_strong_baseline_catches_realistic_controls():
    b = StrongControlsBaseline()
    caught = b.catches(discount_to_contract())
    # A mature enterprise already catches these — so they are NOT counted net-new.
    assert {"MISSING_AUTHORITY_BASIS", "STATE_RECONCILIATION_FAILURE",
            "PROTECTED_INVARIANT_BREACH"} <= caught


# --- isolation: no production / research imports -----------------------------

def test_package_is_self_contained_and_read_only():
    root = pathlib.Path(__file__).resolve().parents[1]
    banned = ("agentic.agentic_framework", "agentic.healthcare", "agentic.trading",
              "agentic.enterprise_ontology", "jepa", "sovereign", "latent")
    offenders = []
    for py in root.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(), filename=str(py))):
            mod = None
            if isinstance(node, ast.Import):
                mod = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if mod and any(b in mod for b in banned):
                offenders.append(f"{py.name}: {mod}")
    assert not offenders, f"unexpected imports: {offenders}"
