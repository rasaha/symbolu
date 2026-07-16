"""KVPro V3 query-fold — Phase C/D structural audit (shared lib, CPU-pure).

For each (layer, head) the production metadata matrix M[b,d] (scale or xmin) is fit
with the PRE-REGISTERED models and scored by relative-Frobenius reconstruction error
(the decode-relevant error), variance explained, and systematic per-channel bias. The
scale uses the rank-1 multiplicative (log-additive) model + linear SVD; xmin uses the
additive model + linear SVD. Ranks are pre-registered by the CALLER — never chosen
from downstream results.
"""
from __future__ import annotations

import argparse
import csv
import json
from statistics import median
from typing import Dict, List

import torch

try:
    from . import factorize, synthetic
except ImportError:  # pragma: no cover
    import factorize      # type: ignore
    import synthetic      # type: ignore

PREREGISTERED_RANKS = (2, 4)          # frozen before any capture is viewed


def _summ(M: torch.Tensor, fit: Dict[str, object], block_meta: int) -> Dict[str, object]:
    cb = factorize.channel_bias(M, fit["fitted"])
    return {
        "var_explained": round(float(fit["var_explained"]), 5),
        "var_explained_log": (round(float(fit["var_explained_log"]), 5)
                              if "var_explained_log" in fit else None),
        "rel_frob": round(float(fit["rel_frob"]), 6),
        "max_rel_channel_bias": round(float(cb["max_rel_channel_bias"]), 6),
        "block_meta_values": block_meta,
        "prod_meta_values": M.shape[1],       # production keeps D per block
    }


def audit_head(M_bd: torch.Tensor, kind: str, ranks=PREREGISTERED_RANKS) -> Dict[str, dict]:
    """M_bd: (B, D) production metadata for one (layer, head)."""
    if M_bd.ndim != 2:
        raise ValueError(f"expected (B,D); got {tuple(M_bd.shape)}")
    models: Dict[str, dict] = {}
    if kind == "scale":
        models["rank1_mult"] = _summ(M_bd, factorize.rank1_log_multiplicative(M_bd), 1)
    elif kind == "xmin":
        models["additive"] = _summ(M_bd, factorize.two_way_additive(M_bd), 1)
    else:
        raise ValueError(f"kind must be scale|xmin; got {kind!r}")
    for R in ranks:
        models[f"svd_R{R}"] = _summ(M_bd, factorize.low_rank_svd(M_bd, R), R)
    return models


def audit_manifest(manifest: dict, kind: str, ranks=PREREGISTERED_RANKS) -> dict:
    """Loop every (layer, head), aggregate per model. Returns median + WORST-case."""
    key = "s_prod" if kind == "scale" else "xmin_prod"
    per_model: Dict[str, Dict[str, list]] = {}
    n_lh = 0
    for lyr in manifest["layers"]:
        M = lyr[key]                                          # (B, H, D)
        H = M.shape[1]
        for h in range(H):
            res = audit_head(M[:, h, :], kind, ranks)
            n_lh += 1
            for mname, m in res.items():
                pm = per_model.setdefault(mname, {"rel_frob": [], "var_explained": [],
                                                  "bias": [], "block_meta": m["block_meta_values"],
                                                  "loc": []})
                pm["rel_frob"].append(m["rel_frob"])
                pm["var_explained"].append(m["var_explained"])
                pm["bias"].append(m["max_rel_channel_bias"])
                pm["loc"].append((lyr["layer"], h))
    out = {"kind": kind, "n_layer_head": n_lh, "ranks": list(ranks), "models": {}}
    for mname, pm in per_model.items():
        rf = pm["rel_frob"]
        worst_i = max(range(len(rf)), key=lambda i: rf[i])
        out["models"][mname] = {
            "rel_frob_median": round(median(rf), 6),
            "rel_frob_worst": round(rf[worst_i], 6),
            "worst_layer_head": list(pm["loc"][worst_i]),
            "var_explained_median": round(median(pm["var_explained"]), 5),
            "var_explained_worst": round(min(pm["var_explained"]), 5),
            "max_rel_channel_bias_median": round(median(pm["bias"]), 6),
            "max_rel_channel_bias_worst": round(max(pm["bias"]), 6),
            "block_meta_values": pm["block_meta"],
            "prod_meta_values_per_block": manifest["geom"]["D"],
        }
    return out


def load_manifest(path: str) -> dict:
    return torch.load(path, map_location="cpu", weights_only=False)


def run(manifest: dict, kind: str, out_json: str = None, out_csv: str = None,
        ranks=PREREGISTERED_RANKS) -> dict:
    rep = audit_manifest(manifest, kind, ranks)
    rep["model_name"] = manifest.get("model")
    print(f"[{kind}] {rep['n_layer_head']} (layer,head) pairs, ranks={rep['ranks']}")
    for mname, m in rep["models"].items():
        print(f"  {mname:12} rel_frob med={m['rel_frob_median']:.4f} worst={m['rel_frob_worst']:.4f} "
              f"(L{m['worst_layer_head'][0]}H{m['worst_layer_head'][1]}) | "
              f"varexp med={m['var_explained_median']:.3f} worst={m['var_explained_worst']:.3f} | "
              f"chan-bias worst={m['max_rel_channel_bias_worst']:.4f} | "
              f"block_meta={m['block_meta_values']}/{m['prod_meta_values_per_block']}")
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(rep, fh, indent=2)
        print(f"  -> {out_json}")
    if out_csv:
        with open(out_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["model", "rel_frob_median", "rel_frob_worst", "var_explained_median",
                        "var_explained_worst", "chan_bias_worst", "block_meta", "prod_meta"])
            for mname, m in rep["models"].items():
                w.writerow([mname, m["rel_frob_median"], m["rel_frob_worst"],
                            m["var_explained_median"], m["var_explained_worst"],
                            m["max_rel_channel_bias_worst"], m["block_meta_values"],
                            m["prod_meta_values_per_block"]])
        print(f"  -> {out_csv}")
    return rep


def main(argv=None, kind: str = None):
    ap = argparse.ArgumentParser(description="KVPro V3 query-fold structural audit")
    ap.add_argument("--manifest", help="capture .pt from capture_metadata.py")
    ap.add_argument("--kind", choices=["scale", "xmin"], default=kind)
    ap.add_argument("--out-json"); ap.add_argument("--out-csv")
    ap.add_argument("--synthetic", choices=["factorable", "random"],
                    help="CPU self-check with known ground truth (no manifest needed)")
    a = ap.parse_args(argv)
    if not a.kind:
        ap.error("--kind scale|xmin required")
    if a.synthetic:
        man = synthetic.synthetic_metadata_manifest(factorable=(a.synthetic == "factorable"))
        print(f"[SYNTHETIC {a.synthetic}] structural self-check (clean ground truth)")
        run(man, a.kind, a.out_json, a.out_csv)
        return 0
    if not a.manifest:
        ap.error("--manifest PATH required (or --synthetic)")
    run(load_manifest(a.manifest), a.kind, a.out_json, a.out_csv)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
