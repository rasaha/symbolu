"""Phase 15 (correlated-failure scenarios) + Phase 16 (missing-metadata degradation).

Phase 15: exercise the reference component across distinct correlated-failure mechanisms and record
escape + disposition per scenario. Scenarios = the eleven failure types embedded in the corpus, a
clean control, and constructed adversarial variants covering the hardest taxonomy rows (fabricated /
synthetic / model-consensus diversity) where the honest correct answer is abstention, not certainty.

Phase 16: progressively drop observed provenance metadata (0-70%) and measure whether the component
degrades *gracefully* — shifting to INDETERMINATE (abstain) rather than escaping. Silent escape under
missing metadata would be the dangerous failure; abstention is the safe one.

Deterministic. Writes eval_results/experiments_v1.json. Touches no prior-track artifact.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict

from . import dataset, assurance
from .taxonomy import delivered_as_supported

# taxonomy labels for the corpus failure-type codes (see CORRELATED_FAILURE_TAXONOMY.md)
TYPE_LABEL = {
    1: "shared_bad_retrieval", 4: "summaries_of_one_source", 5: "citation_circularity",
    8: "stale_replicated", 11: "wrong_passage_entailment", 12: "claim_citation_misalignment",
    13: "scope_inflation", 17: "authority_mismatch", 20: "missing_counterevidence",
    25: "synthetic_consensus", 29: "official_superseded", None: "clean_control",
}

# observed provenance fields dropped when simulating missing metadata
_PROV_FIELDS = ("observed_distinct_publishers", "observed_distinct_domains",
                "observed_distinct_retrieval_paths", "observed_upstream_ids",
                "observed_content_hashes", "observed_provenance_confidence")


def _score(cases):
    """escape / false-block / indeterminate over a set of case dicts."""
    esc = fb = indet = 0
    n_unsup = n_sup = 0
    dispo = Counter()
    for c in cases:
        res = assurance.assess(c)
        dispo[res.state] += 1
        gs = delivered_as_supported(c["gold_state"])
        ps = delivered_as_supported(res.state)
        if gs:
            n_sup += 1
        else:
            n_unsup += 1
        if ps and not gs:
            esc += 1
        if not ps and gs:
            fb += 1
        if res.state == "INDETERMINATE":
            indet += 1
    return {
        "n": len(cases),
        "escape": round(esc / n_unsup, 4) if n_unsup else 0.0,
        "false_block": round(fb / n_sup, 4) if n_sup else 0.0,
        "indeterminate_rate": round(indet / len(cases), 4) if cases else 0.0,
        "dispositions": dict(dispo),
    }


# ---------- Phase 15 ------------------------------------------------------------------------------

def _adversarial_variant(base, key, mutate):
    """Construct a scenario by mutating observed metadata to fake diversity/authority, keeping TRUE
    latent state (so gold is unchanged) — tests whether the component is fooled by observed lies."""
    out = []
    for c in base:
        d = dict(c)
        mutate(d)
        d["case_id"] = d["case_id"] + key
        out.append(d)
    return out


def correlated_failure_scenarios() -> dict:
    cases = [asdict(c) for c in dataset.all_cases()]
    by_type = {}
    for c in cases:
        by_type.setdefault(c["correlated_failure_type"], []).append(c)

    scenarios = {}
    # 1..12: the embedded failure types + clean control
    for t, group in sorted(by_type.items(), key=lambda x: (x[0] is not None, x[0])):
        scenarios[f"T{t}_{TYPE_LABEL.get(t, t)}"] = _score(group)

    # 13..20: constructed adversarial variants over the dependent/adversarial trap cases
    trap = [c for c in cases if c["partition"] in ("CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE")]

    def fake_publisher_diversity(d):
        d["observed_distinct_publishers"] = 6
        d["observed_distinct_domains"] = 6

    def fake_retrieval_diversity(d):
        d["observed_distinct_retrieval_paths"] = 5

    def fake_high_provconf(d):
        d["observed_provenance_confidence"] = 0.95

    def fake_all_diversity(d):
        fake_publisher_diversity(d); fake_retrieval_diversity(d); fake_high_provconf(d)

    def fake_distinct_hashes(d):
        d["observed_content_hashes"] = [f"h{i}" for i in range(6)]

    def fake_recent_years(d):
        d["observed_publication_years"] = [2024, 2024, 2024]

    def fake_authority(d):
        d["observed_authority_classes"] = ["reputable"] * 4

    def fake_upstream_roots(d):
        # the load-bearing attack: fabricate DISTINCT upstream roots + high provenance confidence,
        # so the independence layer is told the sources are genuinely independent.
        d["observed_upstream_ids"] = [f"u{i}" for i in range(4)]
        d["observed_provenance_confidence"] = 0.95

    def fake_everything(d):
        fake_all_diversity(d); fake_distinct_hashes(d); fake_recent_years(d); fake_authority(d)

    def fake_everything_incl_upstream(d):
        fake_everything(d); fake_upstream_roots(d)

    scenarios["S13_fake_publisher_diversity"] = _score(
        _adversarial_variant(trap, "P", fake_publisher_diversity))
    scenarios["S14_fake_retrieval_diversity"] = _score(
        _adversarial_variant(trap, "R", fake_retrieval_diversity))
    scenarios["S15_fake_high_provenance_conf"] = _score(
        _adversarial_variant(trap, "C", fake_high_provconf))
    scenarios["S16_fake_all_diversity"] = _score(
        _adversarial_variant(trap, "A", fake_all_diversity))
    scenarios["S17_fake_distinct_hashes"] = _score(
        _adversarial_variant(trap, "H", fake_distinct_hashes))
    scenarios["S18_fake_recent_years"] = _score(
        _adversarial_variant(trap, "Y", fake_recent_years))
    scenarios["S19_fake_authority"] = _score(
        _adversarial_variant(trap, "U", fake_authority))
    scenarios["S20_fake_everything_no_upstream"] = _score(
        _adversarial_variant(trap, "E", fake_everything))
    # the honest breaking point: fabricate the upstream/provenance signal itself
    scenarios["S21_fake_upstream_roots"] = _score(
        _adversarial_variant(trap, "G", fake_upstream_roots))
    scenarios["S22_fake_everything_incl_upstream"] = _score(
        _adversarial_variant(trap, "F", fake_everything_incl_upstream))

    # S23 — the honest ceiling. A "no-tell" correlated failure: the claim is FALSE, but every
    # OBSERVABLE signal says supported — passage aligned (no NLI tell), NO discoverable
    # counterevidence, and fabricated-but-plausible independent provenance. This is taxonomy
    # types 23/30 (model consensus on a false premise / training contamination): the dependence and
    # the error live entirely outside the evidence record. The corpus never contains this case (every
    # trap case there carries at least one tell), so we construct it to measure where the component
    # MUST fail. Expectation: it escapes — no metadata-based method can catch a failure that leaves
    # no metadata trace. This bounds the component and motivates external verification (Phase 23).
    verified = [c for c in cases if c["gold_state"] == "VERIFIED"]

    def make_no_tell(d):
        d["true_claim_correct"] = False           # ground truth: the claim is wrong
        d["gold_state"] = "REJECT_EVIDENCE_STATE"  # so it counts as an escape if delivered
        d["gold_delivery"] = "REJECT"
        d["partition"] = "CORRELATED_FAILURE"
        # observed signals are left fully supportive (no tell): aligned, fresh, authoritative,
        # independent-looking, no counterevidence.
        d["observed_alignment_signal"] = True
        d["observed_passage_aligned"] = True
        d["true_counterevidence_exists"] = False
        d["observed_upstream_ids"] = [f"u{i}" for i in range(4)]
        d["observed_provenance_confidence"] = 0.95

    scenarios["S23_no_tell_correlated_failure"] = _score(
        _adversarial_variant(verified, "N", make_no_tell))
    return scenarios


# ---------- Phase 16 ------------------------------------------------------------------------------

def _drop_metadata(case, rho, salt):
    """Deterministically drop observed provenance metadata for a rho fraction of cases (keyed by
    case id + salt). A dropped case has provenance fields emptied and metadata_complete=False."""
    idx = int("".join(ch for ch in case["case_id"] if ch.isdigit()) or "0")
    if (idx * 7 + salt) % 100 >= rho * 100:
        return case
    d = dict(case)
    for f in _PROV_FIELDS:
        if f == "observed_provenance_confidence":
            d[f] = 0.0
        elif f.startswith("observed_distinct"):
            d[f] = 0
        else:
            d[f] = []
    d["metadata_complete"] = False
    return d


def missing_metadata_study() -> dict:
    cases = [asdict(c) for c in dataset.all_cases()]
    rows = []
    for pct in range(0, 71, 10):
        rho = pct / 100.0
        degraded = [_drop_metadata(c, rho, salt=3) for c in cases]
        s = _score(degraded)
        rows.append({"missingness": rho, **{k: s[k] for k in
                     ("escape", "false_block", "indeterminate_rate")}})
    return {"missingness_sweep": rows}


def run() -> dict:
    return {
        "corpus": dataset.DATASET_VERSION,
        "phase15_correlated_failure_scenarios": correlated_failure_scenarios(),
        "phase16_missing_metadata": missing_metadata_study(),
    }


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "experiments_v1.json")
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)

    print(f"corpus={r['corpus']}")
    print("\nPhase 15 — correlated-failure scenarios (escape must be ~0; abstention is safe):")
    print(f"  {'scenario':38} {'n':>4} {'escape':>7} {'indet':>7}")
    for name, s in r["phase15_correlated_failure_scenarios"].items():
        print(f"  {name:38} {s['n']:>4} {s['escape']:>7.3f} {s['indeterminate_rate']:>7.3f}")

    print("\nPhase 16 — missing-metadata degradation (escape must stay ~0; INDETERMINATE should rise):")
    print(f"  {'missingness':>11} {'escape':>7} {'false_block':>12} {'indeterminate':>14}")
    for row in r["phase16_missing_metadata"]["missingness_sweep"]:
        print(f"  {row['missingness']:>11.2f} {row['escape']:>7.3f} "
              f"{row['false_block']:>12.3f} {row['indeterminate_rate']:>14.3f}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
