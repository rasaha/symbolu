"""
TAP-E3 evaluation harness.

For each case: build an IntentRecord with the FROZEN TAP-E1 layer, assemble a TAP-E2
RetrievalRecord from the case's evidence units (frozen TAP-E2 structures), run each of
the six baselines, and score with the TAP-E3 metrics. Configuration selection uses the
DEV split only (the simplest baseline that satisfies all preregistered gates); the
locked eval split is scored once for the verdict.

Deterministic; no randomness.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1_config
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e3_relationship_truth import extractor, metrics
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus import cases as corpus
from truth_assurance_pipeline.tap_e3_relationship_truth.corpus.cases import (
    Case, build_retrieval_record,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.extractor import (
    BASELINES, ExtractionConfig, RelationshipTruthLayer,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.validator import require_valid

_E1 = IntentUnderstandingLayer(e1_config("V4"))
_INTENT_CACHE: Dict[str, object] = {}


def _intent(case: Case):
    if case.case_id not in _INTENT_CACHE:
        _INTENT_CACHE[case.case_id] = _E1.interpret(
            RawUserRequest(case.case_id, case.request_text))
    return _INTENT_CACHE[case.case_id]


def run_config(cfg: ExtractionConfig, cs: Sequence[Case]) -> List:
    layer = RelationshipTruthLayer(cfg)
    out = []
    for case in cs:
        intent = _intent(case)
        retrieval = build_retrieval_record(case)
        require_valid(intent, retrieval)
        rec = layer.extract(intent, retrieval)
        out.append(metrics.score_case(case, rec))
    return out


def _metrics_by_config(cs: Sequence[Case]) -> Dict[str, Dict]:
    return {cfg.name: metrics.aggregate(run_config(cfg, cs)) for cfg in BASELINES}


# --------------------------------------------------------------------------- #
# preregistered gates                                                         #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Gate:
    key: str
    op: str
    threshold: float


GATES: Tuple[Gate, ...] = (
    Gate("relationship_f1", ">=", 0.80),
    Gate("predicate_accuracy", ">=", 0.85),
    Gate("direction_accuracy", ">=", 0.90),
    Gate("polarity_accuracy", ">=", 0.95),
    Gate("modality_accuracy", ">=", 0.85),
    Gate("provenance_completeness", "==", 1.00),
    Gate("conflict_detection_f1", ">=", 0.75),
    Gate("gap_detection_accuracy", ">=", 0.75),
    Gate("cooccurrence_false_positive_rate", "<=", 0.10),
    Gate("unsupported_relationship_rate", "<=", 0.10),
    Gate("severe_critical_failure_count", "==", 0.0),
)


def _passes(g: Gate, v: float) -> bool:
    return (v >= g.threshold if g.op == ">=" else
            v <= g.threshold if g.op == "<=" else v == g.threshold)


def evaluate_gates(m: Mapping[str, object]) -> Dict[str, object]:
    res = []
    ok_all = True
    for g in GATES:
        v = float(m[g.key])
        ok = _passes(g, v)
        ok_all = ok_all and ok
        res.append({"gate": g.key, "op": g.op, "threshold": g.threshold,
                    "value": round(v, 4), "pass": ok})
    return {"all_pass": ok_all, "gates": res}


def select_config(dev: Mapping[str, Mapping[str, object]]) -> str:
    """Simplest baseline (A..F order) that satisfies ALL gates on DEV."""
    for cfg in BASELINES:
        if evaluate_gates(dev[cfg.name])["all_pass"]:
            return cfg.name
    return BASELINES[-1].name          # fallback: most complex


def verdict(gate_result: Mapping[str, object], selected_passes_dev: bool) -> Tuple[str, str]:
    n_fail = sum(1 for g in gate_result["gates"] if not g["pass"])
    severe = next(g for g in gate_result["gates"] if g["gate"] == "severe_critical_failure_count")
    if n_fail == 0:
        return ("PASS_WITH_LIMITED_CLAIM",
                "All preregistered gates pass on the locked eval split for the selected "
                "baseline. The claim is limited to mechanism/construction validation: a "
                "deterministic, provenance-preserving relationship extraction/normalization/"
                "conflict/gap architecture on the synthetic corpus used in this study. No "
                "claim of production semantic understanding or external generalization.")
    if not selected_passes_dev:
        return ("INCONCLUSIVE",
                "No baseline satisfied all preregistered gates on the development split.")
    if not severe["pass"] or n_fail >= 3:
        return ("FAIL", f"{n_fail} preregistered gate(s) failed on the locked eval split.")
    return ("INCONCLUSIVE", f"{n_fail} preregistered gate(s) failed; evidence is mixed.")


def frozen_components_hash() -> str:
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash
    src = {
        "extractor": inspect.getsource(extractor),
        "metrics": inspect.getsource(metrics),
        "gates": [(g.key, g.op, g.threshold) for g in GATES],
        "baselines": [(c.name, c.cooccurrence_only, c.predicate_keyword, c.normalize,
                       c.polarity_modality, c.temporal_scope_cond, c.consolidate)
                      for c in BASELINES],
    }
    return stable_hash(src)


def run_all() -> Dict[str, object]:
    dev = corpus.cases_for_split("dev")
    ev = corpus.cases_for_split("eval")
    dev_m = _metrics_by_config(dev)
    eval_m = _metrics_by_config(ev)

    selected = select_config(dev_m)
    selected_passes_dev = evaluate_gates(dev_m[selected])["all_pass"]
    gate_result = evaluate_gates(eval_m[selected])
    v, v_reason = verdict(gate_result, selected_passes_dev)

    from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import (
        ONTOLOGY_VERSION, predicates_in_ontology,
    )
    from truth_assurance_pipeline.tap_e3_relationship_truth.schema import SCHEMA_VERSION
    return {
        "schema_version": SCHEMA_VERSION, "ontology_version": ONTOLOGY_VERSION,
        "ontology_predicate_count": predicates_in_ontology(),
        "corpus_manifest": corpus.manifest(),
        "frozen_components_hash": frozen_components_hash(),
        "baselines": [{"name": c.name, "description": c.description} for c in BASELINES],
        "metrics": {"dev": dev_m, "eval_locked": eval_m},
        "selection": {
            "selected_config": selected,
            "selected_passes_dev": selected_passes_dev,
            "rule": "simplest baseline (A..F) satisfying ALL preregistered gates on DEV; "
                    "locked eval never used for selection",
            "dev_gate_pass": {c.name: evaluate_gates(dev_m[c.name])["all_pass"]
                              for c in BASELINES},
        },
        "gates": gate_result,
        "verdict": v, "verdict_reason": v_reason,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    r = run_all()
    print(json.dumps({k: v for k, v in r.items() if k != "metrics"}, indent=2, default=str))
