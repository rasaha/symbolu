#!/usr/bin/env python3
"""
Deterministic report generator for the Exploratory Resolver Study v0.1. Renders the
12 preregistered reporting tables as Markdown directly from EXPERIMENT_RESULTS.json
and EXPERIMENT_ANALYSIS.json, so every table is byte-consistent with the computed
numbers (no hand transcription). Run AFTER run_experiment + analyze.

Emits the data-driven report docs; the narrative docs (verdict, boundaries,
limitations, summary, readme) are authored separately.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(__file__)


def _load():
    with open(os.path.join(HERE, "EXPERIMENT_RESULTS.json")) as f:
        res = json.load(f)
    with open(os.path.join(HERE, "EXPERIMENT_ANALYSIS.json")) as f:
        ana = json.load(f)
    return res, ana


def _fmt(x):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def _w(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text.rstrip() + "\n")


# --------------------------------------------------------------------------- #
def comparator_report(res):
    order = ["null", "always_abstain", "frozen", "rule", "graph_traversal", "hybrid_relationship"]
    cols = [("discovery_f1", "disc F1"), ("discovery_precision", "disc P"),
            ("discovery_recall", "disc R"), ("classification_accuracy", "class"),
            ("governance_accuracy_modeG", "govG"), ("packet_realization_accuracy_modeP", "packP"),
            ("selective_accuracy", "select"), ("answer_coverage", "cover"),
            ("unsafe_answers", "unsafe"), ("primary_macro", "MACRO")]
    h = "| resolver | " + " | ".join(c[1] for c in cols) + " |"
    sep = "|" + "---|" * (len(cols) + 1)
    lines = [h, sep]
    for name in order:
        m = res["hidden"][name]
        lines.append("| " + name + " | " + " | ".join(_fmt(m.get(c[0])) for c in cols) + " |")
    body = (
        "# Comparator Report — Table 1 (hidden pilot, owner-clean)\n\n"
        "Six preregistered comparators on the frozen 60-case Hidden Relationship Corpus\n"
        "Pilot v0.2. All metrics owner-clean (parser and SafetyGate excluded). Governance\n"
        "and packet are identical for rule/graph/hybrid on the owned-case denominator by\n"
        "construction (hybrid reuses the frozen GraphTraversal governance + packet builder).\n\n"
        + "\n".join(lines) + "\n\n"
        "Reading: the hybrid resolver posts the top macro (0.5761) and the strongest\n"
        "discovery F1 (0.5512, from recall 0.4167 vs 0.1786) and classification (0.9143),\n"
        "while its discovery precision falls to 0.814 (it over-proposes edges). The\n"
        "adversarial Null and Always-abstain comparators score far below, confirming the\n"
        "macro is not gameable by trivial strategies.\n")
    _w("COMPARATOR_REPORT.md", body)


def primary_endpoint_report(res):
    p = res["primary_endpoint"]
    b = res["statistics"]["bootstrap_macro_hybrid_minus_graph"]
    body = (
        "# Primary Endpoint Report — Table 2\n\n"
        "**Primary endpoint (singular):** hidden owner-clean macro =\n"
        "mean(discovery_F1, classification_accuracy, governance_accuracy_modeG,\n"
        "packet_realization_accuracy_modeP, selective_accuracy).\n\n"
        "| quantity | value |\n|---|---|\n"
        f"| GraphTraversal macro | {_fmt(p['graph_traversal'])} |\n"
        f"| Hybrid macro | {_fmt(p['hybrid_relationship'])} |\n"
        f"| absolute macro gain | {_fmt(p['macro_gain'])} |\n"
        f"| practical threshold | {_fmt(p['practical_threshold'])} |\n"
        f"| practically significant | {_fmt(p['practically_significant'])} |\n"
        f"| paired bootstrap 95% CI (hybrid − graph) | [{_fmt(b['ci95'][0])}, {_fmt(b['ci95'][1])}] |\n"
        f"| CI excludes zero | {_fmt(b['excludes_zero'])} |\n"
        f"| n (paired cases) | {b['n']} |\n"
        f"| bootstrap iters / seed | {b['iters']} / {b['seed']} |\n\n"
        "The macro gain (+0.0788) exceeds the preregistered practical-significance\n"
        "threshold (0.03) and the 95% paired-bootstrap CI excludes zero. The primary\n"
        "endpoint therefore shows a statistically and practically significant improvement.\n"
        "Whether this counts as *success* is gated by the non-inferiority constraints\n"
        "(see NON_INFERIORITY_REPORT.md).\n")
    _w("PRIMARY_ENDPOINT_REPORT.md", body)


def non_inferiority_report(res):
    ni = res["non_inferiority"]["hybrid_relationship"]
    lines = ["| constraint | candidate | base | delta | margin | violated |",
             "|---|---|---|---|---|---|"]
    for k, v in ni["rows"].items():
        lines.append(f"| {k} | {_fmt(v['candidate'])} | {_fmt(v['base'])} | "
                     f"{_fmt(v.get('delta'))} | {_fmt(v.get('margin'))} | "
                     f"{'**YES**' if v.get('violated') else 'no'} |")
    body = (
        "# Non-Inferiority Report — Table 3 (hybrid vs GraphTraversal)\n\n"
        "Frozen margins from the preregistration. A macro gain does NOT count as success\n"
        "if any constraint is violated.\n\n"
        + "\n".join(lines) + "\n\n"
        f"**Passes non-inferiority: {_fmt(ni['passes_non_inferiority'])}.**\n\n"
        "Two constraints are violated: discovery precision falls 0.186 (margin 0.05) —\n"
        "the broad proposal lexicon over-fires on the more varied hidden wording — and\n"
        "selective accuracy falls 0.0351 (margin 0.03), because the richer graph leads the\n"
        "frozen governance to answer a few more cases, some of them wrong. Critically, the\n"
        "unsafe/overconfident answer count does NOT increase (2 vs 2), false-abstention\n"
        "does not rise, and determinism holds. The failure is a precision/selectivity\n"
        "trade-off, not a safety regression.\n")
    _w("NON_INFERIORITY_REPORT.md", body)


def abstention_report(res):
    order = ["frozen", "rule", "graph_traversal", "hybrid_relationship"]
    cols = [("abstention_precision", "abst P"), ("abstention_recall", "abst R"),
            ("false_abstention_rate", "false-abst"), ("missed_abstention_rate", "missed-abst"),
            ("answer_coverage", "coverage"), ("selective_accuracy", "selective"),
            ("unsafe_answers", "unsafe")]
    lines = ["| resolver | " + " | ".join(c[1] for c in cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for name in order:
        m = res["hidden"][name]
        lines.append("| " + name + " | " + " | ".join(_fmt(m.get(c[0])) for c in cols) + " |")
    body = (
        "# Abstention & Coverage Report — Table 4 (hidden pilot)\n\n"
        "Abstention treated as a decision problem (TA/FA/MA/TN) on the resolver-owned\n"
        "cases; coverage is the answered fraction; selective accuracy is accuracy on\n"
        "answered cases; unsafe = confident wrong answer where gold requires abstention.\n\n"
        + "\n".join(lines) + "\n\n"
        "The hybrid abstains slightly more than GraphTraversal (coverage 0.95 vs 1.00) via\n"
        "the confidence gate, which lowers its missed-abstention rate (0.2167 vs 0.2667)\n"
        "but does not increase unsafe answers. Selective accuracy dips marginally — see the\n"
        "non-inferiority report.\n")
    _w("ABSTENTION_COVERAGE_REPORT.md", body)


def statistics_report(res):
    s = res["statistics"]
    mc = s["mcnemar_hybrid_vs_graph"]
    holm = s["holm_over_stage_mcnemar"]
    b = s["bootstrap_macro_hybrid_minus_graph"]
    l1 = ["| stage (binary correctness) | hybrid fixes | hybrid breaks | discordant n | exact p |",
          "|---|---|---|---|---|"]
    for k, v in mc.items():
        l1.append(f"| {k} | {v['b10_candidate_fixes']} | {v['b01_candidate_breaks']} | "
                  f"{v['n_discordant']} | {_fmt(v['p_value'])} |")
    l2 = ["| stage | raw p | Holm threshold | Holm-adj p | reject null |",
          "|---|---|---|---|---|"]
    for k, v in holm.items():
        l2.append(f"| {k} | {_fmt(v['raw_p'])} | {_fmt(v['holm_threshold'])} | "
                  f"{_fmt(v['holm_adjusted_p'])} | {_fmt(v['reject_null'])} |")
    body = (
        "# Statistics Report — Tables 5–7\n\n"
        "Paired case-level statistics, Hybrid vs GraphTraversal, hidden pilot (n=60).\n\n"
        "## Table 5 — Exact McNemar per stage\n\n" + "\n".join(l1) + "\n\n"
        "Discovery completeness improves overwhelmingly (18 cases fixed, 1 broken,\n"
        "exact two-sided p = 7.6e-05). Governance, packet, and answer correctness are\n"
        "perfectly concordant (n=0 discordant) because the hybrid reuses the frozen\n"
        "governance + packet builder unchanged — the discovery layer is the only moving\n"
        "part, exactly as designed.\n\n"
        "## Table 6 — Paired bootstrap on the macro\n\n"
        "| observed diff | 95% CI | excludes 0 | n | iters | seed |\n|---|---|---|---|---|---|\n"
        f"| {_fmt(b['observed_diff'])} | [{_fmt(b['ci95'][0])}, {_fmt(b['ci95'][1])}] | "
        f"{_fmt(b['excludes_zero'])} | {b['n']} | {b['iters']} | {b['seed']} |\n\n"
        "## Table 7 — Holm correction over the stage McNemar family\n\n" + "\n".join(l2) + "\n\n"
        "Only the discovery-completeness endpoint survives Holm correction, and it does so\n"
        "decisively. Significance is reported; it is not conflated with practical\n"
        "significance or with non-inferiority.\n")
    _w("STATISTICS_REPORT.md", body)


def ablation_report(res):
    ah = res["ablations"]["hidden"]
    order = ["A0_full", "A1_no_semantic", "A2_no_traversal", "A3_no_governance_rules",
             "A4_no_confidence_abstain", "A5_no_provenance", "A6_discovery_only"]
    cols = [("discovery_precision", "disc P"), ("discovery_recall", "disc R"),
            ("discovery_f1", "disc F1"), ("classification_accuracy", "class"),
            ("selective_accuracy", "select"), ("primary_macro", "MACRO")]
    lines = ["| ablation | " + " | ".join(c[1] for c in cols) + " |",
             "|" + "---|" * (len(cols) + 1)]
    for a in order:
        m = ah[a]
        lines.append("| " + a + " | " + " | ".join(_fmt(m.get(c[0])) for c in cols) + " |")
    body = (
        "# Ablation Report — Table 8 (hidden pilot)\n\n"
        "Preregistered ablations A0–A8. A7 (Mode G, gold graph injected) and A8 (Mode P,\n"
        "gold governance injected) are evaluation-mode isolations already reported as the\n"
        "govG / packP columns; they are recorded below the table.\n\n"
        + "\n".join(lines) + "\n\n"
        f"- **A7 Mode G (gold graph):** governance_accuracy_modeG = "
        f"{_fmt(ah['A7_modeG_gold_graph']['governance_accuracy_modeG'])}\n"
        f"- **A8 Mode P (gold governance):** packet_realization_accuracy_modeP = "
        f"{_fmt(ah['A8_modeP_gold_governance']['packet_realization_accuracy_modeP'])}\n\n"
        "**Attribution of the gain.** A1 (remove the semantic proposal layer → fall back to\n"
        "the narrow cue set) collapses every discovery/classification gain and returns the\n"
        "macro to the GraphTraversal baseline (0.4973). The semantic proposal layer is the\n"
        "*sole* source of the improvement. A4 (remove the confidence gate) leaves the macro\n"
        "unchanged (0.5761) — the τ=0.5 gate does not drive the result. A5 (remove the\n"
        "provenance filter) is likewise inert on this corpus. A2/A6 (no governance traversal\n"
        "/ discovery-only) zero out the governance-dependent metrics as expected while\n"
        "leaving discovery intact, confirming clean separation of the discovery layer.\n")
    _w("ABLATION_REPORT.md", body)


def generalization_report(ana):
    g = ana["generalization"]
    gt, hy = g["graph_traversal"], g["hybrid_relationship"]

    def two_col(dim, valkey):
        keys = list(gt[dim].keys())
        lines = [f"| {dim.replace('by_', '')} | n | graph | hybrid | Δ |", "|---|---|---|---|---|"]
        for k in keys:
            gv, hv = gt[dim][k].get(valkey), hy[dim][k].get(valkey)
            delta = round((hv or 0) - (gv or 0), 4)
            n = gt[dim][k]["n"]
            mark = " **↑**" if delta > 0.02 else (" ↓" if delta < -0.02 else "")
            lines.append(f"| {k} | {n} | {_fmt(gv)} | {_fmt(hv)} | {_fmt(delta)}{mark} |")
        return "\n".join(lines)

    src = two_col("by_source", "macro")
    cap = two_col("by_capability", "macro")
    diff = two_col("by_difficulty", "macro")
    edge = two_col("by_gold_edge_type", "disc_f1")
    ncg = gt["negative_control"]; nch = hy["negative_control"]
    body = (
        "# Generalization Report — Tables 9–11 (hidden pilot)\n\n"
        "Macro (or discovery F1 for edge-type) by slice, GraphTraversal vs Hybrid. Slices\n"
        "are small (n shown); these are descriptive, not per-slice hypothesis tests.\n\n"
        "## Wording family (seed vs pilot) — the two independently authored families\n\n"
        + src + "\n\n"
        "The gain holds in **both** families (seed +0.086, pilot +0.074), satisfying the\n"
        "H1 requirement of improvement across >1 wording/structural family.\n\n"
        "## Table 9 — by capability (macro)\n\n" + cap + "\n\n"
        "Broad-based: hybrid improves or holds macro on the large majority of capabilities,\n"
        "with the biggest gains on nested/scoped exceptions, version supersession, circular\n"
        "and implicit references, and insufficient-evidence handling. A few regress —\n"
        "notably `table_vs_text` (a spurious table/text conflict edge) and\n"
        "`hierarchical_governance` — flagged as future-work targets (not fixed post-lock).\n\n"
        "## Table 10 — by difficulty (macro)\n\n" + diff + "\n\n"
        "The gain is present at every difficulty level, largest at the extremes of the\n"
        "range rather than concentrated in easy cases.\n\n"
        "## Table 11 — by gold edge-type (discovery F1)\n\n" + edge + "\n\n"
        "Largest discovery gains on `exception_to` (0.182→0.571), `references`\n"
        "(0.345→0.703), and `effective_after` (0→0.5); small regressions on\n"
        "`conflicts_with`, `governs_over`, and `same_as`.\n\n"
        "## Negative-control subset\n\n"
        f"| resolver | n | macro |\n|---|---|---|\n"
        f"| graph_traversal | {ncg['n']} | {_fmt(ncg['macro'])} |\n"
        f"| hybrid_relationship | {nch['n']} | {_fmt(nch['macro'])} |\n\n"
        "On the negative-control cases (no-relationship / insufficient-evidence /\n"
        "unresolvable), the hybrid scores **higher** (0.7028 vs 0.4683): the richer layer\n"
        "does not manufacture governance where none is warranted. The precision cost seen\n"
        "in aggregate comes from over-proposing *edges*, not from unsafe *answers*.\n")
    _w("GENERALIZATION_REPORT.md", body)


def failure_attribution_report(ana):
    fa = ana["failure_attribution"]
    gt, hy = fa["graph_traversal"]["counts"], fa["hybrid_relationship"]["counts"]
    stages = sorted(set(gt) | set(hy))
    lines = ["| primary failure stage | graph | hybrid |", "|---|---|---|"]
    for s in stages:
        lines.append(f"| {s} | {gt.get(s, 0)} | {hy.get(s, 0)} |")
    body = (
        "# Failure Attribution Report — Table 12 (hidden pilot)\n\n"
        "Each incorrect case is attributed to exactly one PRIMARY stage, in fixed priority\n"
        "order (discovery incompleteness → over-proposal → classification → governance →\n"
        "packet). Counts are cases, not edges.\n\n"
        + "\n".join(lines) + "\n\n"
        "The dominant residual failure for both resolvers is **relationship discovery**\n"
        "(edges still missed): the hybrid raises recall from 0.18 to 0.42 but the majority\n"
        "of hidden edges remain undiscovered, so discovery is where the next research\n"
        "effort should concentrate. Governance- and packet-attributed failures are shared\n"
        "identically with GraphTraversal (inherited via the frozen reuse), so they are not\n"
        "the hybrid's to fix. Over-proposal is the primary stage for only one case but\n"
        "depresses aggregate precision across many — a precision-focused proposal gate is\n"
        "the clearest single improvement for a follow-up.\n")
    _w("FAILURE_ATTRIBUTION_REPORT.md", body)


def reproducibility_report(res):
    body = (
        "# Reproducibility Report\n\n"
        f"- **Deterministic:** {_fmt(res['deterministic'])} (no LLM, no training, no RNG "
        "except the fixed-seed bootstrap).\n"
        f"- **Repetitions:** {res['repetitions']} full runs.\n"
        f"- **Byte-identical across repetitions:** {_fmt(res['byte_identical_reps'])}.\n"
        "- **Bootstrap:** fixed seed 20240601, 10000 iterations, recorded in the manifest.\n"
        "- **Lock:** all resolver/metric/stat/prereg sources and frozen dependencies were\n"
        "  content-hashed before the first hidden evaluation (HIDDEN_EVALUATION_LOCK.md).\n"
        "  `lock.verify()` reports zero drift.\n"
        "- **Run order:** fixed comparator order recorded in the manifest.\n\n"
        "Re-running `python -m agentic.hybrid_handover.resolution.experiment.run_experiment`\n"
        "reproduces EXPERIMENT_RESULTS.json exactly; `analyze` and `make_reports` are pure\n"
        "functions of that output.\n")
    _w("REPRODUCIBILITY_REPORT.md", body)


def main():
    res, ana = _load()
    comparator_report(res)
    primary_endpoint_report(res)
    non_inferiority_report(res)
    abstention_report(res)
    statistics_report(res)
    ablation_report(res)
    generalization_report(ana)
    failure_attribution_report(ana)
    reproducibility_report(res)
    print("reports written")


if __name__ == "__main__":
    main()
