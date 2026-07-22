"""
TAP-E2 evaluation harness.

Drives the frozen TAP-E1 layer to produce an IntentRecord for each query
(demonstrating the E1->E2 interface), runs the six retrieval baselines, scores them
with the TAP-E2 metrics, selects a configuration on the DEV split only, and applies
preregistered gates to the selected configuration on the locked eval split.

Deterministic except for wall-clock latency (reported separately and excluded from the
reproducibility comparison).
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e1_intent import IntentUnderstandingLayer, config as e1_config
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e2_trusted_retrieval import metrics, retrieval
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import documents, queries
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus.queries import QueryCase
from truth_assurance_pipeline.tap_e2_trusted_retrieval.index import RetrievalIndex
from truth_assurance_pipeline.tap_e2_trusted_retrieval.retrieval import (
    BASELINES, RetrievalConfig, TrustedRetrievalLayer,
)

_INDEX = RetrievalIndex.build(documents.units())
_INDEX_IDS = frozenset(documents.unit_ids())
_E1 = IntentUnderstandingLayer(e1_config("V4"))
_INTENT_CACHE: Dict[str, object] = {}


def _intent(q: QueryCase):
    if q.query_id not in _INTENT_CACHE:
        _INTENT_CACHE[q.query_id] = _E1.interpret(
            RawUserRequest(q.query_id, q.request_text))
    return _INTENT_CACHE[q.query_id]


def run_config(cfg: RetrievalConfig, qs: Sequence[QueryCase]
               ) -> Tuple[List, float]:
    layer = TrustedRetrievalLayer(cfg, _INDEX)
    scores = []
    latency = 0.0
    for q in qs:
        rec = layer.retrieve(_intent(q))
        latency += rec.latency_ms
        scores.append(metrics.score_query(q, rec, _INDEX_IDS))
    return scores, (latency / len(qs) if qs else 0.0)


def _metrics_by_config(qs: Sequence[QueryCase]) -> Tuple[Dict[str, Dict], Dict[str, float]]:
    out: Dict[str, Dict] = {}
    lat: Dict[str, float] = {}
    for cfg in BASELINES:
        scores, latency = run_config(cfg, qs)
        out[cfg.name] = metrics.aggregate(scores)
        lat[cfg.name] = round(latency, 4)
    return out, lat


# --------------------------------------------------------------------------- #
# preregistered gates (fixed before locked-set scoring)                       #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Gate:
    key: str
    op: str
    threshold: float
    rationale: str

    def passes(self, v: float) -> bool:
        return (v >= self.threshold if self.op == ">=" else
                v <= self.threshold if self.op == "<=" else v == self.threshold)


SEVERE_CRITICALS = ("authoritative_evidence_omitted", "provenance_missing",
                    "conflicting_evidence_hidden", "hallucinated_evidence_identifiers")

GATES: Tuple[Gate, ...] = (
    Gate("recall_at_k", ">=", 0.80, "must retrieve the authoritative evidence when it exists"),
    Gate("provenance_completeness", "==", 1.0, "no evidence may appear without provenance"),
    Gate("authority_coverage", ">=", 0.80, "authoritative sources must be surfaced"),
    Gate("gap_detection_accuracy", ">=", 0.70, "retrieval incompleteness must be detected"),
    Gate("false_evidence_inclusion", "<=", 0.20, "distractors must be largely excluded"),
    Gate("severe_critical_count", "==", 0.0, "no severe critical failures on the locked set"),
)


def _severe_count(m: Mapping[str, object]) -> int:
    crit = m["critical_failures"]
    return sum(int(crit[k]) for k in SEVERE_CRITICALS)


def _gate_value(m: Mapping[str, object], key: str) -> float:
    if key == "severe_critical_count":
        return float(_severe_count(m))
    return float(m[key])


def evaluate_gates(m: Mapping[str, object]) -> Dict[str, object]:
    res = []
    all_pass = True
    for g in GATES:
        v = _gate_value(m, g.key)
        ok = g.passes(v)
        all_pass = all_pass and ok
        res.append({"gate": g.key, "op": g.op, "threshold": g.threshold,
                    "value": round(v, 4), "pass": ok, "rationale": g.rationale})
    return {"all_pass": all_pass, "gates": res}


def verdict(gate_result: Mapping[str, object]) -> Tuple[str, str]:
    n_fail = sum(1 for g in gate_result["gates"] if not g["pass"])
    severe = next(g for g in gate_result["gates"] if g["gate"] == "severe_critical_count")
    recall = next(g for g in gate_result["gates"] if g["gate"] == "recall_at_k")
    if n_fail == 0:
        return ("PASS_WITH_LIMITED_CLAIM",
                "All preregistered gates pass on the locked eval set. The claim is limited "
                "to mechanism/construction validation on a small synthetic corpus with a "
                "DETERMINISTIC concept-vector stand-in for dense retrieval (not neural "
                "embeddings). No claim of real-world retrieval quality or production "
                "readiness is made.")
    if not severe["pass"] or recall["value"] < 0.6 or n_fail >= 3:
        return ("FAIL", f"{n_fail} preregistered gate(s) failed, including severe or recall.")
    return ("INCONCLUSIVE", f"{n_fail} preregistered gate(s) failed; evidence is mixed.")


# --------------------------------------------------------------------------- #
# selection (dev only)                                                         #
# --------------------------------------------------------------------------- #

def _sel_score(m: Mapping[str, object]) -> float:
    return round(
        1.0 * float(m["recall_at_k"])
        + 1.0 * float(m["ndcg_at_k"])
        + 0.8 * float(m["provenance_completeness"])
        + 0.8 * float(m["authority_coverage"])
        + 0.8 * float(m["gap_detection_accuracy"])
        + 0.6 * (1.0 - float(m["false_evidence_inclusion"]))
        + 0.4 * (1.0 - float(m["redundancy"]))
        - 0.3 * float(_severe_count(m)), 6)


def select_config(dev: Mapping[str, Mapping[str, object]]) -> str:
    best, best_s = BASELINES[0].name, float("-inf")
    for cfg in BASELINES:
        s = _sel_score(dev[cfg.name])
        if s > best_s:
            best_s, best = s, cfg.name
    return best


# --------------------------------------------------------------------------- #
# locks / full run                                                            #
# --------------------------------------------------------------------------- #

def frozen_components_hash() -> str:
    from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import stable_hash
    src = {
        "retrieval": inspect.getsource(retrieval),
        "metrics": inspect.getsource(metrics),
        "gates": [(g.key, g.op, g.threshold) for g in GATES],
        "baselines": [(c.name, c.use_lexical, c.use_semantic, c.expansion, c.dedup,
                       c.provenance_filter, c.gap_detection) for c in BASELINES],
    }
    return stable_hash(src)


def run_all() -> Dict[str, object]:
    dev = queries.queries_for_split("dev")
    ev = queries.queries_for_split("eval")
    dev_m, dev_lat = _metrics_by_config(dev)
    eval_m, eval_lat = _metrics_by_config(ev)

    selected = select_config(dev_m)
    gate_result = evaluate_gates(eval_m[selected])
    v, v_reason = verdict(gate_result)

    from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import corpus_manifest
    return {
        "schema_version": retrieval.SCHEMA_VERSION,
        "corpus_manifest": corpus_manifest(),
        "frozen_components_hash": frozen_components_hash(),
        "baselines": [{"name": c.name, "description": c.description} for c in BASELINES],
        "metrics": {"dev": dev_m, "eval_locked": eval_m},
        "latency_ms_mean": {"dev": dev_lat, "eval_locked": eval_lat},
        "selection": {
            "selected_config": selected,
            "selection_scores_dev": {c.name: _sel_score(dev_m[c.name]) for c in BASELINES},
            "rule": "argmax on DEV of a documented weighted criterion; simplest wins ties; "
                    "locked eval never used for selection",
        },
        "gates": gate_result,
        "verdict": v,
        "verdict_reason": v_reason,
    }


if __name__ == "__main__":  # pragma: no cover
    import json
    r = run_all()
    print(json.dumps({k: v for k, v in r.items() if k != "metrics"}, indent=2, default=str))
