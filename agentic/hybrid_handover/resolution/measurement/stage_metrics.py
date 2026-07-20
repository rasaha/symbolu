#!/usr/bin/env python3
"""
Owner-clean stage metrics. Each function measures exactly ONE capability.

  Stage 1 Discovery      — did the required relationship endpoints exist? (type-agnostic)
  Stage 2 Classification — given correct endpoints, was the type correct?
  Stage 3 Governance     — Mode G: gold graph in, is the governing/abstain decision right?
  Stage 4 Packet         — Mode P: gold governance in, is the built answer right?
"""

from __future__ import annotations

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.resolution.graph import GovernanceResolution
from agentic.hybrid_handover.resolution.gold import GOLD
from agentic.hybrid_handover.resolution.modes import mode_oracle

from .gold_graph import build_gold_graph

_INHOUSE = InHouseExtractor()


def _governance_owned(cid, gold) -> bool:
    # pure-coverage cases (OCR) are a SafetyGate/parser matter, not governance
    return not (gold.capabilities == ["coverage"])


# --- Stage 1 + 2 : discovery & classification (type-agnostic endpoints) ----- #
def discovery_classification(resolver, cases):
    disc_hit = disc_predpairs = disc_goldpairs = 0
    cls_ok = cls_tot = 0
    for case in cases:
        gold = GOLD[case.case_id]
        graph = resolver.resolve_relationships(case.question, mode_oracle(case))
        pred_pairs = {(e.src, e.dst) for e in graph.edges}
        pred_typed = {(e.src, e.dst): e.type for e in graph.edges}
        gold_pairs = {(s, d) for (s, _t, d) in gold.edges}
        gold_type = {(s, d): _t for (s, _t, d) in gold.edges}

        disc_goldpairs += len(gold_pairs)
        disc_predpairs += len(pred_pairs)
        disc_hit += len(gold_pairs & pred_pairs)

        for (s, d), t in pred_typed.items():
            if (s, d) in gold_type:
                cls_tot += 1
                if t == gold_type[(s, d)]:
                    cls_ok += 1
    return {
        "discovery_recall": _r(disc_hit, disc_goldpairs),
        "discovery_precision": _r(disc_hit, disc_predpairs),
        "classification_accuracy": _r(cls_ok, cls_tot),
    }


# --- Stage 3 : governance in isolation (Mode G) ----------------------------- #
def governance_modeG(resolver, cases):
    ok = tot = 0
    per = {}
    for case in cases:
        gold = GOLD[case.case_id]
        if not _governance_owned(case.case_id, gold):
            continue
        g = build_gold_graph(case, gold)
        gov = resolver.resolve_governance(case.question, g)
        correct = (gov.abstain == gold.abstain) and (
            gold.abstain or set(gov.governing) == set(gold.governing))
        per[case.case_id] = correct
        ok += int(correct); tot += 1
    return {"governance_accuracy_modeG": _r(ok, tot), "_per_case": per}


# --- Stage 4 : packet realization in isolation (Mode P) --------------------- #
def _packet_from_gold_governance(resolver, graph, gold):
    gov = GovernanceResolution(governing=list(gold.governing), abstain=gold.abstain)
    if hasattr(resolver, "_derive"):
        return resolver._derive(graph, gov)
    # frozen-style builder: resolve over the governing nodes' text
    if gov.abstain:
        return "unknown", None, None
    text = " ".join((graph.node(k).text if graph.node(k) else "") for k in gov.governing)
    from agentic.hybrid_handover.schema import Corpus, Document
    ans = _INHOUSE.resolve("", Corpus(documents=[Document(doc_id="g", citation="g", order=0, text=text)]))
    return ans.termination_for_convenience, ans.notice_days, ans.penalty


def packet_modeP(resolver, cases):
    ok = tot = 0
    per = {}
    for case in cases:
        gold = GOLD[case.case_id]
        if not _governance_owned(case.case_id, gold):
            continue
        g = build_gold_graph(case, gold)
        tfc, notice, penalty = _packet_from_gold_governance(resolver, g, gold)
        exp = case.expected_answer
        if gold.abstain:
            correct = tfc == "unknown"
        else:
            correct = (tfc, notice, penalty) == (
                exp.termination_for_convenience, exp.notice_days, exp.penalty)
        per[case.case_id] = correct
        ok += int(correct); tot += 1
    return {"packet_realization_accuracy_modeP": _r(ok, tot), "_per_case": per}


def _r(a, b):
    return round(a / b, 4) if b else None
