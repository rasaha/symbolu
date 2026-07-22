#!/usr/bin/env python3
"""Run the naming evaluation. Produces every DETERMINISTIC metric now (no model needed) and, if an LLM
is reachable, also the outcome metrics (generation + blinded judging + stats). Writes JSON + report.

Deterministic metrics: token/char cost & prompt growth, injected-payload symbolic honesty, arm
distinctness, random-control length parity, ablation field costs, determinism.
Outcome metrics (candidate quality, explanation quality, portfolio consistency): require a live LLM;
recorded as LLM_UNAVAILABLE when none is reachable — never fabricated.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent.parent
sys.path.insert(0, str(_HERE))
import corpus as C            # noqa: E402
import arms as A              # noqa: E402
import judge as J             # noqa: E402

# decode-CLAIM phrases the task flags as symbolic dishonesty (about a person/customer).
CLAIM_PHRASES = ["this proves", "this reveals", "this means the customer", "means the customer",
                 "reveals the customer", "proves that", "the name means", "decodes the", "reveals that you",
                 "this shows you are"]
RAW_DECODE = ["proves", "reveals", "decodes"]           # looser incidental count (excludes 'means' — see note)


def est_tokens(s):
    return (len(s) + 3) // 4                             # ~4 chars/token heuristic (approximate)


def conditioning_of(prompt):
    # everything after the CONSTRAINTS line is the injected conditioning
    i = prompt.find("\nCONSTRAINTS:")
    tail = prompt[i:].split("\n", 1)
    return tail[1] if len(tail) > 1 else ""


def deterministic_metrics():
    rows = []
    for it in C.CORPUS:
        arms, c_src = A.all_arms(it, C.CORPUS)
        # determinism: rebuild B twice, byte-identical
        det = A.arm_B(it) == A.arm_B(it)
        distinct = len(set(arms.values())) == 4
        b_cond = conditioning_of(arms["B_profile"])
        claim_hits = sum(b_cond.lower().count(p) for p in CLAIM_PHRASES)
        raw_hits = sum(b_cond.lower().count(w) for w in RAW_DECODE)
        toks = {k: est_tokens(v) for k, v in arms.items()}
        rows.append({
            "id": it["id"], "category": it["category"], "seed": it["seed_concept"],
            "c_random_source": c_src, "determinism": det, "distinct_arms": distinct,
            "tokens": toks,
            "growth_B_over_A": toks["B_profile"] - toks["A_baseline"],
            "growth_D_over_A": toks["D_minimal"] - toks["A_baseline"],
            "B_vs_C_char_diff": abs(len(arms["B_profile"]) - len(arms["C_random"])),
            "injected_claim_phrases": claim_hits, "injected_raw_decode_tokens": raw_hits,
        })
    return rows


def ablation_metrics():
    out = []
    for it in C.CORPUS:
        abl = A.ablations(it)
        base = est_tokens(abl["B_full"])
        out.append({"id": it["id"],
                    "field_token_cost": {k: base - est_tokens(v) for k, v in abl.items() if k != "B_full"},
                    "B_full_tokens": base})
    return out


def aggregate(rows, abl):
    g = [r["growth_B_over_A"] for r in rows]
    gd = [r["growth_D_over_A"] for r in rows]
    ctrl = [r["B_vs_C_char_diff"] for r in rows]
    n = len(rows)
    def ci95(xs):
        if len(xs) < 2:
            return [xs[0], xs[0]] if xs else [0, 0]
        m = statistics.mean(xs); sd = statistics.pstdev(xs)
        h = 1.96 * sd / (len(xs) ** 0.5)
        return [round(m - h, 1), round(m + h, 1)]
    # ablation: mean token cost per removed field
    fields = ["abl_no_trajectory", "abl_no_binding", "abl_no_liberating", "abl_no_provenance",
              "abl_shuffled_order"]
    field_cost = {f: round(statistics.mean(a["field_token_cost"][f] for a in abl), 1) for f in fields}
    return {
        "n_items": n,
        "prompt_growth_B_over_A_tokens": {"mean": round(statistics.mean(g), 1),
                                          "stdev": round(statistics.pstdev(g), 1),
                                          "ci95": ci95(g), "min": min(g), "max": max(g)},
        "prompt_growth_D_over_A_tokens": {"mean": round(statistics.mean(gd), 1),
                                          "stdev": round(statistics.pstdev(gd), 1)},
        "random_control_B_vs_C_char_diff": {"mean": round(statistics.mean(ctrl), 1),
                                            "max": max(ctrl)},
        "determinism_all": all(r["determinism"] for r in rows),
        "distinct_arms_all": all(r["distinct_arms"] for r in rows),
        "injected_claim_phrases_total": sum(r["injected_claim_phrases"] for r in rows),
        "injected_raw_decode_tokens_total": sum(r["injected_raw_decode_tokens"] for r in rows),
        "ablation_field_token_cost_mean": field_cost,
    }


def maybe_outcome_metrics():
    if not J.llm_available():
        return dict(J.UNAVAILABLE)
    # Full generation + blinded judging pipeline (runs only when a model is reachable).
    per_item = []
    for it in C.CORPUS:
        arms, _ = A.all_arms(it, C.CORPUS)
        gen = {a: J.generate(p) for a, p in arms.items()}
        if any(isinstance(v, dict) for v in gen.values()):
            return {"status": "LLM_PARTIAL", "detail": "generation failed mid-run", "item": it["id"]}
        # blind: flatten one candidate per arm, hide labels, judge
        picks = {a: (v[0] if v else "") for a, v in gen.items()}
        labelled, l2a = J.blind_shuffle(picks, salt=it["id"])
        scores = J.judge(it["brief"], [c for _, c in labelled])
        per_item.append({"id": it["id"], "gen": gen, "label_to_arm": l2a, "scores": scores})
    return {"status": "RAN", "per_item": per_item}


def main():
    rows = deterministic_metrics()
    abl = ablation_metrics()
    agg = aggregate(rows, abl)
    outcome = maybe_outcome_metrics()
    result = {"corpus_size": len(C.CORPUS), "deterministic_per_item": rows,
              "ablation_per_item": abl, "aggregate": agg, "outcome_metrics": outcome}
    (_HERE / "naming_eval_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Naming evaluation — deterministic metrics")
    print(f"  corpus items: {len(C.CORPUS)}")
    print(f"  prompt growth B over A (tokens): mean={agg['prompt_growth_B_over_A_tokens']['mean']} "
          f"ci95={agg['prompt_growth_B_over_A_tokens']['ci95']} "
          f"range=[{agg['prompt_growth_B_over_A_tokens']['min']},{agg['prompt_growth_B_over_A_tokens']['max']}]")
    print(f"  prompt growth D over A (tokens): mean={agg['prompt_growth_D_over_A_tokens']['mean']}")
    print(f"  random-control B-vs-C char diff: mean={agg['random_control_B_vs_C_char_diff']['mean']} "
          f"(low = good length parity)")
    print(f"  determinism all: {agg['determinism_all']}   distinct arms all: {agg['distinct_arms_all']}")
    print(f"  injected decode-CLAIM phrases: {agg['injected_claim_phrases_total']}  "
          f"(raw decode tokens: {agg['injected_raw_decode_tokens_total']})")
    print(f"  ablation field token cost (mean): {agg['ablation_field_token_cost_mean']}")
    print(f"  OUTCOME METRICS: {outcome.get('status', outcome)}")
    print(f"wrote {(_HERE / 'naming_eval_results.json').relative_to(_REPO)}")
    return result


if __name__ == "__main__":
    main()
