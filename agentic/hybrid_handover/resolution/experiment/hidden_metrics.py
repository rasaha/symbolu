#!/usr/bin/env python3
"""
Owner-clean metrics on the hidden corpus, computed per the FROZEN Relationship
Resolution Measurement Spec v1.0 definitions (re-applied to hidden data; the
frozen spec code is not modified). Returns per-case correctness vectors (for
paired stats) and aggregates.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import Edge, GovernanceResolution, Node, ResolvedEvidenceGraph
from agentic.hybrid_handover.resolution.parse import parse_nodes
from agentic.hybrid_handover.inhouse import InHouseExtractor

from .hidden_data import governance_owned, hidden_cases

_INHOUSE = InHouseExtractor()


def _gold_graph(case):
    g = case["gold"]
    parsed = {n.key: n for n in parse_nodes(case["evidence"])}
    node_keys = set(g["nodes"])
    nodes = []
    for cite, gtype in g["nodes"].items():
        p = parsed.get(cite)
        attrs = dict(p.attrs) if p else {}
        if gtype == "Document" and ("scanned" in (cite + (p.text if p else "")).lower()
                                    or "not ocr" in ((p.text if p else "").lower())):
            attrs["unusable"] = True
        nodes.append(Node(key=cite, type=gtype, doc_id=(p.doc_id if p else ""),
                          text=(p.text if p else ""), section=(p.section if p else None), attrs=attrs))
    edges = [Edge(src=s, type=t, dst=d, attrs=({"dangling": True} if d not in node_keys else {}))
             for (s, t, d) in g["edges"]]
    return ResolvedEvidenceGraph(nodes=nodes, edges=edges)


def _packet_from_gold(resolver, graph, gold):
    gov = GovernanceResolution(governing=list(gold["governing"]), abstain=gold["abstain"])
    if hasattr(resolver, "_gt") and hasattr(resolver._gt, "_derive"):
        return resolver._gt._derive(graph, gov)
    if hasattr(resolver, "_derive"):
        return resolver._derive(graph, gov)
    if gov.abstain:
        return "unknown", None, None
    text = " ".join((graph.node(k).text if graph.node(k) else "") for k in gov.governing)
    from agentic.hybrid_handover.schema import Corpus, Document
    a = _INHOUSE.resolve("", Corpus(documents=[Document(doc_id="g", citation="g", order=0, text=text)]))
    return a.termination_for_convenience, a.notice_days, a.penalty


def _pkt_correct(tfc, notice, penalty, gold):
    if gold["abstain"]:
        return tfc == "unknown"
    e = gold["packet"]
    return (tfc, notice, penalty) == (e.get("tfc"), e.get("notice_days"), e.get("penalty"))


def evaluate(resolver, cases=None) -> dict:
    cases = cases or hidden_cases()
    # discovery / classification
    d_tp = d_pred = d_ref = c_ok = c_tot = 0
    # governance ModeG / packet ModeP (per-case correctness for stats)
    govG, packP = {}, {}
    # abstention decision
    TA = FA = MA = TN = answered = correct_answered = 0
    unsafe = 0  # confident wrong answer where gold abstains (missed abstention with an answer)
    per_case = {}

    for case in cases:
        gold = case["gold"]
        # discovery/classification
        graph = resolver.resolve_relationships(case["question"], case["evidence"])
        pred_pairs = {(e.src, e.dst) for e in graph.edges}
        pred_type = {(e.src, e.dst): e.type for e in graph.edges}
        gold_pairs = {(s, d) for (s, _t, d) in gold["edges"]}
        gold_type = {(s, d): t for (s, t, d) in gold["edges"]}
        d_ref += len(gold_pairs); d_pred += len(pred_pairs); d_tp += len(gold_pairs & pred_pairs)
        case_c_ok = case_c_tot = 0
        for p, t in pred_type.items():
            if p in gold_type:
                c_tot += 1; c_ok += int(t == gold_type[p])
                case_c_tot += 1; case_c_ok += int(t == gold_type[p])

        owned = governance_owned(gold)
        gg = _gold_graph(case)
        # Mode G
        if owned:
            gov = resolver.resolve_governance(case["question"], gg)
            gcorrect = (gov.abstain == gold["abstain"]) and (gold["abstain"] or set(gov.governing) == set(gold["governing"]))
            govG[case["cid"]] = gcorrect
            # Mode P
            tfc, notice, penalty = _packet_from_gold(resolver, gg, gold)
            packP[case["cid"]] = _pkt_correct(tfc, notice, penalty, gold)

        # abstention decision (full pipeline)
        res = resolver.resolve(case["question"], case["evidence"])
        ab = res.governance.abstain
        acorrect = None
        if owned:
            if gold["abstain"] and ab:
                TA += 1
            elif not gold["abstain"] and ab:
                FA += 1
            elif gold["abstain"] and not ab:
                MA += 1
                if res.tfc in ("allowed", "prohibited"):
                    unsafe += 1  # confident wrong answer where abstention was required
            else:
                TN += 1
            if not ab:
                answered += 1
                ok = _pkt_correct(res.tfc, res.notice_days, res.penalty, gold)
                correct_answered += int(ok)
                acorrect = ok
        per_case[case["cid"]] = {
            "discovery_hit": len(gold_pairs & pred_pairs), "gold_pairs": len(gold_pairs),
            "pred_pairs": len(pred_pairs),
            "class_ok": case_c_ok, "class_tot": case_c_tot,
            "discovery_complete": (len(gold_pairs & pred_pairs) == len(gold_pairs)),
            "owned": owned,
            "governanceG": govG.get(case["cid"]), "packetP": packP.get(case["cid"]),
            "answered": (owned and not ab), "abstain": ab, "answer_correct": acorrect,
            "difficulty": gold["difficulty"], "edge_types": sorted({t for (_s, t, _d) in gold["edges"]}),
            "capability": gold["capability"], "variation": gold["variation"],
            "negative_control": gold["negative_control"], "source": case["source"],
        }

    def r(a, b):
        return round(a / b, 4) if b else None
    disc_p, disc_r = r(d_tp, d_pred), r(d_tp, d_ref)
    disc_f1 = round(2 * disc_p * disc_r / (disc_p + disc_r), 4) if disc_p and disc_r else None
    gAcc = r(sum(govG.values()), len(govG))
    pAcc = r(sum(packP.values()), len(packP))
    sel = r(correct_answered, answered)
    n_owned = TA + FA + MA + TN
    metrics = {
        "discovery_precision": disc_p, "discovery_recall": disc_r, "discovery_f1": disc_f1,
        "classification_accuracy": r(c_ok, c_tot),
        "governance_accuracy_modeG": gAcc,
        "packet_realization_accuracy_modeP": pAcc,
        "abstention_precision": r(TA, TA + FA), "abstention_recall": r(TA, TA + MA),
        "false_abstention_rate": r(FA, n_owned), "missed_abstention_rate": r(MA, n_owned),
        "answer_coverage": r(answered, n_owned), "selective_accuracy": sel,
        "unsafe_answers": unsafe,
    }
    macro_parts = [disc_f1, metrics["classification_accuracy"], gAcc, pAcc, sel]
    macro = round(sum(x or 0 for x in macro_parts) / len(macro_parts), 4)
    metrics["primary_macro"] = macro
    return {"metrics": metrics, "per_case": per_case}
