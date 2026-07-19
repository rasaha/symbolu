"""
Gap analysis, baseline-vs-ontology comparison, layer-dependence ablation, and
the deterministic verdict.

The ablation is the rigorous core of the evaluation: it measures whether the
value comes from the twelve LAYER LABELS or from the epistemic/authority/
dependency/reconciliation METADATA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from agentic.enterprise_ontology.events import (
    DependencyStatus,
    EnterpriseEventEnvelope,
    PERMISSIVE_EFFECTS,
)
from agentic.enterprise_ontology.failure_classes import FailureClass, Finding
from agentic.enterprise_ontology.invariants import INVARIANTS, run_all_invariants
from agentic.enterprise_ontology.layers import OntologyLayer
from agentic.enterprise_ontology.projection import Scenario, baseline_detectable
from agentic.enterprise_ontology.records import VerificationState


# --- per-event gap report ----------------------------------------------------

def gap_report(env: EnterpriseEventEnvelope) -> Dict:
    layers_present = {l.value for l in env.layers_present()}
    layers_missing = [l.value for l in OntologyLayer if l not in env.layers_present()]

    unverified_purpose = [
        r.record_id for r in env.records_in_layer(OntologyLayer.PURPOSE)
        if r.verification != VerificationState.VERIFIED]
    missing_authority = [
        d.decision_id for d in env.decisions
        if d.effect in PERMISSIVE_EFFECTS
        and not any(env.record_by_id(rid) and env.record_by_id(rid).is_authority_bearing
                    for rid in d.supporting_record_ids)]
    unsatisfied_deps = [
        f"{d.from_vertical.value}->{d.to_vertical.value}:{d.status.value}"
        for d in env.dependencies if d.status != DependencyStatus.SATISFIED]

    # (vertical, layer) coverage matrix
    coverage = {}
    for r in env.records:
        coverage.setdefault(r.vertical.value, {})[r.layer.value] = r.status.value

    return {
        "event_id": env.event_id,
        "layers_present": sorted(layers_present),
        "layers_missing": layers_missing,
        "unverified_purpose_records": unverified_purpose,
        "permissive_decisions_missing_authority_basis": missing_authority,
        "unsatisfied_dependencies": unsatisfied_deps,
        "reconciliation_status": env.reconciliation_status,
        "coverage_matrix": coverage,
    }


# --- baseline vs ontology ----------------------------------------------------

@dataclass(frozen=True)
class ScenarioComparison:
    scenario: str
    ontology_failure_classes: Tuple[str, ...]
    baseline_failure_classes: Tuple[str, ...]
    ontology_only: Tuple[str, ...]     # value the baseline could not surface
    finding_count: int


def compare_scenario(scenario: Scenario) -> ScenarioComparison:
    findings = run_all_invariants(scenario.envelope)
    onto = {f.failure_class for f in findings}
    base = set(baseline_detectable(scenario))
    only = onto - base
    return ScenarioComparison(
        scenario=scenario.name,
        ontology_failure_classes=tuple(sorted(c.value for c in onto)),
        baseline_failure_classes=tuple(sorted(c.value for c in base)),
        ontology_only=tuple(sorted(c.value for c in only)),
        finding_count=len(findings))


# --- layer-dependence ablation ----------------------------------------------

def layer_dependence() -> Dict:
    """Which layer labels detection actually hinges on, vs organizing coordinates.

    An invariant is 'layer-keyed' if its detection logic filters on a layer
    label; otherwise it keys purely on epistemic/authority/dependency/execution
    METADATA (and would work even if the twelve labels were collapsed to a small
    record-kind tag)."""
    keyed = set()
    for spec in INVARIANTS:
        if spec.layer_keyed:
            keyed.update(spec.layers_used)
    all_layers = set(OntologyLayer)
    metadata_invariants = [s.name for s in INVARIANTS if not s.layer_keyed]
    layer_invariants = [s.name for s in INVARIANTS if s.layer_keyed]
    return {
        "invariants_metadata_keyed": metadata_invariants,
        "invariants_layer_keyed": layer_invariants,
        "layers_used_by_some_invariant": sorted(l.value for l in keyed),
        "layers_never_keyed": sorted(l.value for l in (all_layers - keyed)),
        "fraction_invariants_needing_layers": round(
            len(layer_invariants) / len(INVARIANTS), 3),
        "fraction_layers_load_bearing": round(len(keyed) / len(all_layers), 3),
    }


# --- verdict -----------------------------------------------------------------

VERDICTS = (
    "NO_INCREMENTAL_VALUE",
    "DOCUMENTATION_VALUE_ONLY",
    "OBSERVABILITY_VALUE",
    "CROSS_VERTICAL_GOVERNANCE_VALUE",
    "CANDIDATE_ENTERPRISE_SEMANTIC_ARCHITECTURE",
)

# Cross-vertical failure classes that a per-vertical baseline structurally cannot
# express without bespoke joins.
_CROSS_VERTICAL_CLASSES = frozenset({
    FailureClass.CROSS_VERTICAL_DEPENDENCY_FAILURE,
    FailureClass.UNIVERSAL_CONSTRAINT_BREACH,
    FailureClass.STATE_RECONCILIATION_FAILURE,
    FailureClass.ADVISORY_AUTHORITY_ESCALATION,
    FailureClass.EXECUTION_OBSERVATION_MISMATCH,
})


def compute_verdict(scenarios: List[Scenario]) -> Dict:
    comparisons = [compare_scenario(s) for s in scenarios]
    all_only = set()
    reusable_invariants_fired = set()
    cross_vertical_hits = 0
    scenarios_with_ontology_only = 0
    for s, c in zip(scenarios, comparisons):
        if c.ontology_only:
            scenarios_with_ontology_only += 1
        all_only.update(c.ontology_only)
        for f in run_all_invariants(s.envelope):
            reusable_invariants_fired.add(f.invariant)
            if f.failure_class in _CROSS_VERTICAL_CLASSES:
                cross_vertical_hits += 1

    distinct_only_classes = len(all_only)
    # Deterministic verdict rule.
    if distinct_only_classes == 0:
        verdict = "NO_INCREMENTAL_VALUE"
    elif cross_vertical_hits == 0:
        verdict = "DOCUMENTATION_VALUE_ONLY"
    elif len(reusable_invariants_fired) < 4 or scenarios_with_ontology_only < 2:
        verdict = "OBSERVABILITY_VALUE"
    elif (scenarios_with_ontology_only >= 3 and distinct_only_classes >= 5
          and len(reusable_invariants_fired) >= 6):
        verdict = "CROSS_VERTICAL_GOVERNANCE_VALUE"
    else:
        verdict = "OBSERVABILITY_VALUE"
    # CANDIDATE_ENTERPRISE_SEMANTIC_ARCHITECTURE is intentionally NOT auto-awarded
    # from a 4-scenario synthetic pilot; it requires broader external validation.

    return {
        "verdict": verdict,
        "distinct_ontology_only_failure_classes": sorted(all_only),
        "reusable_invariants_that_fired": sorted(reusable_invariants_fired),
        "cross_vertical_findings": cross_vertical_hits,
        "scenarios_with_ontology_only_value": scenarios_with_ontology_only,
        "comparisons": [c.__dict__ for c in comparisons],
        "layer_dependence": layer_dependence(),
    }
