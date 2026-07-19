#!/usr/bin/env python3
"""
Resolver-specific (component) metrics — kept entirely separate from SEEB's
pipeline metrics, which are not redefined.

Graph-structure metrics: edge precision/recall, relationship-type accuracy,
cross-document link accuracy. Governance/outcome metrics: per-capability
resolution accuracy, negation, cycle detection, abstention.
"""

from __future__ import annotations

from .gold import GOLD


def _answer_correct(result, expected, gold) -> bool:
    if gold.abstain:
        return result.governance.abstain
    if result.governance.abstain:
        return False
    return (result.tfc, result.notice_days, result.penalty) == (
        expected.termination_for_convenience, expected.notice_days, expected.penalty
    )


class ResolverScore:
    def __init__(self):
        self.edge_tp = self.edge_fp = self.edge_fn = 0
        self.type_ok = self.type_tot = 0
        self.xdoc_hit = self.xdoc_tot = 0
        self.cap = {}          # capability -> [correct, total]
        self.abstain_ok = 0
        self.n = 0

    def _cap(self, name, ok):
        c = self.cap.setdefault(name, [0, 0])
        c[1] += 1
        if ok:
            c[0] += 1


def score_case(case_id, result, expected, score: ResolverScore):
    gold = GOLD[case_id]
    score.n += 1

    # --- edges ---
    pred = result.graph.edge_triples()
    goldset = {tuple(e) for e in gold.edges}
    score.edge_tp += len(pred & goldset)
    score.edge_fp += len(pred - goldset)
    score.edge_fn += len(goldset - pred)

    # cross-document link recall (gold cross-doc edges predicted)
    def _doc(cite):
        return cite.split(" §")[0].split(" (")[0].split(" p.")[0]
    for e in goldset:
        if _doc(e[0]) != _doc(e[2]):
            score.xdoc_tot += 1
            if e in pred:
                score.xdoc_hit += 1

    # --- node type accuracy ---
    pred_types = {n.key: n.type for n in result.graph.nodes}
    for cite, gtype in gold.nodes.items():
        if cite in pred_types:
            score.type_tot += 1
            if pred_types[cite] == gtype:
                score.type_ok += 1

    # --- outcome / capability metrics ---
    correct = _answer_correct(result, expected, gold)
    cap_map = {
        "precedence": "precedence_resolution",
        "override": "override_resolution",
        "exception": "exception_resolution",
        "definition": "definition_resolution",
        "version": "version_selection",
        "conflict": "conflict_resolution",
        "negation": "negation_interpretation",
        "cycle": "cycle_detection",
        "abstention": "abstention",
        "reference": "cross_document_link",
        "coverage": "coverage_abstention",
    }
    for capability in gold.capabilities:
        metric = cap_map.get(capability)
        if metric:
            score._cap(metric, correct)

    # abstention decision correctness (all cases)
    if result.governance.abstain == gold.abstain:
        score.abstain_ok += 1


def summarise(score: ResolverScore) -> dict:
    def ratio(a, b):
        return round(a / b, 4) if b else None
    out = {
        "relationship_edge_precision": ratio(score.edge_tp, score.edge_tp + score.edge_fp),
        "relationship_edge_recall": ratio(score.edge_tp, score.edge_tp + score.edge_fn),
        "relationship_type_accuracy": ratio(score.type_ok, score.type_tot),
        "cross_document_link_accuracy": ratio(score.xdoc_hit, score.xdoc_tot),
        "abstention_accuracy": ratio(score.abstain_ok, score.n),
    }
    for metric, (ok, tot) in sorted(score.cap.items()):
        out[metric + "_accuracy"] = ratio(ok, tot)
    return out
