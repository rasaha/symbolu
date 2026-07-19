"""
Enterprise-ontology research pilot (self-contained, read-only).

Evaluates whether the 12-layer ontology adds real cross-vertical value beyond
ordinary workflow records — WITHOUT importing or modifying any production
ActionGate / healthcare / trading / JEPA / sovereign code. It consumes only its
own synthetic enterprise scenarios.
"""

from __future__ import annotations

from typing import Dict

from agentic.enterprise_ontology.events import EnterpriseEventEnvelope
from agentic.enterprise_ontology.failure_classes import FailureClass, Finding
from agentic.enterprise_ontology.gap_analysis import (
    compute_verdict, gap_report, layer_dependence, compare_scenario,
)
from agentic.enterprise_ontology.invariants import INVARIANTS, run_all_invariants
from agentic.enterprise_ontology.layers import LayerStatus, OntologyLayer
from agentic.enterprise_ontology.records import (
    AuthorityRole, EpistemicOrigin, OntologyRecord, VerificationState,
)
from agentic.enterprise_ontology.scenarios import all_scenarios
from agentic.enterprise_ontology.verticals import EnterpriseVertical


def run_evaluation() -> Dict:
    """Run all scenarios and produce the full evaluation payload."""
    scenarios = all_scenarios()
    per_scenario = []
    for s in scenarios:
        findings = run_all_invariants(s.envelope)
        per_scenario.append({
            "scenario": s.name,
            "description": s.description,
            "findings": [f.to_dict() for f in findings],
            "gap_report": gap_report(s.envelope),
            "comparison": compare_scenario(s).__dict__,
        })
    verdict = compute_verdict(scenarios)
    return {
        "scenarios": per_scenario,
        "verdict": verdict,
        "layer_dependence": layer_dependence(),
    }


__all__ = [
    "run_evaluation", "all_scenarios", "run_all_invariants", "INVARIANTS",
    "gap_report", "compute_verdict", "layer_dependence", "compare_scenario",
    "FailureClass", "Finding", "OntologyLayer", "LayerStatus", "OntologyRecord",
    "AuthorityRole", "EpistemicOrigin", "VerificationState", "EnterpriseVertical",
    "EnterpriseEventEnvelope",
]
