"""
Stage-2 evaluation: per-concept metrics, the two ablations, metadata
reproduction, deterministic per-concept verdicts, and an overall summary.
"""

from __future__ import annotations

from typing import Dict, List

from agentic.enterprise_ontology.stage2.ablation import (
    ablate_content, ablate_label, metadata_reproduction,
)
from agentic.enterprise_ontology.stage2.failures import Concept
from agentic.enterprise_ontology.stage2.invariants import run_concept_invariants
from agentic.enterprise_ontology.stage2.scenarios import all_stage2_scenarios

# Reasoned value-dimension + category per concept (used only when incremental
# value is demonstrated by the metrics — never awarded for prose alone).
_VALUE_TYPE = {
    Concept.POTENTIAL: ("PLANNING_GOVERNANCE_VALUE", ["planning", "preventive"]),
    Concept.COGNITION: ("AUDIT_VALUE", ["audit", "observability", "explanatory"]),
    Concept.REASONING: ("AUDIT_VALUE", ["audit", "explanatory"]),
    Concept.INTEGRATION: ("ENFORCEMENT_VALUE", ["enforcement", "audit"]),
}


def _verdict(concept, full, label_adds, content_adds, repro_structured) -> str:
    if full == 0:
        return "NO_INCREMENTAL_VALUE"
    if content_adds == 0:
        return "LABEL_ONLY_VALUE" if label_adds != 0 else "METADATA_EQUIVALENT"
    if repro_structured >= full:
        return "METADATA_EQUIVALENT"
    return _VALUE_TYPE[concept][0]


def evaluate_concept(scenario) -> Dict:
    c = scenario.concept
    full = run_concept_invariants(c, scenario.violating)
    label_ab = run_concept_invariants(c, ablate_label(scenario.violating, c))
    content_ab = run_concept_invariants(c, ablate_content(scenario.violating, c))
    clean = run_concept_invariants(c, scenario.clean)
    repro = metadata_reproduction(c, scenario.violating, full)

    findings_full = len(full)
    label_adds = findings_full - len(label_ab)
    content_adds = findings_full - len(content_ab)
    unique_classes = sorted({f.failure_class.value for f in full})
    baseline = {b.value for b in scenario.baseline_reproducible}
    ontology_only = sorted(set(unique_classes) - baseline)

    verdict = _verdict(c, findings_full, label_adds, content_adds,
                       repro["structured_reproduced"])
    return {
        "concept": c.value,
        "scenario": scenario.name,
        "findings_full": findings_full,
        "findings_after_label_ablation": len(label_ab),
        "findings_lost_after_content_ablation": content_adds,
        "reproducible_via_metadata_structured": repro["structured_reproduced"],
        "metadata_coarse_existence": repro["coarse_existence"],
        "metadata_note": repro["note"],
        "label_adds_value": label_adds != 0,
        "content_adds_value": content_adds > 0,
        "unique_failure_classes": unique_classes,
        "baseline_reproducible": sorted(baseline),
        "ontology_only": ontology_only,
        "false_positives_on_clean": len(clean),
        "value_dimensions": _VALUE_TYPE[c][1],
        "verdict": verdict,
    }


def run_stage2_evaluation() -> Dict:
    per_concept = [evaluate_concept(s) for s in all_stage2_scenarios()]
    labels_ever_load_bearing = any(c["label_adds_value"] for c in per_concept)
    content_all_load_bearing = all(c["content_adds_value"] for c in per_concept)
    any_false_positive = any(c["false_positives_on_clean"] for c in per_concept)

    # Overall: did the four concepts prove non-load-bearing, or under-exercised?
    if content_all_load_bearing and not labels_ever_load_bearing:
        overall = "SEMANTIC_CONTENT_LOAD_BEARING_LABELS_NOT"
    elif not content_all_load_bearing:
        overall = "MIXED_SOME_CONCEPTS_REDUNDANT"
    else:
        overall = "LABELS_AND_CONTENT_LOAD_BEARING"

    return {
        "per_concept": per_concept,
        "labels_ever_load_bearing": labels_ever_load_bearing,
        "content_all_load_bearing": content_all_load_bearing,
        "any_false_positive": any_false_positive,
        "overall_stage2_verdict": overall,
        "concept_verdicts": {c["concept"]: c["verdict"] for c in per_concept},
    }
