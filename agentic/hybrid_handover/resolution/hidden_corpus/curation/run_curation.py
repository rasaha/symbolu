#!/usr/bin/env python3
"""
Curation orchestrator — runs the whole expansion pipeline over the pilot
candidates and issues the pipeline-validation verdict. Runs NO resolver and
reports NO resolver performance.

    python -m agentic.hybrid_handover.resolution.hidden_corpus.curation.run_curation
"""

from __future__ import annotations

import json
import os
from collections import Counter

from agentic.hybrid_handover.resolution.hidden_corpus import corpus as seed_corpus
from agentic.hybrid_handover.resolution.hidden_corpus.annotations import all_annotations as seed_anns

from . import answer_position, gold_sufficiency, leakage_pilot, pilot_loader
from .agreement import cohens_kappa_binary, compare
from .blinding import annotator_is_blind
from .difficulty_rubric import factors_from_graph, rubric_level
from .duplicates import quarantine_recommended, similarity
from .lifecycle import check_candidate
from .records import (
    accepted_candidates, adjudication_record, all_candidates, annotator_record,
    author_record, candidate_view, opaque_id,
)

OUT_DIR = os.path.dirname(__file__)


def _prf_agg(triples):
    tp = pred = ref = 0
    exact = 0
    for p, r in triples:
        tp += len(p & r); pred += len(p); ref += len(r)
        exact += int(p == r)
    prec = round(tp / pred, 4) if pred else None
    rec = round(tp / ref, 4) if ref else None
    f1 = round(2 * prec * rec / (prec + rec), 4) if prec and rec else None
    return {"precision": prec, "recall": rec, "f1": f1,
            "exact_match_rate": round(exact / len(triples), 4) if triples else None}


