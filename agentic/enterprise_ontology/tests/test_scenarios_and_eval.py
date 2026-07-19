"""Scenario coverage, baseline comparison, ablation, verdict, and isolation tests."""

import ast
import pathlib

import pytest

from agentic.enterprise_ontology import run_evaluation
from agentic.enterprise_ontology.gap_analysis import (
    compare_scenario, compute_verdict, layer_dependence,
)
from agentic.enterprise_ontology.invariants import run_all_invariants
from agentic.enterprise_ontology.scenarios import all_scenarios


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_scenario_triggers_expected_failure_classes(scenario):
    got = {f.failure_class for f in run_all_invariants(scenario.envelope)}
    missing = scenario.expected_failure_classes - got
    assert not missing, f"{scenario.name} missing {[m.value for m in missing]}"


@pytest.mark.parametrize("scenario", all_scenarios(), ids=lambda s: s.name)
def test_ontology_surfaces_more_than_baseline(scenario):
    cmp = compare_scenario(scenario)
    # Every scenario should reveal at least one failure class the per-vertical
    # baseline cannot express on its own.
    assert cmp.ontology_only, f"{scenario.name} added nothing beyond baseline"


def test_verdict_is_cross_vertical_governance_value():
    v = compute_verdict(all_scenarios())
    assert v["verdict"] == "CROSS_VERTICAL_GOVERNANCE_VALUE"
    assert v["scenarios_with_ontology_only_value"] == 4
    assert len(v["reusable_invariants_that_fired"]) >= 6


def test_layer_ablation_identifies_non_load_bearing_layers():
    ld = layer_dependence()
    # The honest finding: several layers never drive detection (documentation only).
    assert set(ld["layers_never_keyed"]) == {
        "cognition", "integration", "potential", "reasoning"}
    # And a real share of invariants key purely on metadata, not layer labels.
    assert 0.0 < ld["fraction_invariants_needing_layers"] < 1.0


def test_form_execution_mismatch_normalizes_across_verticals():
    # Same structural failure class in two different verticals (the normalization claim).
    scenarios = {s.name: s for s in all_scenarios()}
    disc = {f.failure_class.value for f in run_all_invariants(scenarios["discount"].envelope)}
    hire = {f.failure_class.value for f in run_all_invariants(scenarios["hiring"].envelope)}
    assert "FORM_EXECUTION_MISMATCH" in disc  # quote → contract
    assert "FORM_EXECUTION_MISMATCH" in hire  # standard_access → admin_access


def test_run_evaluation_shape():
    r = run_evaluation()
    assert len(r["scenarios"]) == 4
    assert r["verdict"]["verdict"] in (
        "NO_INCREMENTAL_VALUE", "DOCUMENTATION_VALUE_ONLY", "OBSERVABILITY_VALUE",
        "CROSS_VERTICAL_GOVERNANCE_VALUE", "CANDIDATE_ENTERPRISE_SEMANTIC_ARCHITECTURE")


def test_package_does_not_import_production_actiongate():
    """Isolation: the research package must not import production ActionGate /
    healthcare / trading / jepa / sovereign / latent-state modules."""
    root = pathlib.Path(__file__).resolve().parents[1]
    banned = ("agentic.agentic_framework", "agentic.healthcare", "agentic.trading",
              "jepa", "sovereign", "latent")
    offenders = []
    for py in root.rglob("*.py"):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                mod = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if mod and any(b in mod for b in banned):
                offenders.append(f"{py.name}: {mod}")
    assert not offenders, f"production imports found: {offenders}"
