"""Baseline characterization (Phase 8). Reports per method: avg claims per output, claim-count error
vs gold, and a first-look fragile-dimension preservation rate. Full semantic-preservation scoring is
metrics.py (Phase 11); downstream impact is Phase 18. Deterministic. Writes eval_results/baselines.json.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from . import dataset, baselines, detect


def _fragile_preserved(gold_claim, produced_texts) -> bool:
    """Is the gold claim's fragile dimension still recoverable somewhere in the produced claims?
    Lexical dims via the detector; structural dims (population/scope/reference) via substring of the
    load-bearing phrase."""
    frag = gold_claim["fragile_dimension"]
    joined = " ".join(produced_texts).lower()
    if frag in ("population",):
        pop = (gold_claim.get("population") or "").lower()
        return bool(pop) and pop in joined
    if frag == "exceptions" or frag == "scope":
        exc = gold_claim.get("exceptions") or []
        cond = gold_claim.get("conditions") or []
        needles = [x.lower() for x in exc + cond] or ["unless", "except"]
        return any(n in joined for n in needles)
    if frag == "reference":
        # reference preserved iff the resolved subject/population survived WITHOUT a dangling pronoun
        pop = (gold_claim.get("population") or "").lower()
        has_dangling = " it " in (" " + joined + " ")
        return bool(pop) and pop in joined and not has_dangling
    key = detect.FRAGILE_TO_DETECTOR.get(frag)
    if not key:
        return True
    dd = detect.detect_dimensions(joined)
    if frag == "polarity":
        return dd["polarity"] == "negated"
    if frag == "attribution":
        return dd["attribution"] == "attributed"
    if frag == "normative_status":
        return dd["normative_status"] == "normative"
    if frag == "causal_direction":
        return dd["causal_direction"] == "correlational"
    val = dd.get(key)
    return val not in (False, "none")


def evaluate() -> dict:
    exs = [asdict(e) for e in dataset.all_examples()]
    n_gold_claims = sum(len(e["gold_claims"]) for e in exs)
    rows = []
    for name, fn in baselines.BASELINES.items():
        total_produced = 0
        count_err = 0
        frag_preserved = 0
        frag_total = 0
        for e in exs:
            produced = fn(e)
            total_produced += len(produced)
            count_err += abs(len(produced) - e["expected_claim_count"])
            for g in e["gold_claims"]:
                frag_total += 1
                if _fragile_preserved(g, produced):
                    frag_preserved += 1
        rows.append({
            "method": name,
            "simulated": name in baselines.SIMULATED,
            "avg_claims_per_output": round(total_produced / len(exs), 3),
            "mean_claim_count_error": round(count_err / len(exs), 3),
            "fragile_preservation_rate": round(frag_preserved / frag_total, 4),
            "rule_count": _RULE_COUNT.get(name, 0),
            "external_deps": _EXTERNAL.get(name, "none (local approximation)"),
            "model_calls": 0,
        })
    return {"corpus": dataset.DATASET_VERSION, "n_examples": len(exs),
            "n_gold_claims": n_gold_claims, "results": rows}


# honest metadata: rule counts and what the real method would depend on
_RULE_COUNT = {"A_preserve_whole": 0, "B_sentence_split": 1, "C_clause_split": 2, "D_dependency": 5,
               "E_srl": 5, "F_openie": 5, "G_rule_spo": 5, "H_citation_aware_split": 2,
               "N_minimal_split": 3, "O_aggressive_split": 2, "M_equivalence_filter": 2, "Q_oracle": 0,
               "R_learned_comparator": 4}
_EXTERNAL = {"D_dependency": "spaCy/parser (unavailable -> local approx)",
             "E_srl": "SRL model (unavailable -> local approx)",
             "F_openie": "OpenIE (unavailable -> local approx)",
             "G_rule_spo": "none (local approx)",
             "I_llm_simple": "LLM (no live calls -> deterministic sim)",
             "J_llm_schema": "LLM (no live calls -> deterministic sim)",
             "K_llm_selfcheck": "LLM (no live calls -> deterministic sim)",
             "L_hybrid": "LLM+rules (no live calls -> deterministic sim)",
             "R_learned_comparator": "trained extractor (unavailable -> fixed-rule sim)"}


def main() -> None:
    r = evaluate()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "baselines.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print(f"corpus={r['corpus']} n={r['n_examples']} gold_claims={r['n_gold_claims']}")
    print(f"{'method':24} {'sim':4} {'claims/out':>10} {'count_err':>9} {'fragile_preserved':>18}")
    for row in sorted(r["results"], key=lambda x: -x["fragile_preservation_rate"]):
        sim = "sim" if row["simulated"] else ""
        print(f"{row['method']:24} {sim:4} {row['avg_claims_per_output']:>10.2f} "
              f"{row['mean_claim_count_error']:>9.2f} {row['fragile_preservation_rate']:>18.3f}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
