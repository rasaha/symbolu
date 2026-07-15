"""KVPro V3 Gate-1 — reconstruction-error eval (Phase C, recon half).

Loads captured {K,V,Q,protect_mask} per layer (real, from capture_kv.py on a pod) OR a --synthetic
plumbing fixture (NOT a quality verdict), applies affine + each symmetric candidate to the residual,
and emits per-layer + summary reconstruction metrics as JSON.

Reconstruction MSE is NOT the decision metric on its own (see attention_error_eval.py); this is the
low-level companion signal.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quantizers as Q                      # noqa: E402
import metrics as M                         # noqa: E402


def make_synthetic(n_layers=2, S=64, H_kv=4, D=128, n_protect=6, seed=0):
    """Plumbing fixture: gaussian K/V with a few high-variance 'outlier' channels marked protected.
    Explicitly NOT representative of real KV — for harness validation only."""
    g = torch.Generator().manual_seed(seed)
    layers = []
    for li in range(n_layers):
        K = torch.randn(S, H_kv, D, generator=g)
        V = torch.randn(S, H_kv, D, generator=g)
        mask = torch.zeros(H_kv, D, dtype=torch.int8)
        # mark n_protect highest-variance channels per head as protected + inject an outlier there
        for h in range(H_kv):
            idx = torch.randperm(D, generator=g)[:n_protect]
            mask[h, idx] = 1
            K[:, h, idx] *= 6.0              # outliers live in protected channels (KVPro premise)
        Q = torch.randn(max(1, S // 8), H_kv * 7, D, generator=g)   # GQA group 7
        layers.append({"K": K, "V": V, "Q": Q, "protect_mask": mask})
    return {"layers": layers, "meta": {"synthetic": True, "n_layers": n_layers, "S": S,
                                       "H_kv": H_kv, "D": D, "n_protect": n_protect}}


def load_capture(path):
    blob = torch.load(path, map_location="cpu", weights_only=False)
    if "layers" not in blob:
        raise ValueError(f"capture {path} missing 'layers'")
    return blob


def run(cap, BS=32, v_group_size=32):
    cands = Q.candidate_names()
    per_layer = []
    for li, L in enumerate(cap["layers"]):
        K, V, mask = L["K"].float(), L["V"].float(), L["protect_mask"]
        row = {"layer": li}
        for c in cands:
            Kh, Vh = Q.reconstruct(K, V, mask, c, BS=BS, v_group_size=v_group_size)
            mk = M.recon_metrics(K, Kh, protect_mask_hd=mask, tag="K_")
            mv = M.recon_metrics(V, Vh, tag="V_")
            row[c] = {**mk, **mv}
        per_layer.append(row)
    # summary: worst-case (min cos / max mse) across layers, per candidate
    summary = {}
    for c in cands:
        kcos = [r[c]["K_cos"] for r in per_layer]
        vcos = [r[c]["V_cos"] for r in per_layer]
        kunp = [r[c].get("K_unprot_cos", float("nan")) for r in per_layer]
        summary[c] = {
            "K_cos_min": min(kcos), "V_cos_min": min(vcos),
            "K_unprot_cos_min": min(x for x in kunp if x == x) if any(x == x for x in kunp) else None,
            "K_mse_max": max(r[c]["K_mse"] for r in per_layer),
            "V_mse_max": max(r[c]["V_mse"] for r in per_layer),
        }
    return {"summary": summary, "per_layer": per_layer}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Gate-1 reconstruction eval")
    ap.add_argument("--capture", default=None, help="captured KV .pt (real; from capture_kv.py)")
    ap.add_argument("--synthetic", action="store_true", help="use a plumbing fixture (NOT a verdict)")
    ap.add_argument("--out", default="reconstruction_metrics.json")
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--v-group-size", type=int, default=32)
    args = ap.parse_args(argv)

    if args.capture:
        cap = load_capture(args.capture); source = f"capture:{args.capture}"; measured = True
    elif args.synthetic:
        cap = make_synthetic(); source = "synthetic-fixture"; measured = False
    else:
        print("[FAIL] provide --capture <real.pt> or --synthetic (plumbing only)", file=sys.stderr)
        return 2

    res = run(cap, BS=args.bs, v_group_size=args.v_group_size)
    res["source"] = source
    res["label"] = "MEASURED" if measured else "NOT_A_VERDICT_SYNTHETIC"
    with open(args.out, "w") as fh:
        json.dump(res, fh, indent=2)
    print(f"[{'MEASURED' if measured else 'SYNTHETIC'}] reconstruction -> {args.out}")
    for c, s in res["summary"].items():
        print(f"  {c:7} K_cos_min={s['K_cos_min']:.5f} V_cos_min={s['V_cos_min']:.5f} "
              f"K_unprot_cos_min={s['K_unprot_cos_min']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
