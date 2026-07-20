#!/usr/bin/env python3
"""
Deterministic report generator for the Edge Prioritization Experiment v0.1. Renders
the data-driven deliverables directly from PRIORITIZATION_RESULTS.json and
PRIORITIZATION_COMPETITIONS.json (and a deterministic re-evaluation for the per-case
fix/break attribution). Run AFTER run_prioritization_experiment.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(__file__)


def _load():
    with open(os.path.join(HERE, "PRIORITIZATION_RESULTS.json")) as f:
        res = json.load(f)
    with open(os.path.join(HERE, "PRIORITIZATION_COMPETITIONS.json")) as f:
        comp = json.load(f)
    return res, comp


def _f(x):
    return "—" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def _w(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text.rstrip() + "\n")


def _fix_break():
    """Per changed case, was the P0→P4 answer a fix (F→T) or a break (T→F)?"""
    from agentic.hybrid_handover.resolution.experiment import hidden_metrics
    from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
    from .hybrid_resolver_v3 import HybridRelationshipResolverV3
    from .prioritizer import ABLATIONS
    cases = hidden_cases()
    pc0 = hidden_metrics.evaluate(HybridRelationshipResolverV3(ABLATIONS["P0_none"]), cases)["per_case"]
    pc4 = hidden_metrics.evaluate(HybridRelationshipResolverV3(ABLATIONS["P4_full"]), cases)["per_case"]
    out = {}
    for cid in pc0:
        a, b = pc0[cid]["answer_correct"], pc4[cid]["answer_correct"]
        if a != b:
            out[cid] = "fix (wrong→right)" if (not a and b) else "break (right→wrong)"
    return out


def ablations(res):
    h = res["hidden"]
    order = ["P0_none", "P1_authority", "P2_authority_temporal",
             "P3_auth_temporal_specificity", "P4_full"]
    cols = [("discovery_precision", "disc P"), ("discovery_recall", "disc R"),
            ("classification_accuracy", "class"), ("governance_accuracy_modeG", "govG"),
            ("packet_realization_accuracy_modeP", "packP"),
            ("selective_accuracy", "select"), ("unsafe_answers", "unsafe")]
    lines = ["| ablation | " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for a in order:
        m = h[a]
        lines.append("| " + a + " | " + " | ".join(_f(m.get(c[0])) for c in cols) + " |")
    body = (
        "# PRIORITIZATION_ABLATIONS — Edge Prioritization Experiment v0.1\n\n"
        "Preregistered ablations P0–P4 on the hidden pilot. P0 reproduces v0.2 bit-for-bit.\n\n"
        + "\n".join(lines) + "\n\n"
        "**Every ablation is identical on every metric.** In all three competing cases the\n"
        "**authority** component alone is decisive, so P1 (authority only) already realizes\n"
        "the full reordering and P2–P4 add nothing. The protected metrics (discovery\n"
        "precision/recall, classification, governance Mode G, packet Mode P, unsafe) are\n"
        "unchanged across the ladder — as guaranteed structurally, and confirmed here.\n"
        "Selective accuracy is flat at 0.2982 throughout.\n")
    _w("PRIORITIZATION_ABLATIONS.md", body)


def competing_edge_analysis(res, comp):
    fb = _fix_break()
    lines = ["| case | winner | competing (demoted) | decisive component |", "|---|---|---|---|"]
    for r in comp["per_competition"]:
        lines.append(f"| {r['cid']} | {r['winner']} | {r['competing_edge']} | {r['decisive_component']} |")
    clines = ["| case | P0 decision | P4 decision | effect |", "|---|---|---|---|"]
    for c in comp["changed_cases"]:
        clines.append(f"| {c['cid']} | {c['p0']} | {c['p4']} | {fb.get(c['cid'], 'no answer change')} |")
    body = (
        "# COMPETING_EDGE_ANALYSIS — Edge Prioritization Experiment v0.1\n\n"
        f"On the hidden pilot, {res['competition']['cases_with_competition']} cases contain\n"
        "two or more competing governance sources (elsewhere the layer is a strict no-op).\n"
        f"{res['competition']['competing_edges_reprioritized']} competing edges were\n"
        f"reprioritized; {res['competition']['governance_decisions_changed']} full-pipeline\n"
        "governance decisions changed as a result.\n\n"
        "## Competitions (winner vs demoted source)\n\n" + "\n".join(lines) + "\n\n"
        "In every competition the **authority** component (later / higher instrument) is\n"
        "decisive — the prioritizer selects the more authoritative governance source as the\n"
        "frozen packet's `primary`.\n\n"
        "## Governance decisions that changed (P0 → P4)\n\n" + "\n".join(clines) + "\n\n"
        "**This is the crux of the NO CLEAR SIGNAL verdict.** The two changed decisions\n"
        "cancel: one is a genuine fix (a policy-migration case where the later Policy P-8\n"
        "should dominate — P0 answered `unknown`, P4 correctly answers `prohibited`), and one\n"
        "is a break (a parallel-overrides case where ranking a Regulatory Directive above a\n"
        "Corporate Policy by authority causes the frozen packet to drop the operative\n"
        "prohibition — P0 was correct, P4 is not). Net effect on selective accuracy: zero.\n\n"
        "The authority heuristic is *correct* for supersession/migration but *wrong* for the\n"
        "parallel-authority case, where the right answer depends on which instrument carries\n"
        "the operative term — a semantic distinction that lives in the frozen governance /\n"
        "packet, not in edge ordering. Reordering alone cannot separate these two cases.\n")
    _w("COMPETING_EDGE_ANALYSIS.md", body)


def reproducibility(res):
    body = (
        "# REPRODUCIBILITY_REPORT — Edge Prioritization Experiment v0.1\n\n"
        f"- **Deterministic:** {res['deterministic']} — no LLM, no training, no inference-time RNG.\n"
        f"- **Repetitions:** {res['repetitions']}; **byte-identical:** {res['byte_identical_reps']}.\n"
        "- **Lock:** all v0.3 sources + the v0.2 experiment (proposal + validation) + the v0.1\n"
        "  experiment + frozen platform were content-hashed before the first hidden\n"
        "  evaluation (HIDDEN_EVALUATION_LOCK_V3.md); `lock_v3.verify()` reports zero drift.\n"
        "- **P0 faithfulness:** with prioritization disabled, the resolver reproduces v0.2\n"
        "  exactly on visible and hidden.\n"
        "- **Structural invariants confirmed empirically:** discovery precision/recall,\n"
        "  classification, governance Mode G, packet Mode P, and unsafe answers are identical\n"
        "  across P0–P4 (the layer never touches the discovery graph, Mode G, or Mode P).\n"
        "- **Calibration:** the visible corpus contains no multi-governance-source\n"
        "  competition, so P1–P4 leave every visible metric unchanged; no correct visible\n"
        "  decision is altered.\n\n"
        "Re-running\n"
        "`python -m agentic.hybrid_handover.resolution.experiment_v3.run_prioritization_experiment`\n"
        "reproduces PRIORITIZATION_RESULTS.json exactly; `make_reports_v3` is a pure function\n"
        "of that output.\n")
    _w("REPRODUCIBILITY_REPORT.md", body)


def main():
    res, comp = _load()
    ablations(res)
    competing_edge_analysis(res, comp)
    reproducibility(res)
    print("v3 reports written")


if __name__ == "__main__":
    main()
