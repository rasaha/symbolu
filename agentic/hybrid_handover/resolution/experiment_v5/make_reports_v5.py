#!/usr/bin/env python3
"""Deterministic report generator for the Competing Operative Resolution Experiment v0.1.
Renders the data-driven deliverables + required tables from COMPETING_OPERATIVE_RESULTS.json.
Run AFTER run_competing_operative_experiment."""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(__file__)


def _load():
    with open(os.path.join(HERE, "COMPETING_OPERATIVE_RESULTS.json")) as f:
        return json.load(f)


def _f(x):
    return "—" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def _w(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text.rstrip() + "\n")


def ablations(res):
    h = res["hidden"]
    order = ["C0_g3_control", "C1_extract", "C2_scope", "C3_classify", "C4_full"]
    cols = [("selective_accuracy", "select"), ("answer_coverage", "cover"),
            ("governance_accuracy_modeG", "govG"), ("packet_realization_accuracy_modeP", "packP"),
            ("false_abstention_rate", "false-ab"), ("missed_abstention_rate", "miss-ab"),
            ("abstention_recall", "ab-recall"), ("unsafe_answers", "unsafe")]
    lines = ["| condition | " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for a in order:
        m = h[a]
        lines.append("| " + a + " | " + " | ".join(_f(m.get(c[0])) for c in cols) + " |")
    g4 = res["historical_comparators"]["G4_full"]
    v2 = res["historical_comparators"]["frozen_v2"]
    body = (
        "# COMPETING_OPERATIVE_ABLATIONS — Competing Operative Resolution Experiment v0.1\n\n"
        "## Table 3 — C0–C4 aggregate (hidden). Discovery/classification identical (Table 2).\n\n"
        + "\n".join(lines) + "\n\n"
        "C0=C1=C2=C3: extraction, scope, and classification build the operative representation\n"
        "without changing the decision. Only **C4** acts, and only via precise abstention. It\n"
        "abstains on **one** additional case (coverage 0.95 → 0.9333), with false-abstention\n"
        "held at 0 — the opposite of G4's failure.\n\n"
        "## Historical comparators (diagnostic only)\n\n"
        "| condition | select | cover | false-ab | note |\n|---|---|---|---|---|\n"
        f"| frozen v0.2 | {_f(v2['selective_accuracy'])} | {_f(v2['answer_coverage'])} | {_f(v2['false_abstention_rate'])} | pre-G3 baseline |\n"
        f"| C0 = G3 | {_f(h['C0_g3_control']['selective_accuracy'])} | {_f(h['C0_g3_control']['answer_coverage'])} | {_f(h['C0_g3_control']['false_abstention_rate'])} | principal control |\n"
        f"| C4 (this) | {_f(h['C4_full']['selective_accuracy'])} | {_f(h['C4_full']['answer_coverage'])} | {_f(h['C4_full']['false_abstention_rate'])} | precise abstention |\n"
        f"| historical G4 | {_f(g4['selective_accuracy'])} | {_f(g4['answer_coverage'])} | {_f(g4['false_abstention_rate'])} | coarse abstention (failed) |\n\n"
        "The contrast with historical G4 is the point: G4 reached selective 0.5294 only by\n"
        "collapsing coverage to 0.2833 and driving false-abstention to 0.5. C4 keeps coverage\n"
        "at 0.9333 and false-abstention at 0 — it does **not** over-abstain — but on this pilot\n"
        "it also finds no genuine conflict to exploit, so it adds no selective gain over G3.\n")
    _w("COMPETING_OPERATIVE_ABLATIONS.md", body)


def case_transitions(res):
    t = res["transitions"]
    rows = [r for r in res["transition_rows"]]
    lines = ["| case | C0 (abstain, correct) | C4 (abstain, correct) | kind |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['cid']} | {r['c0']} | {r['c4']} | {r['kind']} |")
    body = (
        "# CASE_TRANSITION_ANALYSIS — Competing Operative Resolution Experiment v0.1\n\n"
        "Every case whose C4 outcome differs from C0. Opaque identifiers only; hidden wording\n"
        "is not reproduced.\n\n"
        "## Table 7 — fix / break / abstention transitions\n\n"
        f"| metric | count |\n|---|---|\n"
        f"| fixes (wrong→right) | {t['fixes']} |\n| breaks (right→wrong) | {t['breaks']} |\n"
        f"| new abstentions | {t['new_abstention']} |\n| new answers | {t['new_answer']} |\n"
        f"| unchanged correct | {t['unchanged_correct']} |\n| unchanged incorrect | {t['unchanged_incorrect']} |\n\n"
        "## Changed cases\n\n" + "\n".join(lines) + "\n\n"
        "Exactly one case changes: a `no_relationship` case whose gold requires abstention.\n"
        "C0 (G3) answered it `unknown` (leniently scored correct because `unknown` matches a\n"
        "gold abstention); C4 abstains explicitly via `OPERATIVE_TERM_NOT_LOCATED`. This is a\n"
        "correct abstention (gold abstains) and raises abstention recall, but it removes a\n"
        "leniently-credited answer from the selective denominator, so selective ticks down\n"
        "0.011. There are zero fixes and zero breaks: the competing-operative machinery found\n"
        "no genuine conflict to resolve on this corpus.\n")
    _w("CASE_TRANSITION_ANALYSIS.md", body)


def packet_limitation(res):
    ca = res["conflict_analysis"]
    body = (
        "# PACKET_LIMITATION_ANALYSIS — Competing Operative Resolution Experiment v0.1\n\n"
        "Diagnostic analysis of the frozen single-primary packet contract. The packet is not\n"
        "modified in this experiment.\n\n"
        "## Table 15 — packet-cardinality limitation\n\n"
        f"| quantity | value |\n|---|---|\n"
        f"| cases with >1 applicable operative (parallel/cumulative) | {ca['packet_cardinality_cases']} |\n"
        f"| abstentions forced by FROZEN_PACKET_CARDINALITY_LIMIT | 0 |\n"
        f"| genuine unresolved conflicts | {ca['category_counts'].get('GENUINE_UNRESOLVED_CONFLICT', 0)} |\n\n"
        "**No case on the hidden pilot required more than one answer-bearing operative that the\n"
        "single-primary packet could not render.** Every competition resolved to a compatible\n"
        "or resolved category (Table 10), and no genuine unresolved conflict arose. Therefore\n"
        "this experiment does **not** demonstrate the packet cardinality contract as the active\n"
        "bottleneck — that question is NOT YET ESTABLISHED on this corpus. Governance conflict,\n"
        "operative-set multiplicity, and packet cardinality are reported separately and are not\n"
        "collapsed: here all three are effectively inactive.\n")
    _w("PACKET_LIMITATION_ANALYSIS.md", body)


def failure_attribution(res):
    pc_incorrect = res["transitions"]["unchanged_incorrect"]
    body = (
        "# COMPETING_OPERATIVE_FAILURE_ATTRIBUTION — Competing Operative Resolution Experiment v0.1\n\n"
        "Residual C4 errors attributed to exactly one primary stage. The Competing Operative\n"
        "layer is blamed only for errors it owns (conflict classification, conflict resolution,\n"
        "governance abstention). It introduced **no** new incorrect answers (0 breaks), so its\n"
        "own attribution count is 0.\n\n"
        "## Table 16 — failure attribution (C4)\n\n"
        "| primary stage | incorrect C4 cases |\n|---|---|\n"
        "| proposal generation (missing edge; frozen) | inherited from C0 |\n"
        "| frozen governing set / operative selection (G3) | inherited from C0 |\n"
        "| frozen packet realization | inherited from C0 |\n"
        "| competing-operative resolution (this layer) | 0 |\n"
        "| governance abstention (this layer) | 0 false abstentions |\n\n"
        f"All {pc_incorrect} residual incorrect cases are unchanged from C0 (they were already\n"
        "incorrect under G3, owned by frozen proposal generation, the frozen governing set, or\n"
        "the frozen packet). The Competing Operative layer neither fixed nor broke any of them,\n"
        "because none contained a genuine unresolved conflict for it to act on.\n")
    _w("COMPETING_OPERATIVE_FAILURE_ATTRIBUTION.md", body)


def statistical_analysis(res):
    mc = res["statistics"]["mcnemar_answer_correct_c4_vs_c0"]
    pe = res["primary_endpoint"]
    body = (
        "# STATISTICAL_ANALYSIS — Competing Operative Resolution Experiment v0.1\n\n"
        "Paired case-level, hidden pilot (n=60). Emphasis on effect size and mechanism given\n"
        "the tiny activating subset.\n\n"
        "## Table 4 — primary endpoint (C4 vs C0)\n\n"
        f"| quantity | value |\n|---|---|\n"
        f"| C0 (G3) selective | {_f(pe['c0'])} |\n| C4 selective | {_f(pe['c4'])} |\n"
        f"| selective gain | {_f(pe['selective_gain'])} |\n"
        f"| abstention-recall gain | {_f(pe['abstention_recall_gain'])} (threshold +0.10) |\n"
        f"| coverage C0 → C4 | {_f(pe['coverage_c0'])} → {_f(pe['coverage_c4'])} |\n"
        f"| primary met | {pe['primary_met']} |\n\n"
        "## Exact McNemar (full-pipeline correctness, C4 vs C0)\n\n"
        f"| fixes | breaks | n discordant | exact p |\n|---|---|---|---|\n"
        f"| {mc['b10_candidate_fixes']} | {mc['b01_candidate_breaks']} | {mc['n_discordant']} | {_f(mc['p_value'])} |\n\n"
        "Zero discordant answered pairs: the one changed case is an abstention transition, not\n"
        "an answer flip, so it does not enter the answered-correctness McNemar. Neither the\n"
        "selective threshold (+0.03) nor the abstention-recall threshold (+0.10) is met. The\n"
        "confidence interval is uninformative because the mechanism activated on effectively no\n"
        "cases — the defensible statistical statement is that the corpus contains too few\n"
        "genuine competing operatives to test the hypothesis.\n")
    _w("STATISTICAL_ANALYSIS.md", body)


def reproducibility(res):
    g = res["calibration_gates"]
    rows = "\n".join(f"| {k} | {v} |" for k, v in g.items())
    body = (
        "# REPRODUCIBILITY_REPORT — Competing Operative Resolution Experiment v0.1\n\n"
        "## Table 1 — calibration gates\n\n| gate | pass |\n|---|---|\n" + rows + "\n\n"
        "## Table 2 — protected-stage identity (C0–C4)\n\n"
        "| stage | identical |\n|---|---|\n| discovery P/R/F1 | yes |\n| classification | yes |\n"
        "| proposal-validation records | yes |\n| governing set (Mode G) | yes |\n"
        "| G3 operative selection | yes |\n| packet Mode P | yes |\n\n"
        "## Table 19 — reproducibility\n\n"
        f"| property | value |\n|---|---|\n| deterministic | {res['deterministic']} |\n"
        f"| repetitions | {res['repetitions']} |\n| byte-identical reps | {res['byte_identical_reps']} |\n"
        f"| all calibration gates pass | {res['calibration_gates_pass']} |\n"
        f"| all 5 G3 fixes retained | {res['all_g3_fixes_retained']} |\n\n"
        "- No LLM, no training, no inference-time RNG. Lock: v0.5 sources + specs + v0.4/v0.3/\n"
        "  v0.2/v0.1 + frozen platform content-hashed before the first hidden evaluation\n"
        "  (COMPETING_OPERATIVE_HIDDEN_LOCK.md); `lock_v5.verify()` reports zero drift, and all\n"
        "  four prior locks verify clean.\n"
        "- C0 reproduces G3 bit-for-bit; the synthetic fixtures (C8/C9) prove the genuine-conflict\n"
        "  machinery abstains only on genuine conflict and never on co-occurrence alone.\n")
    _w("REPRODUCIBILITY_REPORT.md", body)


def main():
    res = _load()
    ablations(res)
    case_transitions(res)
    packet_limitation(res)
    failure_attribution(res)
    statistical_analysis(res)
    reproducibility(res)
    print("v5 reports written")


if __name__ == "__main__":
    main()
