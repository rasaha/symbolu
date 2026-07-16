#!/usr/bin/env python3
"""Phase H — end-to-end fake-quant quality for SURVIVING candidates (POD-ONLY).

Only run for candidates that passed Phases C–G. Reuses the FROZEN symmetric-residual
drivers (needle / hard-needle / 2000-Q MMLU) by monkey-patching `quantizers.reconstruct`
to route the query-fold candidates through the factored reconstruction (K re-quantized
onto the candidate's grid; V production-affine; protected channels exact). Same masks,
seeds, prompts, and greedy decoding as the prior study. Emits the baseline-relative
summary `decide.gate_quality` consumes. Both models must pass — run once per model.

  python run_quality.py --model Qwen/Qwen2.5-7B-Instruct --mask <m.pt> \
      --candidates QF1,QF2 --mmlu-questions 2000 --out qwen_quality.json --outdir out_qwen
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIB = os.path.join(_HERE, "..", "kvpro_v3_symmetric_residual")
for p in (_HERE, _SIB, os.path.join(_HERE, "..", "..", "CTM_plus", "KVPolicy")):
    sys.path.insert(0, p)

import candidates  # noqa: E402
import quant_ref   # noqa: E402

_QF = ("QF1", "QF2", "QF3")


def _patch_reconstruct():
    """Route QF candidates through the query-fold reconstruction; leave fp/affine/S*/P8
    to the original. build_fakequant_cache resolves Q.reconstruct at call time, so
    patching the module attribute is enough."""
    import quantizers as Q
    orig = Q.reconstruct

    def _qf(K, V, mask, candidate, BS=32, v_group_size=32, **kw):
        if candidate in _QF:
            s_prod, xmin_prod, _ = quant_ref.production_k_metadata(K, BS)
            K_hat = candidates.reconstruct_k(K, s_prod, xmin_prod, mask, candidate, BS)
            V_hat = quant_ref.production_v(V, v_group_size)
            return K_hat, V_hat
        return orig(K, V, mask, candidate, BS=BS, v_group_size=v_group_size, **kw)

    Q.reconstruct = _qf


def _acc(path, benchmark, cells):
    import results as R
    blob = json.load(open(path))
    agg = R.aggregate(blob["items"], cells, benchmark)
    return {c: agg[c]["overall"]["accuracy"] for c in cells}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 query-fold Phase H quality (pod-only)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--mask", default=os.environ.get("PROTECT_MASK_PATH"))
    ap.add_argument("--candidates", default="QF1,QF2", help="surviving QF candidates (from decide)")
    ap.add_argument("--seeds", default="0,1")
    ap.add_argument("--mmlu-questions", type=int, default=2000)
    ap.add_argument("--outdir", default="qf_quality_out")
    ap.add_argument("--out", default="quality.json")
    a = ap.parse_args(argv)
    if not a.mask or not os.path.isfile(a.mask):
        print(f"[FAIL] mask missing: {a.mask!r}", file=sys.stderr); return 2

    qf = [c for c in a.candidates.split(",") if c in _QF]
    cells = ["fp", "affine"] + qf
    cells_csv = ",".join(cells)
    os.makedirs(a.outdir, exist_ok=True)
    np_, hp_, mp_ = (os.path.join(a.outdir, f) for f in ("needle.json", "hard_needle.json", "mmlu.json"))

    _patch_reconstruct()                                # MUST precede any driver run
    import needle_driver, hard_needle_driver, mmlu_driver

    print(f"[quality] cells={cells_csv} model={a.model}")
    needle_driver.main(["--model", a.model, "--mask", a.mask, "--seeds", a.seeds,
                        "--cells", cells_csv, "--out", np_])
    hard_needle_driver.main(["--model", a.model, "--mask", a.mask, "--seeds", a.seeds,
                             "--cells", cells_csv, "--out", hp_])
    mmlu_driver.main(["--model", a.model, "--mask", a.mask, "--num-questions", str(a.mmlu_questions),
                      "--real", "--cells", cells_csv, "--out", mp_])

    acc_n = _acc(np_, "needle", cells)
    acc_h = _acc(hp_, "hard_needle", cells)
    acc_m = _acc(mp_, "mmlu", cells)
    aff_n = max(acc_n["affine"], 1e-9)
    aff_h = max(acc_h["affine"], 1e-9)

    per_candidate = {}
    for c in qf:
        per_candidate[c] = {
            "needle_frac_of_affine": round(acc_n[c] / aff_n, 4),
            "hard_needle_frac_of_affine": round(acc_h[c] / aff_h, 4),
            "mmlu_drop_pts": round((acc_m["affine"] - acc_m[c]) * 100, 3),
            "needle_acc": round(acc_n[c], 4), "hard_needle_acc": round(acc_h[c], 4),
            "mmlu_acc": round(acc_m[c], 4),
        }
    blob = {"model": a.model, "label": "MEASURED", "cells": cells,
            "affine_acc": {"needle": round(acc_n["affine"], 4), "hard_needle": round(acc_h["affine"], 4),
                           "mmlu": round(acc_m["affine"], 4)},
            "fp_acc": {"needle": round(acc_n["fp"], 4), "mmlu": round(acc_m["fp"], 4)},
            "per_candidate": per_candidate}
    json.dump(blob, open(a.out, "w"), indent=2)
    print(f"[MEASURED] quality -> {a.out}")
    for c, m in per_candidate.items():
        print(f"  {c}: needle {m['needle_frac_of_affine']}x-affine  hard {m['hard_needle_frac_of_affine']}x  "
              f"mmlu drop {m['mmlu_drop_pts']}pts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
