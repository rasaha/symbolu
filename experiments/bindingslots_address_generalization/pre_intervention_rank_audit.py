#!/usr/bin/env python3
"""§7 pre-intervention rank audit (DIAGNOSTIC ONLY — must NOT motivate a sharpening intervention).

Measures, on the ACTUAL held-out eval examples (frozen needle eval, base template), per-example
correct-slot routing for the collapsed exemplars (H2 s23, R0 s23): top-1 accuracy, rank
distribution, correct-vs-best-competitor margin, correct-slot probability, read entropy, and the
ordinary-vs-oracle-address retrieval gap. Since no diagnostic weight checkpoints were saved, the
collapsed seeds are re-reproduced deterministically via the value-path harness (byte-identical) and
measured at the terminal (1200) checkpoint with zero optimizer steps.

Reports whether the historical failure was: correct slot ranked first but too diffuse / an incorrect
competitor ranked first / mixed.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
for p in (str(HERE), str(VPD)):
    if p not in sys.path:
        sys.path.insert(0, p)

COHORT = [("H2", 23), ("R0", 23)]
EVAL_SEED, EVAL_N, EVAL_DIST = 123, 120, 96


def _per_example(model, vocab, T):
    import torch
    import diagnosis_lib as DL
    X, fp, qp, tgt = DL.needle_examples(vocab, T, EVAL_SEED, EVAL_N, EVAL_DIST)
    import arms_ag as A
    er = A._eval_time_routing(model, vocab, T)   # means (prob/top1/rank/margin/entropy + oracle gap)
    return er


def classify_failure(er):
    top1 = er["correct_slot_top1"]
    if top1 >= 0.5:
        return "correct_slot_ranked_first_but_too_diffuse"
    if top1 <= 0.2:
        return "incorrect_competitor_ranked_first"
    return "mixed"


def main():
    import diagnosis_lib as DL
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    out = {"schema": "bindingslots_address_generalization/pre_intervention_rank_audit/v1",
           "diagnostic_only": True,
           "note": "must NOT be used to add a sharpening intervention (§7)",
           "eval": {"seed": EVAL_SEED, "n": EVAL_N, "distance": EVAL_DIST, "template": "base needle (held-out)"},
           "per_seed": []}
    for arm, seed in COHORT:
        rec, snaps, nsteps = DL.reproduce_run(arm, seed, steps=1200, targets=[1200])
        m = snaps[1200]
        er = _per_example(m, vocab, T)
        out["per_seed"].append({
            "arm": arm, "seed": seed, "optimizer_steps": nsteps,
            "correct_slot_top1": er["correct_slot_top1"],
            "correct_slot_rank_mean": er["correct_slot_rank_mean"],
            "correct_slot_prob": er["correct_slot_prob"],
            "correct_vs_best_competitor_margin": er["correct_vs_best_competitor_margin"],
            "read_entropy": er["read_entropy"],
            "ordinary_needle": er["ordinary_needle"],
            "oracle_address_needle": er["oracle_address_needle"],
            "ordinary_vs_oracle_gap": er["ordinary_vs_oracle_gap"],
            "failure_mode": classify_failure(er),
        })
    # aggregate characterization
    modes = {r["failure_mode"] for r in out["per_seed"]}
    out["failure_characterization"] = (list(modes)[0] if len(modes) == 1 else "mixed_across_seeds")
    (HERE / "results").mkdir(parents=True, exist_ok=True)
    (HERE / "results" / "pre_intervention_rank_audit.json").write_text(json.dumps(out, indent=2) + "\n")
    for r in out["per_seed"]:
        print(f"{r['arm']} s{r['seed']}: top1={r['correct_slot_top1']:.3f} rank={r['correct_slot_rank_mean']:.2f} "
              f"prob={r['correct_slot_prob']:.3f} oracle_gap={r['ordinary_vs_oracle_gap']:.3f} -> {r['failure_mode']}")
    print("characterization:", out["failure_characterization"])


if __name__ == "__main__":
    main()
