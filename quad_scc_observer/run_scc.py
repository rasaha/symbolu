#!/usr/bin/env python
"""Main driver: build per-query SCC dataset, evaluate S/R/E/T vs baselines, save RESULTS/."""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import torch

import scc  # noqa: F401
from scc.dataset import build_all
from scc import evaluate, redundancy, plots

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "RESULTS")


def to_jsonable(o):
    if isinstance(o, dict):
        return {str(k): to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (int, float, str, bool)) or o is None:
        return o
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--n-batches", type=int, default=30)
    ap.add_argument("--M", type=int, default=4)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    os.makedirs(OUT, exist_ok=True)
    seeds = args.seeds[:1] if args.quick else args.seeds
    nb = 6 if args.quick else args.n_batches
    t0 = time.time()
    print(f"=== SCC observer study: seeds={seeds} n_batches={nb} M={args.M} ===")

    bundle = build_all(seeds, n_batches=nb, M=args.M)
    print(f"[data built in {time.time()-t0:.0f}s]")
    res = evaluate.run(bundle)

    # redundancy on pooled usable data
    data = bundle["data"]; usable = res["usable_conditions"]
    keys = list(data[seeds[0]][usable[0]].keys())
    pool = {k: np.concatenate([data[s][c][k] for s in seeds for c in usable]) for k in keys}
    red = redundancy.compute(pool)

    # ---- console summary ----
    print("\n=== ARM AUROC (pooled over seeds) ===")
    for c, r in res["per_condition"].items():
        if "arms" not in r:
            print(f"  {c:18s} n={r['n']} fail%={r['failure_rate']:.2f} [skipped]"); continue
        a = r["arms"]
        print(f"  {c:18s} fail%={r['failure_rate']:.2f} conf={a['1_confidence']['auroc']:.3f} "
              f"conf+ground={a['3_conf_ground']['auroc']:.3f} cg+T={a.get('7_cg_T',{}).get('auroc',float('nan')):.3f} "
              f"fullSCC={a['9_full_scc']['auroc']:.3f}")
    pa = res["pooled"]["arms"]
    print("\n  POOLED: " + "  ".join(f"{k}={pa[k]['auroc']:.3f}" for k in
          ["1_confidence","2_conf_entail","3_conf_ground","7_cg_T","9_full_scc","9b_cg_full_scc"] if k in pa))
    print("  term-alone AUROC:", {k: round(v,3) for k,v in res["pooled"].get("term_alone",{}).items()})

    print("\n=== INCREMENTAL ΔAUROC (pooled; term added to base) ===")
    inc = res["pooled"].get("increments", {})
    for t in ["S","R","E","T"]:
        if t not in inc: continue
        row = " ".join(f"{b.replace('over_',''):>18s}: dAUC={inc[t][b]['delta_auroc']:+.4f}(p={inc[t][b]['p_one_sided']:.3g},sig={inc[t][b]['significant_and_meaningful']})"
                       for b in ["over_confidence","over_conf_entail","over_conf_entail_ground"])
        print(f"  {t}: {row}")

    print("\n=== REDUNDANCY (best feature per term; corr with baselines) ===")
    for t, feats in red.items():
        best = max(feats.items(), key=lambda kv: (kv[1]["oriented_auroc"] if kv[1]["oriented_auroc"]==kv[1]["oriented_auroc"] else 0))
        b = best[1]
        print(f"  {t}: {best[0]} auroc={b['oriented_auroc']:.3f} "
              f"corr[conf]={b['max_corr_confidence']:.2f} corr[entail]={b['max_corr_entailment']:.2f} corr[ground]={b['max_corr_grounding']:.2f}")

    V = res["verdict"]
    print(f"\n=== VERDICT: {V['verdict']} ===")
    print(f"  intrinsic survivors (over conf+entail): {V['intrinsic_survivors_over_conf_entail']}")
    print(f"  survivors over confidence: {V['survivors_over_confidence']}")
    print(f"  grounding oracle: {V['grounding_is_closed_world_oracle']} (grounding AUROC={V['grounding_auroc']:.3f}, confidence={V['confidence_auroc']:.3f})")

    plots.make_all(res, os.path.join(OUT, "plots"))
    payload = {"config": {k: bundle[k] for k in ("seeds","conditions","n_batches","batch_size","M","alpha")},
               "model_acc": bundle["model_acc"], "results": res, "redundancy": red,
               "wall_clock_s": time.time()-t0}
    with open(os.path.join(OUT, "scc_results.json"), "w") as f:
        json.dump(to_jsonable(payload), f, indent=2)
    print(f"\nWrote RESULTS/scc_results.json + plots ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
