"""
run_full.py — full matrix (gated on a VALID pilot). Decisive: A3 vs A1 and A3 vs best(A4,A5,A6),
with multi-seed variance, an N=4096 check, held-out generalization, and full Phase causal controls.
Emits PHASE_QUALITY_AUXILIARY_RESULTS.json and the §14 acceptance + §18 verdict.

Scoped for compute: decisive arms get 3 seeds at N=1024; A0/A2 get 1 seed; A1/A3/A5 get an N=4096
check and held-out (unseen entity IDs, unseen templates, train@1024→eval@4096 for longer sequences).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .dataset import Schema, generate, TARGETS
from .quality_heads import HealthModel
from .train import train_health
from .evaluate import evaluate
from .causal_controls import phase_causal_controls

HERE = Path(__file__).resolve().parent
RES = HERE / "results" / "PHASE_QUALITY_AUXILIARY_RESULTS.json"
STEPS = 800
SEEDS = (0, 1, 2)

# held-out pools
TRAIN_SUBJ = list(range(24)); HOLDOUT_SUBJ = list(range(24, 32))
TRAIN_TMPL = list(range(8)); HOLDOUT_TMPL = list(range(8, 12))


def _bs(N):
    return 16 if N <= 1024 else 8


def _train(arm, S, N, seed, steps, subj_pool=None, tmpl_pool=None):
    torch.manual_seed(seed)
    m = HealthModel(S, arm=arm)
    train_health(m, lambda bs, s: generate(S, N, bs, s, subj_pool, tmpl_pool), S,
                 steps=steps, batch_size=_bs(N), seed=seed)
    return m


def _macro(r):
    return {"macro_auroc": r["macro_auroc"], "macro_auprc": r["macro_auprc"],
            "macro_brier": r["macro_brier"],
            "per_target_auroc": {t: r[t]["auroc"] for t in TARGETS},
            "anomaly_fp_on_harmless": r["anomaly_fp_on_harmless"], "recurrence_fn": r["recurrence_fn"]}


def run():
    S = Schema(); t0 = time.time()
    res = {"steps": STEPS, "seeds": list(SEEDS), "N1024": {}, "N4096": {}, "heldout": {}, "causal": {}}
    te1k = generate(S, 1024, 300, 900001)

    # ---- N=1024 multi-seed ----
    seed_arms = {"A0": (0,), "A2": (0,), "A1": SEEDS, "A3": SEEDS, "A4": SEEDS, "A5": SEEDS, "A6": SEEDS}
    a3_models = {}
    for arm, seeds in seed_arms.items():
        runs = []
        for sd in seeds:
            m = _train(arm, S, 1024, sd, STEPS)
            runs.append(_macro(evaluate(m, te1k, S)))
            if arm == "A3" and sd == 0:
                a3_models[0] = m
            print(f"N1024 {arm} seed{sd}: macro={runs[-1]['macro_auroc']:.3f} ({time.time()-t0:.0f}s)", flush=True)
        macro = sum(r["macro_auroc"] for r in runs) / len(runs)
        res["N1024"][arm] = {"seeds": runs, "mean_macro_auroc": macro,
                             "mean_macro_auprc": sum(r["macro_auprc"] for r in runs) / len(runs),
                             "mean_macro_brier": sum(r["macro_brier"] for r in runs) / len(runs),
                             "mean_per_target": {t: sum(r["per_target_auroc"][t] for r in runs) / len(runs)
                                                 for t in TARGETS},
                             "params": HealthModel(S, arm=arm).trainable_params(),
                             "phase_state_bytes": HealthModel(S, arm=arm).phase_state_bytes()}
        RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- N=4096 check (decisive arms, 1 seed) ----
    te4k = generate(S, 4096, 200, 900004)
    for arm in ("A1", "A3", "A5"):
        m = _train(arm, S, 4096, 0, 700)
        res["N4096"][arm] = _macro(evaluate(m, te4k, S))
        print(f"N4096 {arm}: macro={res['N4096'][arm]['macro_auroc']:.3f} ({time.time()-t0:.0f}s)", flush=True)
        RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- held-out generalization (train restricted, eval on unseen) ----
    for arm in ("A1", "A3", "A5"):
        out = {}
        m_e = _train(arm, S, 1024, 0, STEPS, subj_pool=TRAIN_SUBJ, tmpl_pool=TRAIN_TMPL)
        out["unseen_entity"] = evaluate(m_e, generate(S, 1024, 300, 900010, HOLDOUT_SUBJ, TRAIN_TMPL), S)["macro_auroc"]
        out["unseen_template"] = evaluate(m_e, generate(S, 1024, 300, 900011, TRAIN_SUBJ, HOLDOUT_TMPL), S)["macro_auroc"]
        out["in_distribution"] = evaluate(m_e, generate(S, 1024, 300, 900012, TRAIN_SUBJ, TRAIN_TMPL), S)["macro_auroc"]
        # longer sequences: train@1024 model evaluated on N=4096
        out["longer_4096"] = evaluate(m_e, generate(S, 4096, 150, 900013, TRAIN_SUBJ, TRAIN_TMPL), S)["macro_auroc"]
        res["heldout"][arm] = out
        print(f"heldout {arm}: {json.dumps({k: round(v, 3) for k, v in out.items()})} ({time.time()-t0:.0f}s)", flush=True)
        RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- full Phase causal controls on A3 ----
    res["causal"] = phase_causal_controls(a3_models[0], te1k, S)
    print(f"causal: {json.dumps({k: (v if isinstance(v, bool) else round(v.get('macro_auroc', 0), 3)) for k, v in res['causal'].items()}, default=float)}", flush=True)

    # ---- §14 acceptance ----
    a1 = res["N1024"]["A1"]["mean_macro_auroc"]; a3 = res["N1024"]["A3"]["mean_macro_auroc"]
    a1p = res["N1024"]["A1"]["mean_macro_auprc"]; a3p = res["N1024"]["A3"]["mean_macro_auprc"]
    a1b = res["N1024"]["A1"]["mean_macro_brier"]; a3b = res["N1024"]["A3"]["mean_macro_brier"]
    best_base = max(res["N1024"][a]["mean_macro_auroc"] for a in ("A4", "A5", "A6"))
    a3_4k = res["N4096"]["A3"]["macro_auroc"]; a1_4k = res["N4096"]["A1"]["macro_auroc"]
    ho = res["heldout"]["A3"]
    cc = res["causal"]
    accept = {
        "A3_auroc_gain_ge_0.05": (a3 - a1) >= 0.05,
        "A3_auprc_gain_ge_0.05": (a3p - a1p) >= 0.05,
        "A3_brier_rel_improve_ge_10pct": (a1b - a3b) / max(1e-9, a1b) >= 0.10,
        "gain_preserved_at_4096": (a3_4k - a1_4k) >= 0.05,
        "gain_preserved_heldout": (ho["unseen_entity"] - a1) >= 0.05 and (ho["unseen_template"] - a1) >= 0.05,
        "gain_collapses_under_phase_corruption": cc.get("causal_dependence_verified", False),
        "beats_best_temporal_baseline_by_0.03": (a3 - best_base) >= 0.03,
    }
    accept["PASS"] = all(accept.values())
    res["acceptance"] = accept
    res["summary"] = {"A1": a1, "A3": a3, "best_baseline": best_base, "A3_minus_A1": a3 - a1,
                      "A3_minus_best_baseline": a3 - best_base}
    res["verdict"] = {
        "phase_information_health_value": (
            "validated" if accept["PASS"] else
            "useful_but_not_phase_specific" if (a3 - a1) >= 0.03 and (a3 - best_base) < 0.03 else
            "unsupported"),
        "authorized_production_role": "auxiliary quality sensor" if accept["PASS"] else "none",
    }
    RES.write_text(json.dumps(res, indent=2, default=float))
    print("ACCEPTANCE:", json.dumps(accept, default=float), flush=True)
    print("VERDICT:", json.dumps(res["verdict"], default=float), flush=True)
    print("FULL DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