def run():
    cands = all_candidates()
    accepted = accepted_candidates()

    # counts
    counts = Counter(c["decision"] for c in cands)
    rej_reasons = [{"id": opaque_id(c), "decision": c["decision"], "reason": c["adj_rationale"]}
                   for c in cands if c["decision"] != "ACCEPTED"]

    # lifecycle + blinding
    lifecycle_issues, blinding_issues = [], []
    for c in cands:
        lifecycle_issues += [(opaque_id(c), i) for i in check_candidate(candidate_view(c))]
        banned = annotator_is_blind(annotator_record(c))
        if banned:
            blinding_issues.append((opaque_id(c), banned))

    # agreement (author intended vs annotator)
    node_t, edge_t, gov_t = [], [], []
    abst_pairs = []
    for c in cands:
        a = author_record(c)["intended_graph"]
        b = annotator_record(c)["graph"]
        node_t.append((set(b["nodes"]), set(a["nodes"])))
        edge_t.append(({(s, d) for s, _t, d in b["edges"]}, {(s, d) for s, _t, d in a["edges"]}))
        gov_t.append((set(c["ann_governing"]), set(a["governing"])))
        abst_pairs.append((bool(a["abstain"]), bool(c["ann_abstain"])))
    agreement = {
        "node": _prf_agg(node_t), "edge_presence": _prf_agg(edge_t),
        "governing": _prf_agg(gov_t), "packet_membership": _prf_agg(gov_t),
        "abstention_kappa": cohens_kappa_binary(abst_pairs),
        "abstention_exact_match": round(sum(1 for a, b in abst_pairs if a == b) / len(abst_pairs), 4),
    }

    # duplicates: accepted vs (seed + other accepted)
    seed_pairs = []
    seed_cases = seed_corpus.executable_cases()
    seed_ann = seed_anns()
    for sc in seed_cases:
        text = sc["question"] + " " + " ".join(d["text"] for d in sc["documents"])
        graph = {"nodes": seed_ann[sc["id"]]["gold_nodes"], "edges": seed_ann[sc["id"]]["gold_edges"],
                 "governing": seed_ann[sc["id"]]["governing"], "abstain": seed_ann[sc["id"]]["abstain"]}
        seed_pairs.append((text, graph))
    acc_pairs = [(c["question"] + " " + " ".join(d["text"] for d in c["documents"]),
                  {**c["ann_graph"], "governing": c["ann_governing"], "abstain": c["ann_abstain"]})
                 for c in accepted]
    from .candidates import DUP_OVERRIDES
    accepted_quarantine_hits, overridden_hits = [], []
    for i, (txt, g) in enumerate(acc_pairs):
        others = seed_pairs + [p for j, p in enumerate(acc_pairs) if j != i]
        if any(quarantine_recommended(similarity(txt, g, ot, og)) for ot, og in others):
            ref = accepted[i]["ref"]
            if ref in DUP_OVERRIDES:
                overridden_hits.append({"id": opaque_id(accepted[i]), "ref": ref,
                                        "override_reason": DUP_OVERRIDES[ref]})
            else:
                accepted_quarantine_hits.append(opaque_id(accepted[i]))
    # confirm the quarantined design case IS detected against seed + accepted
    quar_detector_ok = True
    for c in cands:
        if c["decision"] == "QUARANTINED":
            txt = c["question"] + " " + " ".join(d["text"] for d in c["documents"])
            g = {**c["ann_graph"], "governing": c["ann_governing"], "abstain": c["ann_abstain"]}
            if not any(quarantine_recommended(similarity(txt, g, ot, og))
                       for ot, og in seed_pairs + acc_pairs):
                quar_detector_ok = False

    # difficulty calibration (retrospective; no seed relabel)
    seed_recal = []
    for sid, ann in seed_ann.items():
        f = factors_from_graph({"nodes": ann["gold_nodes"], "edges": ann["gold_edges"]},
                               ann["ambiguity"], ann["abstain"])
        rlvl = rubric_level(f)
        if rlvl != ann["difficulty"]:
            seed_recal.append({"id": sid, "seed_label": ann["difficulty"], "rubric": rlvl})
    pilot_recal = []
    for c in accepted:
        rlvl = adjudication_record(c)["final_difficulty"]
        if rlvl != c["proposed_difficulty"]:
            pilot_recal.append({"id": opaque_id(c), "proposed": c["proposed_difficulty"], "adjudicated": rlvl})

    # accepted coverage
    cap_counts = Counter()
    diff_counts = Counter()
    edge_counts = Counter()
    negctl = Counter()
    for c in accepted:
        for cap in c["intended_capability"]:
            cap_counts[cap] += 1
        diff_counts[adjudication_record(c)["final_difficulty"]] += 1
        for (_s, t, _d) in c["ann_graph"]["edges"]:
            edge_counts[t] += 1
        if c["negative_control"]:
            negctl[c["negative_control"]] += 1

    out = {
        "corpus": "hidden pilot curation", "synthetic": True,
        "counts": {"authored": len(cands), **{k: counts.get(k, 0) for k in ("ACCEPTED", "REJECTED", "QUARANTINED")}},
        "rejection_reasons": rej_reasons,
        "lifecycle_issues": lifecycle_issues,
        "blinding_issues": blinding_issues,
        "agreement": agreement,
        "duplicates": {"accepted_quarantine_hits": accepted_quarantine_hits,
                       "documented_overrides": overridden_hits,
                       "quarantine_detector_confirms_design_case": quar_detector_ok},
        "difficulty_recalibration": {"seed_recommendations": seed_recal, "pilot_deltas": pilot_recal},
        "gold_sufficiency_issues": gold_sufficiency.audit(),
        "answer_position": answer_position.audit(),
        "leakage_findings": leakage_pilot.verify(),
        "accepted_coverage": {"by_capability": dict(cap_counts),
                              "by_difficulty": dict(diff_counts),
                              "by_relationship_type": dict(edge_counts),
                              "negative_controls": dict(negctl)},
        "combined_corpus_size": {"seed": pilot_loader.seed_count(), "pilot": pilot_loader.pilot_count(),
                                 "total": pilot_loader.seed_count() + pilot_loader.pilot_count()},
    }

    # verdict
    gates = {
        "lifecycle_clean": not lifecycle_issues,
        "blinding_clean": not blinding_issues,
        "gold_sufficiency_clean": not out["gold_sufficiency_issues"],
        "leakage_clean": not out["leakage_findings"],
        "no_accepted_quarantine": not accepted_quarantine_hits,
        "quarantine_detector_works": quar_detector_ok,
        "no_answer_position_excess": not out["answer_position"]["excessive_flags"],
        "every_case_adjudicated": counts.get("ACCEPTED", 0) + counts.get("REJECTED", 0) + counts.get("QUARANTINED", 0) == len(cands),
    }
    out["gates"] = gates
    out["verdict"] = "CURATION PIPELINE VALIDATED" if all(gates.values()) else "CURATION PIPELINE NOT VALIDATED"
    return out


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "CURATION_AUDIT.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("=" * 82)
    print("HIDDEN CORPUS CURATION PIPELINE — AUDIT (no resolver run)")
    print("=" * 82)
    print(f"authored={out['counts']['authored']}  accepted={out['counts']['ACCEPTED']}  "
          f"rejected={out['counts']['REJECTED']}  quarantined={out['counts']['QUARANTINED']}")
    print(f"agreement edges P/R/F1 = {out['agreement']['edge_presence']['precision']}/"
          f"{out['agreement']['edge_presence']['recall']}/{out['agreement']['edge_presence']['f1']}"
          f"  abstention kappa={out['agreement']['abstention_kappa']}")
    print(f"gold sufficiency issues: {out['gold_sufficiency_issues'] or 'none'}")
    print(f"leakage findings: {out['leakage_findings'] or 'none'}")
    print(f"answer-position excess flags: {out['answer_position']['excessive_flags'] or 'none'}")
    print(f"accepted quarantine hits: {out['duplicates']['accepted_quarantine_hits'] or 'none'}  "
          f"detector-confirms-design: {out['duplicates']['quarantine_detector_confirms_design_case']}")
    print(f"combined corpus size: {out['combined_corpus_size']}")
    print("gates:")
    for k, v in out["gates"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nVERDICT: {out['verdict']}")


if __name__ == "__main__":
    main()
