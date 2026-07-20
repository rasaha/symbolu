#!/usr/bin/env python3
"""
Exploratory Resolver Study v0.1 — orchestrator.

Runs the six preregistered comparators (Null, Always-abstain, Frozen, Rule,
GraphTraversal, Hybrid) and the preregistered ablations A0..A8 on BOTH the visible
development corpus (frozen measurement package) and the frozen 60-case Hidden
Relationship Corpus Pilot v0.2 (experiment.hidden_metrics, which re-applies the
frozen owner-clean definitions to the hidden data). Fully deterministic; two
repetitions must be byte-identical.

Nothing frozen is modified: the visible path calls the frozen measurement
functions verbatim; the hidden path re-implements the frozen definitions without
touching the spec code.

The primary endpoint is the HIDDEN owner-clean macro. Non-inferiority is checked
against GraphTraversalResolver on the frozen margins. All statistics
(exact McNemar, paired bootstrap CI, Holm) are computed from per-case vectors.
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.audit.adversarial import AlwaysAbstain, NullResolver
from agentic.hybrid_handover.resolution.measurement.abstention import abstention_metrics
from agentic.hybrid_handover.resolution.measurement.stage_metrics import (
    discovery_classification, governance_modeG, packet_modeP,
)
from agentic.hybrid_handover.resolution.resolvers import (
    FrozenResolver, GraphTraversalResolver, RuleResolver,
)

from . import hidden_metrics, stats
from .hidden_data import hidden_cases
from .hybrid_resolver import ABLATIONS, HybridRelationshipResolver

OUT_DIR = os.path.dirname(__file__)

# frozen run order (recorded in the manifest)
COMPARATORS = [
    ("null", NullResolver),
    ("always_abstain", AlwaysAbstain),
    ("frozen", FrozenResolver),
    ("rule", RuleResolver),
    ("graph_traversal", GraphTraversalResolver),
    ("hybrid_relationship", HybridRelationshipResolver),
]

# frozen non-inferiority margins vs graph_traversal (positive = degradation limit)
NI_MARGINS = {
    "discovery_precision": ("decrease", 0.05),
    "governance_accuracy_modeG": ("decrease", 0.03),
    "packet_realization_accuracy_modeP": ("decrease", 0.03),
    "selective_accuracy": ("decrease", 0.03),
    "false_abstention_rate": ("increase", 0.05),
    "missed_abstention_rate": ("increase", 0.05),
    "answer_coverage": ("decrease", 0.10),
}


# --------------------------------------------------------------------------- #
# visible corpus (frozen measurement package, verbatim)
# --------------------------------------------------------------------------- #
def _visible_metrics(resolver, cases):
    dc = discovery_classification(resolver, cases)
    gg = governance_modeG(resolver, cases)
    pp = packet_modeP(resolver, cases)
    ab = abstention_metrics(resolver, cases)
    disc_p, disc_r = dc["discovery_precision"], dc["discovery_recall"]
    disc_f1 = round(2 * disc_p * disc_r / (disc_p + disc_r), 4) if disc_p and disc_r else None
    m = {
        "discovery_precision": disc_p, "discovery_recall": disc_r, "discovery_f1": disc_f1,
        "classification_accuracy": dc["classification_accuracy"],
        "governance_accuracy_modeG": gg["governance_accuracy_modeG"],
        "packet_realization_accuracy_modeP": pp["packet_realization_accuracy_modeP"],
        "abstention_precision": ab["abstention_precision"], "abstention_recall": ab["abstention_recall"],
        "answer_coverage": ab["answer_coverage"], "selective_accuracy": ab["selective_accuracy"],
    }
    c = ab["_counts"]
    m["false_abstention_rate"] = round(c["FA"] / (c["TA"] + c["FA"] + c["MA"] + c["TN"]), 4) \
        if (c["TA"] + c["FA"] + c["MA"] + c["TN"]) else None
    m["missed_abstention_rate"] = round(c["MA"] / (c["TA"] + c["FA"] + c["MA"] + c["TN"]), 4) \
        if (c["TA"] + c["FA"] + c["MA"] + c["TN"]) else None
    macro_parts = [disc_f1, m["classification_accuracy"], m["governance_accuracy_modeG"],
                   m["packet_realization_accuracy_modeP"], m["selective_accuracy"]]
    m["primary_macro"] = round(sum(x or 0 for x in macro_parts) / len(macro_parts), 4)
    m["_counts"] = c
    return m


# --------------------------------------------------------------------------- #
# per-case macro recompute (for paired bootstrap on the hidden set)
# --------------------------------------------------------------------------- #
def _macro_from_records(records: list[dict]) -> float:
    d_hit = sum(r["discovery_hit"] for r in records)
    d_pred = sum(r["pred_pairs"] for r in records)
    d_ref = sum(r["gold_pairs"] for r in records)
    c_ok = sum(r["class_ok"] for r in records)
    c_tot = sum(r["class_tot"] for r in records)
    owned = [r for r in records if r["owned"]]
    gg = [r["governanceG"] for r in owned if r["governanceG"] is not None]
    pp = [r["packetP"] for r in owned if r["packetP"] is not None]
    answered = [r for r in owned if r["answered"]]
    p = d_hit / d_pred if d_pred else 0.0
    rc = d_hit / d_ref if d_ref else 0.0
    f1 = 2 * p * rc / (p + rc) if (p + rc) else 0.0
    cls = c_ok / c_tot if c_tot else 0.0
    g = sum(gg) / len(gg) if gg else 0.0
    pk = sum(pp) / len(pp) if pp else 0.0
    sel = sum(1 for r in answered if r["answer_correct"]) / len(answered) if answered else 0.0
    return (f1 + cls + g + pk + sel) / 5


def _bootstrap_macro(rec_a: list[dict], rec_b: list[dict],
                     iters: int = stats.BOOTSTRAP_ITERS, seed: int = stats.BOOTSTRAP_SEED) -> dict:
    import random
    n = len(rec_a)
    obs = _macro_from_records(rec_a) - _macro_from_records(rec_b)
    rng = random.Random(seed)
    diffs = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(_macro_from_records([rec_a[i] for i in idx])
                     - _macro_from_records([rec_b[i] for i in idx]))
    diffs.sort()
    lo = diffs[int((stats.CI_ALPHA / 2) * iters)]
    hi = diffs[int((1 - stats.CI_ALPHA / 2) * iters) - 1]
    return {"observed_diff": round(obs, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "n": n, "iters": iters, "seed": seed, "excludes_zero": bool(lo > 0 or hi < 0)}


# --------------------------------------------------------------------------- #
# non-inferiority check
# --------------------------------------------------------------------------- #
def _non_inferiority(cand: dict, base: dict) -> dict:
    rows = {}
    ok = True
    for metric, (direction, margin) in NI_MARGINS.items():
        cv, bv = cand.get(metric), base.get(metric)
        if cv is None or bv is None:
            rows[metric] = {"candidate": cv, "base": bv, "delta": None, "violated": False}
            continue
        delta = round(cv - bv, 4)
        if direction == "decrease":
            violated = (bv - cv) > margin
        else:
            violated = (cv - bv) > margin
        rows[metric] = {"candidate": cv, "base": bv, "delta": delta,
                        "margin": margin, "direction": direction, "violated": violated}
        ok = ok and not violated
    unsafe_c = cand.get("unsafe_answers", 0)
    unsafe_b = base.get("unsafe_answers", 0)
    unsafe_violated = unsafe_c > unsafe_b
    rows["unsafe_answers"] = {"candidate": unsafe_c, "base": unsafe_b,
                              "delta": unsafe_c - unsafe_b, "violated": unsafe_violated}
    ok = ok and not unsafe_violated
    return {"passes_non_inferiority": ok, "rows": rows}


# --------------------------------------------------------------------------- #
# main run (one repetition)
# --------------------------------------------------------------------------- #
def _one_rep():
    vcases = all_cases()
    hcases = hidden_cases()

    visible = {name: _visible_metrics(cls(), vcases) for name, cls in COMPARATORS}
    hidden = {}
    hidden_percase = {}
    for name, cls in COMPARATORS:
        ev = hidden_metrics.evaluate(cls(), hcases)
        hidden[name] = ev["metrics"]
        hidden_percase[name] = ev["per_case"]

    # ablations A0..A6 (resolver-config) on both corpora
    abl_visible, abl_hidden, abl_hidden_pc = {}, {}, {}
    for aname, cfg in ABLATIONS.items():
        r = HybridRelationshipResolver(cfg)
        abl_visible[aname] = _visible_metrics(r, vcases)
        ev = hidden_metrics.evaluate(HybridRelationshipResolver(cfg), hcases)
        abl_hidden[aname] = ev["metrics"]
        abl_hidden_pc[aname] = ev["per_case"]

    # A7 (Mode G isolation) and A8 (Mode P isolation) are already the govG / packP
    # columns in the metric harness (gold graph / gold governance injected). Record
    # them explicitly for the full hybrid as preregistered ablations.
    abl_hidden["A7_modeG_gold_graph"] = {
        "governance_accuracy_modeG": hidden["hybrid_relationship"]["governance_accuracy_modeG"]}
    abl_hidden["A8_modeP_gold_governance"] = {
        "packet_realization_accuracy_modeP": hidden["hybrid_relationship"]["packet_realization_accuracy_modeP"]}

    return {"visible": visible, "hidden": hidden, "hidden_percase": hidden_percase,
            "ablations": {"visible": abl_visible, "hidden": abl_hidden},
            "ablations_hidden_percase": abl_hidden_pc}


def _aligned(pc_a: dict, pc_b: dict, field: str, owned_only=True):
    """Aligned per-case binary vectors for two resolvers (skip None on either)."""
    a, b = [], []
    for cid in pc_a:
        ra, rb = pc_a[cid], pc_b[cid]
        if owned_only and not (ra["owned"] and rb["owned"]):
            continue
        va, vb = ra[field], rb[field]
        if va is None or vb is None:
            continue
        a.append(bool(va)); b.append(bool(vb))
    return a, b


def _stats_block(hidden_percase: dict) -> dict:
    """Paired stats: Hybrid vs GraphTraversal on the hidden set."""
    hy = hidden_percase["hybrid_relationship"]
    gt = hidden_percase["graph_traversal"]
    # McNemar per stage
    mcnemar = {}
    for field in ("discovery_complete", "governanceG", "packetP", "answer_correct"):
        a, b = _aligned(hy, gt, field, owned_only=(field != "discovery_complete"))
        mcnemar[field] = stats.mcnemar_exact(a, b)
    # bootstrap on the macro (aligned case order)
    cids = list(hy)
    rec_a = [dict(hy[c], cid=c) for c in cids]
    rec_b = [dict(gt[c], cid=c) for c in cids]
    boot = _bootstrap_macro(rec_a, rec_b)
    # Holm over the secondary-endpoint McNemar p-values
    holm = stats.holm({k: v["p_value"] for k, v in mcnemar.items()})
    return {"mcnemar_hybrid_vs_graph": mcnemar, "bootstrap_macro_hybrid_minus_graph": boot,
            "holm_over_stage_mcnemar": holm}


def run():
    rep1 = _one_rep()
    rep2 = _one_rep()
    s1 = json.dumps(rep1, sort_keys=True, default=str)
    s2 = json.dumps(rep2, sort_keys=True, default=str)
    byte_identical = (s1 == s2)

    hidden = rep1["hidden"]
    ni = {name: _non_inferiority(hidden[name], hidden["graph_traversal"])
          for name, _ in COMPARATORS}
    stat = _stats_block(rep1["hidden_percase"])

    base_macro = hidden["graph_traversal"]["primary_macro"]
    hy_macro = hidden["hybrid_relationship"]["primary_macro"]
    macro_gain = round(hy_macro - base_macro, 4)

    result = {
        "study": "Exploratory Resolver Study v0.1",
        "resolver_under_test": "HybridRelationshipResolver Experimental v0.1",
        "corpus": "Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)",
        "deterministic": True, "repetitions": 2, "byte_identical_reps": byte_identical,
        "primary_endpoint": {
            "name": "hidden_owner_clean_macro",
            "graph_traversal": base_macro, "hybrid_relationship": hy_macro,
            "macro_gain": macro_gain, "practical_threshold": 0.03,
            "practically_significant": macro_gain >= 0.03,
        },
        "visible": rep1["visible"],
        "hidden": hidden,
        "non_inferiority": ni,
        "statistics": stat,
        "ablations": rep1["ablations"],
    }
    return result


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "EXPERIMENT_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps({
        "byte_identical_reps": out["byte_identical_reps"],
        "primary": out["primary_endpoint"],
        "hybrid_non_inferiority": out["non_inferiority"]["hybrid_relationship"]["passes_non_inferiority"],
    }, indent=2))
    return out


if __name__ == "__main__":
    main()
